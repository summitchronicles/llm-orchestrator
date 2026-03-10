from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from orchestrator.verification_runner import VerificationRunner
from orchestrator.workspace_manager import WorkspaceManager


class ToolExecutor:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.verification_runner = VerificationRunner(self.root)
        self.workspace_manager = WorkspaceManager(self.root)

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        action_name = action.get("action")
        if not action_name:
            raise ValueError("Action payload must include an `action` field.")

        dispatch = {
            "read_file": self.read_file,
            "write_file": self.write_file,
            "edit_file": self.edit_file,
            "list_directory": self.list_directory,
            "run_build": lambda payload: self.verification_runner.run_named_steps(["build"]),
            "run_tests": lambda payload: self.verification_runner.run_named_steps(["tests"]),
            "run_lint": lambda payload: self.verification_runner.run_named_steps(["lint"]),
            "run_typecheck": lambda payload: self.verification_runner.run_named_steps(["typecheck"]),
            "create_branch": self.create_branch,
            "commit_changes": self.commit_changes,
            "create_worktree": self.create_worktree,
            "run_semgrep": lambda payload: self.verification_runner.run_named_steps(["security:semgrep"]),
            "run_trivy": lambda payload: self.verification_runner.run_named_steps(["security:trivy"]),
            "run_secret_scan": lambda payload: self.verification_runner.run_named_steps(["security:gitleaks"]),
        }
        if action_name not in dispatch:
            raise ValueError(f"Unsupported action: {action_name}")
        return dispatch[action_name](action)

    def read_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve_path(payload["path"])
        return {"path": str(path.relative_to(self.root)), "content": path.read_text(encoding="utf-8")}

    def write_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve_path(payload["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        content = payload.get("content", "")
        path.write_text(content, encoding="utf-8")
        return {"path": str(path.relative_to(self.root)), "bytes_written": len(content.encode("utf-8"))}

    def edit_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve_path(payload["path"])
        original = path.read_text(encoding="utf-8")
        if "find" in payload and "replace" in payload:
            updated = original.replace(payload["find"], payload["replace"])
        elif "content" in payload:
            updated = payload["content"]
        else:
            raise ValueError("edit_file requires either `content` or both `find` and `replace`.")
        path.write_text(updated, encoding="utf-8")
        return {
            "path": str(path.relative_to(self.root)),
            "changed": updated != original,
        }

    def list_directory(self, payload: dict[str, Any]) -> dict[str, Any]:
        base = payload.get("path", ".")
        path = self._resolve_path(base)
        entries = sorted(item.name for item in path.iterdir())
        return {"path": str(path.relative_to(self.root)), "entries": entries}

    def create_branch(self, payload: dict[str, Any]) -> dict[str, Any]:
        branch = str(payload["name"])
        if not branch.startswith("codex/"):
            branch = f"codex/{branch}"
        result = subprocess.run(
            ["git", "branch", branch],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return {"branch": branch}

    def commit_changes(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = str(payload["message"])
        add_result = subprocess.run(
            ["git", "add", "-A"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if add_result.returncode != 0:
            raise RuntimeError(add_result.stderr.strip() or add_result.stdout.strip())

        commit_result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if commit_result.returncode != 0:
            raise RuntimeError(commit_result.stderr.strip() or commit_result.stdout.strip())
        return {"message": message, "result": commit_result.stdout.strip()}

    def create_worktree(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.workspace_manager.create_worktree(str(payload["task_id"]))

    def _resolve_path(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError(f"Path escapes repository root: {relative_path}")
        return path

    @staticmethod
    def from_json(text: str) -> dict[str, Any]:
        return json.loads(text)
