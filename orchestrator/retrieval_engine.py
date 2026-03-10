from __future__ import annotations

import re
import subprocess
from pathlib import Path

from orchestrator.config import CONTEXT_FILE_LIMIT, WORKSPACES_DIRNAME
from orchestrator.models import SessionState
from orchestrator.project_layout import ProjectLayout


class RetrievalEngine:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.layout = ProjectLayout(root)

    def recent_git_changes(self, limit: int = 10) -> list[str]:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []
        files: list[str] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            candidate = line[3:].strip()
            if " -> " in candidate:
                candidate = candidate.split(" -> ", 1)[1]
            if self._should_ignore_path(candidate):
                continue
            files.append(candidate)
        return files[:limit]

    def referenced_files_from_current_task(self, limit: int = 10) -> list[str]:
        task_path = self.layout.current_task_path
        if not task_path.exists():
            return []
        text = task_path.read_text(encoding="utf-8")
        patterns = re.findall(r"`([^`\n]+\.[\w]+)`|((?:[\w.-]+/)+[\w.-]+\.[\w]+)", text)
        candidates = []
        for backticked, raw in patterns:
            candidate = backticked or raw
            if self._should_ignore_path(candidate):
                continue
            resolved = (self.root / candidate).resolve()
            if resolved.exists() and resolved.is_file():
                candidates.append(candidate)
        return list(dict.fromkeys(candidates))[:limit]

    def related_tests(self, files: list[str], limit: int = 6) -> list[str]:
        tests_dir = self.root / "tests"
        if not tests_dir.exists():
            return []

        selected: list[str] = []
        all_tests = [path for path in tests_dir.rglob("*") if path.is_file()]
        for file_name in files:
            stem = Path(file_name).stem.replace("test_", "")
            for test_path in all_tests:
                relative = str(test_path.relative_to(self.root))
                if stem and stem in test_path.stem and relative not in selected:
                    selected.append(relative)
                    if len(selected) >= limit:
                        return selected
        return selected[:limit]

    def dependency_linked_files(self, files: list[str], limit: int = 6) -> list[str]:
        linked: list[str] = []
        for file_name in files:
            path = self.root / file_name
            parent = path.parent
            if not parent.exists():
                continue
            for sibling in sorted(parent.iterdir()):
                if not sibling.is_file() or sibling == path:
                    continue
                relative = str(sibling.relative_to(self.root))
                if relative not in linked:
                    linked.append(relative)
                if len(linked) >= limit:
                    return linked
        return linked[:limit]

    def verification_failure_files(self, state: SessionState, limit: int = 6) -> list[str]:
        if not state.last_verification:
            return []
        blob = "\n".join(
            step.get("stdout", "") + "\n" + step.get("stderr", "")
            for step in state.last_verification.get("steps", [])
        )
        matches = re.findall(r"[\w./-]+\.[A-Za-z0-9]+", blob)
        selected: list[str] = []
        for match in matches:
            resolved = (self.root / match).resolve()
            if resolved.exists() and resolved.is_file():
                relative = str(resolved.relative_to(self.root))
                if self._should_ignore_path(relative):
                    continue
                if relative not in selected:
                    selected.append(relative)
                if len(selected) >= limit:
                    return selected
        return selected

    def select_context_files(self, state: SessionState, limit: int = CONTEXT_FILE_LIMIT) -> list[str]:
        ranked: list[str] = []

        def add_many(items: list[str]) -> None:
            for item in items:
                if item not in ranked:
                    ranked.append(item)

        add_many(state.recent_changes)
        add_many(self.recent_git_changes())
        add_many(self.referenced_files_from_current_task())
        add_many(self.verification_failure_files(state))
        add_many(self.dependency_linked_files(ranked))
        add_many(self.related_tests(ranked))

        final: list[str] = []
        for item in ranked:
            if len(final) >= limit:
                break
            path = self.root / item
            if path.exists() and path.is_file() and not self._should_ignore_path(item):
                final.append(item)
        return final

    def _should_ignore_path(self, relative_path: str) -> bool:
        normalized = relative_path.replace("\\", "/").lstrip("./")
        if normalized.startswith(f"{WORKSPACES_DIRNAME}/"):
            return True
        return self.layout.is_runtime_artifact(normalized)
