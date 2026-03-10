from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orchestrator.models import SessionState, utc_now
from orchestrator.project_layout import ProjectLayout


class TrajectoryStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = ProjectLayout(root).trajectory_path

    def append(
        self,
        *,
        state: SessionState,
        model: str,
        event_type: str,
        input_summary: str = "",
        files_touched: list[str] | None = None,
        command_run: str = "",
        command_result: str = "",
        verification_status: str = "skipped",
        notes: str = "",
    ) -> None:
        payload: dict[str, Any] = {
            "timestamp": utc_now(),
            "task_id": state.task_id,
            "model": model,
            "stage": state.current_stage,
            "event_type": event_type,
            "input_summary": input_summary,
            "files_touched": files_touched or [],
            "command_run": command_run,
            "command_result": command_result,
            "verification_status": verification_status,
            "notes": notes,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def read_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:]]
