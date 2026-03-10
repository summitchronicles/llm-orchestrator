from __future__ import annotations

from pathlib import Path

from orchestrator.models import SessionState
from orchestrator.project_layout import ProjectLayout
from orchestrator.templates import render_handoff_md


class HandoffGenerator:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = ProjectLayout(root).handoff_path

    def generate(self, state: SessionState, target_model: str | None = None) -> dict[str, str]:
        summary = (
            f"Stage `{state.current_stage}` is ready for "
            f"`{target_model or state.current_owner}`. "
            f"Last milestone: {state.last_milestone or 'none recorded'}."
        )
        markdown = render_handoff_md(state, summary)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(markdown, encoding="utf-8")
        return {"summary": summary, "markdown": markdown}
