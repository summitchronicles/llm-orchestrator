from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from orchestrator.config import WORKSPACES_DIRNAME
from orchestrator.context_builder import ContextBuilder
from orchestrator.handoff_generator import HandoffGenerator
from orchestrator.models import SessionState
from orchestrator.project_layout import ProjectLayout
from orchestrator.repair_loop import RepairLoop
from orchestrator.retrieval_engine import RetrievalEngine
from orchestrator.stage_router import StageRouter
from orchestrator.state_manager import StateManager
from orchestrator.task_logger import TaskLogger
from orchestrator.templates import (
    render_agents_md,
    render_claude_md,
    render_current_task_md,
    render_gemini_md,
)
from orchestrator.tool_executor import ToolExecutor
from orchestrator.trajectory_store import TrajectoryStore
from orchestrator.verification_runner import VerificationRunner
from orchestrator.workspace_manager import WorkspaceManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize orchestrator files.")
    init_parser.add_argument("--task-id", default="default-task")
    init_parser.add_argument("--goal", default="Define the current development goal.")
    init_parser.add_argument("--project-type", choices=("greenfield", "brownfield"))
    init_parser.add_argument("--constraint", action="append", default=[])

    check_parser = subparsers.add_parser("check", help="Check stage ownership.")
    check_parser.add_argument("--model", required=True, choices=("codex", "claude", "gemini"))

    milestone_parser = subparsers.add_parser("milestone", help="Record a milestone.")
    milestone_parser.add_argument("--model", required=True, choices=("codex", "claude", "gemini"))
    milestone_parser.add_argument("--done", required=True)
    milestone_parser.add_argument("--risk", action="append", default=[])
    milestone_parser.add_argument("--advance", action="store_true")

    takeover_parser = subparsers.add_parser("takeover", help="Create a takeover context pack.")
    takeover_parser.add_argument("--model", required=True, choices=("codex", "claude", "gemini"))

    context_parser = subparsers.add_parser("context", help="Generate a context pack.")
    context_parser.add_argument("--model", required=True, choices=("codex", "claude", "gemini"))

    subparsers.add_parser("verify", help="Run verification pipeline.")
    subparsers.add_parser("repair", help="Generate a repair prompt from the latest failure.")

    replay_parser = subparsers.add_parser("replay", help="Show recent trajectory events.")
    replay_parser.add_argument("--last", type=int, default=20)
    replay_parser.add_argument(
        "--event-type",
        action="append",
        choices=("check", "milestone", "takeover", "tool_call", "verification", "repair", "handoff"),
    )
    replay_parser.add_argument("--failed-only", action="store_true")

    tool_parser = subparsers.add_parser("tool", help="Execute a structured action payload.")
    tool_group = tool_parser.add_mutually_exclusive_group(required=True)
    tool_group.add_argument("--action-json")
    tool_group.add_argument("--action-file")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path.cwd()

    try:
        handlers = {
            "init": lambda: cmd_init(root, args),
            "check": lambda: cmd_check(root, args),
            "milestone": lambda: cmd_milestone(root, args),
            "takeover": lambda: cmd_takeover(root, args),
            "context": lambda: cmd_context(root, args),
            "verify": lambda: cmd_verify(root),
            "repair": lambda: cmd_repair(root),
            "replay": lambda: cmd_replay(root, args),
            "tool": lambda: cmd_tool(root, args),
        }
        handlers[args.command]()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_init(root: Path, args: argparse.Namespace) -> None:
    layout = ProjectLayout(root)
    layout.activate_managed_layout()
    state_manager = StateManager(root)
    state = state_manager.bootstrap(
        task_id=args.task_id,
        goal=args.goal,
        project_type=args.project_type,
        constraints=args.constraint,
    )
    logger = TaskLogger(root)
    trajectory = TrajectoryStore(root)
    WorkspaceManager(root).ensure_root()
    _ensure_gitignore_entries(root, [f"{layout.config.runtime_dir}/", f"{WORKSPACES_DIRNAME}/"])

    _write_if_missing(layout.agents_path, render_agents_md())
    _write_if_missing(layout.claude_path, render_claude_md())
    _write_if_missing(layout.gemini_path, render_gemini_md())
    _write_if_missing(layout.handoff_path, "# Handoff\n\nNo handoff has been generated yet.\n")
    layout.current_task_path.parent.mkdir(parents=True, exist_ok=True)
    layout.current_task_path.write_text(render_current_task_md(state), encoding="utf-8")
    logger.append_session(
        "Initialization",
        [
            f"Task `{state.task_id}` initialized.",
            f"Current stage set to `{state.current_stage}`.",
            f"Recommended owner is `{state.current_owner}`.",
        ],
    )
    trajectory.append(
        state=state,
        model="human",
        event_type="milestone",
        input_summary="Initialized orchestrator state.",
        files_touched=[
            _relative(root, layout.config_path),
            _relative(root, layout.agents_path),
            _relative(root, layout.claude_path),
            _relative(root, layout.gemini_path),
            _relative(root, layout.current_task_path),
            _relative(root, layout.handoff_path),
        ],
        verification_status=state.verification_status,
    )
    print(f"Initialized orchestrator for task `{state.task_id}` at stage `{state.current_stage}`.")


