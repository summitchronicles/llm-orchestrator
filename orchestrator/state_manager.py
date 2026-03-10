from __future__ import annotations

import json
from pathlib import Path

from orchestrator.config import WORKSPACES_DIRNAME
from orchestrator.models import SessionState
from orchestrator.project_layout import ProjectLayout
from orchestrator.stage_router import StageRouter


class StateManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.layout = ProjectLayout(root)
        self.state_path = self.layout.state_path
        self.router = StageRouter()

    def exists(self) -> bool:
        return self.state_path.exists()

    def detect_project_type(self) -> str:
        ignored_names = {
            ".git",
            self.layout.config.runtime_dir,
            self.layout.config_path.name,
            self.layout.agents_path.name,
            self.layout.claude_path.name,
            self.layout.gemini_path.name,
            ".gitignore",
            WORKSPACES_DIRNAME,
        }
        entries = [path for path in self.root.iterdir() if path.name not in ignored_names]
        return "brownfield" if entries else "greenfield"

    def bootstrap(
        self,
        task_id: str,
        goal: str,
        project_type: str | None = None,
        constraints: list[str] | None = None,
    ) -> SessionState:
        state = SessionState(
            task_id=task_id,
            goal=goal,
            project_type=project_type or self.detect_project_type(),
            constraints=constraints or [],
        )
        self.router.sync_state(state)
        self.save(state)
        return state

    def load(self) -> SessionState:
        if not self.exists():
            raise FileNotFoundError(
                "SESSION_STATE.json is missing. Run `orchestrator init` first."
            )
        return SessionState.from_dict(json.loads(self.state_path.read_text(encoding="utf-8")))

    def save(self, state: SessionState) -> None:
        state.touch()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
