from __future__ import annotations

from pathlib import Path

from orchestrator.project_layout import ProjectLayout


class TaskLogger:
    def __init__(self, root: Path) -> None:
        self.path = ProjectLayout(root).task_log_path

    def append_session(self, title: str, lines: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("# Task Log\n\n", encoding="utf-8")
        content = [f"## {title}", ""]
        for line in lines:
            content.append(f"- {line}")
        content.append("")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(content))
