from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from orchestrator.models import VerificationStepResult, utc_now

COMMAND_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class CommandPlan:
    name: str
    command: list[str] | None
    reason: str = ""


class VerificationRunner:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run_all(self) -> dict[str, object]:
        return self._run_plans(self.detect_plan())

    def run_named_steps(self, step_prefixes: list[str]) -> dict[str, object]:
        selected = [
            plan
            for plan in self.detect_plan()
            if any(plan.name == prefix or plan.name.startswith(f"{prefix}:") for prefix in step_prefixes)
        ]
        return self._run_plans(selected)

    def detect_plan(self) -> list[CommandPlan]:
        plan: list[CommandPlan] = []
        has_package_json = (self.root / "package.json").exists()
        has_python = any(
            (self.root / candidate).exists()
            for candidate in ("pyproject.toml", "setup.py", "requirements.txt", "orchestrator")
        )
        has_tests_dir = (self.root / "tests").exists()

        if has_package_json:
            if shutil.which("npm"):
                plan.extend(
                    [
                        CommandPlan("build:npm", ["npm", "run", "build", "--if-present"]),
                        CommandPlan("tests:npm", ["npm", "run", "test", "--if-present"]),
                        CommandPlan("lint:npm", ["npm", "run", "lint", "--if-present"]),
                        CommandPlan("typecheck:npm", ["npm", "run", "typecheck", "--if-present"]),
                    ]
                )
            else:
                plan.extend(
                    [
                        CommandPlan("build:npm", None, "npm is not installed."),
                        CommandPlan("tests:npm", None, "npm is not installed."),
                        CommandPlan("lint:npm", None, "npm is not installed."),
                        CommandPlan("typecheck:npm", None, "npm is not installed."),
                    ]
                )

        if has_python:
            python_exec = shutil.which("python3") or shutil.which("python")
            if python_exec:
                compile_targets = [target for target in ("orchestrator", "tests") if (self.root / target).exists()]
                if compile_targets:
                    plan.append(CommandPlan("build:python", [python_exec, "-m", "compileall", *compile_targets]))
                else:
                    plan.append(CommandPlan("build:python", None, "No Python source targets detected."))
            else:
                plan.append(CommandPlan("build:python", None, "Python is not installed."))

            if has_tests_dir:
                if shutil.which("pytest"):
                    plan.append(CommandPlan("tests:pytest", ["pytest", "-q"]))
                elif python_exec:
                    plan.append(
                        CommandPlan(
                            "tests:unittest",
                            [python_exec, "-m", "unittest", "discover", "-s", "tests", "-v"],
                        )
                    )
                else:
                    plan.append(CommandPlan("tests:python", None, "Python is not installed."))
            else:
                plan.append(CommandPlan("tests:python", None, "No tests directory detected."))

            if shutil.which("ruff"):
                plan.append(CommandPlan("lint:ruff", ["ruff", "check", "."]))
            elif shutil.which("flake8"):
                plan.append(CommandPlan("lint:flake8", ["flake8", "."]))
            else:
                plan.append(CommandPlan("lint:python", None, "No Python linter detected."))

            if shutil.which("mypy"):
                targets = [target for target in ("orchestrator", "tests") if (self.root / target).exists()]
                plan.append(CommandPlan("typecheck:mypy", ["mypy", *targets]))
            else:
                plan.append(CommandPlan("typecheck:python", None, "mypy is not installed."))

        semgrep_command = self._semgrep_command()
        if semgrep_command:
            plan.append(CommandPlan("security:semgrep", semgrep_command))
        else:
            plan.append(
                CommandPlan(
                    "security:semgrep",
                    None,
                    "semgrep is not installed or no local semgrep config was found.",
                )
            )

        if shutil.which("trivy"):
            plan.append(
                CommandPlan("security:trivy", ["trivy", "fs", "--skip-db-update", "--offline-scan", "."])
            )
        else:
            plan.append(CommandPlan("security:trivy", None, "trivy is not installed."))

        if shutil.which("gitleaks"):
            plan.append(
                CommandPlan("security:gitleaks", ["gitleaks", "detect", "--no-banner", "--redact"])
            )
        else:
            plan.append(CommandPlan("security:gitleaks", None, "gitleaks is not installed."))

        return plan

    def _semgrep_command(self) -> list[str] | None:
        if not shutil.which("semgrep"):
            return None
        for candidate in (".semgrep.yml", ".semgrep.yaml", "semgrep.yml", "semgrep.yaml"):
            path = self.root / candidate
            if path.exists():
                return ["semgrep", "--config", candidate, "."]
        return None

    def _run_plans(self, plans: list[CommandPlan]) -> dict[str, object]:
        started_at = utc_now()
        results: list[VerificationStepResult] = []
        for plan in plans:
            if plan.command is None:
                results.append(
                    VerificationStepResult(
                        name=plan.name,
                        command="",
                        status="skipped",
                        reason=plan.reason,
                    )
                )
                continue

            step_started = utc_now()
            try:
                process = subprocess.run(
                    plan.command,
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=COMMAND_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired as exc:
                results.append(
                    VerificationStepResult(
                        name=plan.name,
                        command=" ".join(plan.command),
                        status="failed",
                        stdout=exc.stdout or "",
                        stderr=exc.stderr or "",
                        reason=f"Timed out after {COMMAND_TIMEOUT_SECONDS} seconds.",
                        started_at=step_started,
                        finished_at=utc_now(),
                    )
                )
                continue
            results.append(
                VerificationStepResult(
                    name=plan.name,
                    command=" ".join(plan.command),
                    status="passed" if process.returncode == 0 else "failed",
                    returncode=process.returncode,
                    stdout=process.stdout,
                    stderr=process.stderr,
                    started_at=step_started,
                    finished_at=utc_now(),
                )
            )

        statuses = [result.status for result in results]
        failed = statuses.count("failed")
        passed = statuses.count("passed")
        skipped = statuses.count("skipped")
        overall = "failed" if failed else "passed" if passed else "skipped"
        summary = (
            f"Verification {overall}: {passed} passed, {failed} failed, {skipped} skipped."
        )
        return {
            "status": overall,
            "summary": summary,
            "steps": [result.to_dict() for result in results],
            "started_at": started_at,
            "finished_at": utc_now(),
        }