def cmd_check(root: Path, args: argparse.Namespace) -> None:
    state_manager = StateManager(root)
    state = state_manager.load()
    router = StageRouter()
    decision = router.decision(args.model, state)
    trajectory = TrajectoryStore(root)
    trajectory.append(
        state=state,
        model=args.model,
        event_type="check",
        input_summary=f"Check ownership for model `{args.model}`.",
        verification_status=state.verification_status,
        notes=decision["reason"],
    )
    print(f"CURRENT STAGE: {decision['current_stage']}")
    print(f"OWNER: {decision['owner']}")
    print(f"CURRENT MODEL: {decision['current_model']}")
    print(f"DECISION: {decision['decision']}")


def cmd_milestone(root: Path, args: argparse.Namespace) -> None:
    layout = ProjectLayout(root)
    state_manager = StateManager(root)
    state = state_manager.load()
    router = StageRouter()
    retrieval = RetrievalEngine(root)
    handoff_generator = HandoffGenerator(root)
    logger = TaskLogger(root)
    trajectory = TrajectoryStore(root)

    state.active_model = args.model
    state.last_milestone = args.done
    state.open_risks = list(dict.fromkeys([*state.open_risks, *args.risk]))
    state.recent_changes = retrieval.recent_git_changes()
    state.related_tests = retrieval.related_tests(state.recent_changes)

    if router.should_advance(args.done, force_advance=args.advance):
        router.advance(state)
    else:
        router.sync_state(state)

    handoff = handoff_generator.generate(state)
    state.handoff_summary = handoff["summary"]
    state_manager.save(state)
    layout.current_task_path.parent.mkdir(parents=True, exist_ok=True)
    layout.current_task_path.write_text(render_current_task_md(state), encoding="utf-8")

    logger.append_session(
        "Milestone",
        [
            f"Model `{args.model}` recorded milestone: {args.done}",
            f"Current stage is now `{state.current_stage}`.",
            f"Next stage is `{state.next_stage or 'none'}`.",
        ],
    )
    trajectory.append(
        state=state,
        model=args.model,
        event_type="milestone",
        input_summary=args.done,
        files_touched=state.recent_changes,
        verification_status=state.verification_status,
        notes=handoff["summary"],
    )
    trajectory.append(
        state=state,
        model=args.model,
        event_type="handoff",
        input_summary="Generated handoff after milestone.",
        files_touched=[_relative(root, layout.handoff_path), _relative(root, layout.current_task_path)],
        verification_status=state.verification_status,
        notes=handoff["summary"],
    )
    print(handoff["summary"])


def cmd_takeover(root: Path, args: argparse.Namespace) -> None:
    layout = ProjectLayout(root)
    state_manager = StateManager(root)
    state = state_manager.load()
    state.active_model = args.model
    handoff = HandoffGenerator(root).generate(state, target_model=args.model)
    state.handoff_summary = handoff["summary"]
    state_manager.save(state)
    layout.current_task_path.parent.mkdir(parents=True, exist_ok=True)
    layout.current_task_path.write_text(render_current_task_md(state), encoding="utf-8")
    context = ContextBuilder(root).build(state, args.model)

    TrajectoryStore(root).append(
        state=state,
        model=args.model,
        event_type="takeover",
        input_summary=f"Takeover requested by `{args.model}`.",
        files_touched=[_relative(root, layout.handoff_path), _relative(root, layout.current_task_path)],
        verification_status=state.verification_status,
        notes=handoff["summary"],
    )
    print(json.dumps(context, indent=2))


