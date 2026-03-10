from __future__ import annotations

from orchestrator.models import SessionState


def _bullet_list(items: list[str], fallback: str) -> str:
    if not items:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in items)


def render_agents_md() -> str:
    return """# AGENTS

Rules for all AI agents in this repository:

- never skip verification
- produce structured outputs
- update the task log through the orchestrator
- respect stage ownership
- use explicit handoffs when changing models
- keep humans in control for ambiguous or risky decisions
"""


def render_claude_md() -> str:
    return """# CLAUDE

Primary responsibilities:

- frontend implementation
- UI and UX iteration
- security review
- vulnerability analysis

Structured response format:

```json
{
  "summary": "...",
  "files_changed": [],
  "risks": [],
  "tests_added": [],
  "next_stage_suggestion": ""
}
```
"""


def render_gemini_md() -> str:
    return """# GEMINI

Primary responsibilities:

- documentation
- test generation
- negative testing
- adversarial reasoning

Structured response format:

```json
{
  "summary": "...",
  "files_changed": [],
  "risks": [],
  "tests_added": [],
  "next_stage_suggestion": ""
}
```
"""


def render_current_task_md(state: SessionState) -> str:
    verification_summary = state.last_verification.get(
        "summary", "No verification run has been recorded yet."
    )
    return f"""# Current Task

- Task ID: `{state.task_id}`
- Goal: {state.goal}
- Project Type: `{state.project_type}`
- Current Stage: `{state.current_stage}`
- Recommended Owner: `{state.current_owner}`
- Active Model: `{state.active_model or "unassigned"}`
- Next Stage: `{state.next_stage or "none"}`
- Verification Status: `{state.verification_status}`
- Workspace: `{state.workspace or "not assigned"}`

## Constraints

{_bullet_list(state.constraints, "No explicit constraints recorded.")}

## Open Risks

{_bullet_list(state.open_risks, "No open risks recorded.")}

## Recent Changes

{_bullet_list(state.recent_changes, "No recent file changes captured yet.")}

## Last Verification

{verification_summary}
"""


def render_handoff_md(state: SessionState, summary: str) -> str:
    verification_summary = state.last_verification.get(
        "summary", "No verification results are available yet."
    )
    return f"""# Handoff

## Summary

{summary}

## State Snapshot

- Task ID: `{state.task_id}`
- Goal: {state.goal}
- Current Stage: `{state.current_stage}`
- Recommended Owner: `{state.current_owner}`
- Active Model: `{state.active_model or "unassigned"}`
- Next Stage: `{state.next_stage or "none"}`
- Verification Status: `{state.verification_status}`

## Recent Changes

{_bullet_list(state.recent_changes, "No recent file changes captured yet.")}

## Open Risks

{_bullet_list(state.open_risks, "No open risks recorded.")}

## Verification Summary

{verification_summary}
"""


def render_repair_prompt(summary: str, failed_steps: list[str], notes: list[str]) -> str:
    failed = _bullet_list(failed_steps, "No failed steps were detected.")
    note_block = _bullet_list(notes, "No additional notes.")
    return f"""# Repair Prompt

## Failure Summary

{summary}

## Failed Steps

{failed}

## Instructions

- Fix the minimum set of issues needed to make verification pass.
- Preserve the current stage intent and avoid unrelated refactors.
- Update tests when behavior changes.
- Rerun `orchestrator verify` after edits.

## Notes

{note_block}
"""
