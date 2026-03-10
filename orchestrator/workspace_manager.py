from __future__ import annotations

import re
import subprocess
from pathlib import Path

from orchestrator.config import WORKSPACES_DIRNAME


class WorkspaceManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.workspaces_root = root / WORKSPACES_DIRNAME

    def ensure_root(self) -> None:
        self.workspaces_root.mkdir(exist_ok=True)

    def sanitize_task_id(self, task_id: str) -> str:
        return re.sub(r"[^a-zA-Z0-9._-]+", "-", task_id).strip("-") or "task"

    def branch_name(self, task_id: str) -> str:
        return f"codex/{self.sanitize_task_id(task_id)}"

    def repo_has_commit(self) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def create_worktree(self, task_id: str) -> dict[str, str]:
        self.ensure_root()
        if not self.repo_has_commit():
            raise RuntimeError(
                "Cannot create a git worktree before the repository has an initial commit."
            )

        workspace_name = self.sanitize_task_id(task_id)
        workspace_path = self.workspaces_root / workspace_name
        branch_name = self.branch_name(task_id)

        if workspace_path.exists():
            return {"workspace": str(workspace_path), "branch": branch_name}

        branch_exists = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        ).returncode == 0

        command = ["git", "worktree", "add", str(workspace_path)]
        if branch_exists:
            command.append(branch_name)
        else:
            command.extend(["-b", branch_name])

        result = subprocess.run(
            command,
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())

        return {"workspace": str(workspace_path), "branch": branch_name}
