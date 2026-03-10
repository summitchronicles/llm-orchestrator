# Multi-Model AI Development Orchestrator

Local Python CLI for coordinating AI-assisted development sessions across Codex, Claude, and Gemini with explicit state, verification, handoffs, and structured history.

## Install

Use `pipx` if you want one reusable CLI for every project on your machine.

```bash
pipx install llm-orchestrator
```

For local development of this repo:

```bash
python3 -m pip install -e .
```

## Quick Start

```bash
cd /path/to/your/project
orchestrator init --task-id task-auth --goal "Build authentication system"
orchestrator check --model codex
orchestrator context --model codex
orchestrator milestone --model codex --done "planning complete"
orchestrator takeover --model claude
orchestrator verify
orchestrator repair
orchestrator replay --last 20
```

## Commands

- `init`: bootstrap state files and repo instructions.
- `check`: compare the current stage against a model request.
- `milestone`: record progress, update state, and refresh handoff docs.
- `takeover`: switch the active model and emit a context pack.
- `context`: build a context pack without changing ownership.
- `verify`: run detected build, test, lint, typecheck, and security checks.
- `repair`: generate a repair prompt from the latest failed verification.
- `replay`: inspect recent trajectory events.
- `tool`: execute a structured tool action JSON payload.

## Project Layout

- `orchestrator.toml`: project-level orchestrator config.
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`: repo instruction files kept at the repo root.
- `.orchestrator/SESSION_STATE.json`
- `.orchestrator/CURRENT_TASK.md`
- `.orchestrator/TASK_LOG.md`
- `.orchestrator/HANDOFF.md`
- `.orchestrator/trajectory.jsonl`
- `.orchestrator/REPAIR_PROMPT.md`

`orchestrator init` also appends `.orchestrator/` and `.workspaces/` to the target repo's `.gitignore`.

## Notes

- Workspaces use `git worktree` and require the repository to have an initial commit.
- Verification steps are detected from the local environment and marked `skipped` when the required tools are unavailable.
- Older repos that still have root-level `SESSION_STATE.json` and related files continue to work through a legacy fallback path.
