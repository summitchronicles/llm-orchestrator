from __future__ import annotations

from pathlib import Path

from orchestrator.models import SessionState
from orchestrator.project_layout import ProjectLayout
from orchestrator.templates import render_repair_prompt


class RepairLoop:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = ProjectLayout(root).repair_prompt_path

    def generate(self, state: SessionState) -> dict[str, str]:
        verification = state.last_verification
        if not verification:
            raise RuntimeError("No verification run is recorded. Run `orchestrator verify` first.")

        failed_steps = [
            step["name"]
            for step in verification.get("steps", [])
            if step.get("status") == "failed"
        ]
        if not failed_steps:
            raise RuntimeError("The latest verification run did not fail, so no repair prompt is needed.")

        notes = []
        for step in verification.get("steps", []):
            if step.get("status") != "failed":
                continue
            stderr = (step.get("stderr") or "").strip()
            stdout = (step.get("stdout") or "").strip()
            excerpt = stderr or stdout
            if excerpt:
                notes.append(f"{step['name']}: {excerpt.splitlines()[0]}")

        summary = verification.get("summary", "Verification failed.")
        prompt = render_repair_prompt(summary, failed_steps, notes)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(prompt, encoding="utf-8")
        return {"summary": summary, "prompt": prompt}
