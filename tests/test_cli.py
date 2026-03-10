from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from orchestrator.cli import main


class OrchestratorCliTests(unittest.TestCase):
    def run_cli(self, cwd: Path, *args: str) -> tuple[int, str]:
        stream = StringIO()
        previous = Path.cwd()
        try:
            os.chdir(cwd)
            with redirect_stdout(stream):
                code = main(list(args))
        finally:
            os.chdir(previous)
        return code, stream.getvalue()

    def test_init_creates_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, output = self.run_cli(
                root,
                "init",
                "--task-id",
                "task-auth",
                "--goal",
                "Build authentication",
            )
            self.assertEqual(code, 0)
            self.assertIn("Initialized orchestrator", output)
            for filename in (
                "orchestrator.toml",
                "AGENTS.md",
                "CLAUDE.md",
                "GEMINI.md",
            ):
                self.assertTrue((root / filename).exists(), filename)
            for filename in (
                "SESSION_STATE.json",
                "CURRENT_TASK.md",
                "TASK_LOG.md",
                "HANDOFF.md",
            ):
                self.assertTrue((root / ".orchestrator" / filename).exists(), filename)
            gitignore = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn(".orchestrator/", gitignore)
            self.assertIn(".workspaces/", gitignore)

    def test_milestone_advances_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init")
            code, _ = self.run_cli(
                root,
                "milestone",
                "--model",
                "codex",
                "--done",
                "planning complete",
            )
            self.assertEqual(code, 0)
            state = json.loads((root / ".orchestrator" / "SESSION_STATE.json").read_text(encoding="utf-8"))
            self.assertEqual(state["current_stage"], "backend")
            self.assertEqual(state["current_owner"], "codex")

    def test_verify_records_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init")
            (root / "orchestrator").mkdir()
            (root / "orchestrator" / "__init__.py").write_text("", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_smoke.py").write_text(
                "import unittest\n\n\nclass Smoke(unittest.TestCase):\n"
                "    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            code, output = self.run_cli(root, "verify")
            self.assertEqual(code, 0)
            self.assertIn("Verification", output)
            state = json.loads(
                (root / ".orchestrator" / "SESSION_STATE.json").read_text(encoding="utf-8")
            )
            self.assertIn("summary", state["last_verification"])

    def test_repair_requires_failed_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli(root, "init")
            state_path = root / ".orchestrator" / "SESSION_STATE.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["last_verification"] = {
                "summary": "Verification failed: 0 passed, 1 failed, 0 skipped.",
                "steps": [
                    {
                        "name": "tests:pytest",
                        "status": "failed",
                        "stdout": "",
                        "stderr": "AssertionError: boom",
                    }
                ],
            }
            state["verification_status"] = "failed"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            code, output = self.run_cli(root, "repair")
            self.assertEqual(code, 0)
            self.assertIn("Repair Prompt", output)

    def test_legacy_root_state_still_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_state = {
                "task_id": "legacy-task",
                "goal": "Legacy setup",
                "project_type": "brownfield",
                "current_stage": "planning",
                "current_owner": "codex",
                "verification_status": "not_run",
            }
            (root / "SESSION_STATE.json").write_text(json.dumps(legacy_state), encoding="utf-8")
            code, output = self.run_cli(root, "check", "--model", "codex")
            self.assertEqual(code, 0)
            self.assertIn("CURRENT STAGE: planning", output)


if __name__ == "__main__":
    unittest.main()