def cmd_context(root: Path, args: argparse.Namespace) -> None:
    state_manager = StateManager(root)
    state = state_manager.load()
    context = ContextBuilder(root).build(state, args.model)
    TrajectoryStore(root).append(
        state=state,
        model=args.model,
        event_type="handoff",
        input_summary=f"Context generated for `{args.model}`.",
        verification_status=state.verification_status,
        notes="Context pack built without ownership change.",
    )
    print(json.dumps(context, indent=2))


def cmd_verify(root: Path) -> None:
    layout = ProjectLayout(root)
    state_manager = StateManager(root)
    state = state_manager.load()
    verification = VerificationRunner(root).run_all()
    state.last_verification = verification
    state.verification_status = str(verification["status"])
    state_manager.save(state)
    layout.current_task_path.parent.mkdir(parents=True, exist_ok=True)
    layout.current_task_path.write_text(render_current_task_md(state), encoding="utf-8")

    TaskLogger(root).append_session(
        "Verification",
        [
            verification["summary"],
            *[
                f"{step['name']}: {step['status']}"
                for step in verification["steps"]
            ],
        ],
    )
    TrajectoryStore(root).append(
        state=state,
        model=state.active_model or state.current_owner,
        event_type="verification",
        input_summary="Ran verification pipeline.",
        command_result=verification["summary"],
        verification_status=state.verification_status,
    )
    print(verification["summary"])
    for step in verification["steps"]:
        detail = f" ({step['reason']})" if step.get("reason") else ""
        print(f"- {step['name']}: {step['status']}{detail}")


def cmd_repair(root: Path) -> None:
    layout = ProjectLayout(root)
    state_manager = StateManager(root)
    state = state_manager.load()
    repair = RepairLoop(root).generate(state)
    TrajectoryStore(root).append(
        state=state,
        model=state.active_model or state.current_owner,
        event_type="repair",
        input_summary="Generated repair prompt from latest verification failure.",
        files_touched=[_relative(root, layout.repair_prompt_path)],
        verification_status=state.verification_status,
        notes=repair["summary"],
    )
    print(repair["prompt"])


def cmd_replay(root: Path, args: argparse.Namespace) -> None:
    events = TrajectoryStore(root).read_recent(limit=args.last)
    if args.event_type:
        events = [event for event in events if event["event_type"] in set(args.event_type)]
    if args.failed_only:
        events = [event for event in events if event["verification_status"] == "failed"]
    if not events:
        print("No trajectory events recorded.")
        return
    for event in events:
        print(
            f"{event['timestamp']} | {event['event_type']} | "
            f"stage={event['stage']} | model={event['model']} | "
            f"verification={event['verification_status']} | {event['input_summary']}"
        )


def cmd_tool(root: Path, args: argparse.Namespace) -> None:
    if args.action_json:
        payload = ToolExecutor.from_json(args.action_json)
    else:
        payload = ToolExecutor.from_json(Path(args.action_file).read_text(encoding="utf-8"))

    executor = ToolExecutor(root)
    result = executor.execute(payload)

    state = _safe_state(root)
    TrajectoryStore(root).append(
        state=state,
        model=state.active_model or state.current_owner,
        event_type="tool_call",
        input_summary=payload.get("action", "unknown"),
        command_run=json.dumps(payload),
        command_result=json.dumps(result),
        verification_status=state.verification_status,
    )
    print(json.dumps(result, indent=2))


def _safe_state(root: Path) -> SessionState:
    state_manager = StateManager(root)
    if state_manager.exists():
        return state_manager.load()
    return SessionState()


def _write_if_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _ensure_gitignore_entries(root: Path, entries: list[str]) -> None:
    path = root / ".gitignore"
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated = list(existing)
    for entry in entries:
        if entry not in updated:
            updated.append(entry)
    path.write_text("\n".join(updated).strip() + "\n", encoding="utf-8")


def _relative(root: Path, path: Path) -> str:
    return str(path.relative_to(root))
