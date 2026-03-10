from __future__ import annotations

from pathlib import Path
from typing import Any

from orchestrator.config import CONTEXT_SNIPPET_BYTES
from orchestrator.models import SessionState
from orchestrator.project_layout import ProjectLayout
from orchestrator.retrieval_engine import RetrievalEngine
from orchestrator.stage_router import StageRouter


class ContextBuilder:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.layout = ProjectLayout(root)
        self.retrieval = RetrievalEngine(root)
        self.router = StageRouter()

    def build(self, state: SessionState, model: str) -> dict[str, Any]:
        relevant_files = self.retrieval.select_context_files(state)
        related_tests = self.retrieval.related_tests(relevant_files)
        recent_changes = self.retrieval.recent_git_changes()

        return {
            "task_id": state.task_id,
            "project_type": state.project_type,
            "current_stage": state.current_stage,
            "recommended_model": self.router.recommended_owner(state.current_stage),
            "goal": state.goal,
            "constraints": state.constraints,
            "relevant_files": [self._file_payload(path) for path in relevant_files],
            "recent_changes": recent_changes or state.recent_changes,
            "related_tests": [self._file_payload(path) for path in related_tests],
            "verification_summary": state.last_verification.get(
                "summary", "No verification run has been recorded."
            ),
            "repo_instructions": {
                "agents_md": self._read_text(self.layout.agents_path),
                "claude_md": self._read_text(self.layout.claude_path),
                "gemini_md": self._read_text(self.layout.gemini_path),
            },
            "handoff_summary": state.handoff_summary or self._read_text(self.layout.handoff_path),
            "open_risks": state.open_risks,
            "requested_model": model,
        }

    def _read_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _file_payload(self, relative_path: str) -> dict[str, str]:
        path = self.root / relative_path
        if not path.exists():
            return {"path": relative_path, "content": ""}
        raw = path.read_text(encoding="utf-8", errors="replace")
        return {
            "path": relative_path,
            "content": raw[:CONTEXT_SNIPPET_BYTES],
        }
