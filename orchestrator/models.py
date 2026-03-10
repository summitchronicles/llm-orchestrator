from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VerificationStepResult:
    name: str
    command: str
    status: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    reason: str = ""
    started_at: str = field(default_factory=utc_now)
    finished_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "status": self.status,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "reason": self.reason,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class SessionState:
    task_id: str = "default-task"
    goal: str = "Define the current development goal."
    project_type: str = "greenfield"
    constraints: list[str] = field(default_factory=list)
    current_stage: str = "planning"
    current_owner: str = "codex"
    active_model: str | None = None
    last_milestone: str | None = None
    next_stage: str | None = "backend"
    verification_status: str = "not_run"
    workspace: str | None = None
    workspace_branch: str | None = None
    handoff_summary: str = ""
    open_risks: list[str] = field(default_factory=list)
    recent_changes: list[str] = field(default_factory=list)
    related_tests: list[str] = field(default_factory=list)
    last_verification: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        return cls(
            task_id=data.get("task_id", "default-task"),
            goal=data.get("goal", "Define the current development goal."),
            project_type=data.get("project_type", "greenfield"),
            constraints=list(data.get("constraints") or []),
            current_stage=data.get("current_stage", "planning"),
            current_owner=data.get("current_owner", "codex"),
            active_model=data.get("active_model"),
            last_milestone=data.get("last_milestone"),
            next_stage=data.get("next_stage"),
            verification_status=data.get("verification_status", "not_run"),
            workspace=data.get("workspace"),
            workspace_branch=data.get("workspace_branch"),
            handoff_summary=data.get("handoff_summary", ""),
            open_risks=list(data.get("open_risks") or []),
            recent_changes=list(data.get("recent_changes") or []),
            related_tests=list(data.get("related_tests") or []),
            last_verification=dict(data.get("last_verification") or {}),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "project_type": self.project_type,
            "constraints": self.constraints,
            "current_stage": self.current_stage,
            "current_owner": self.current_owner,
            "active_model": self.active_model,
            "last_milestone": self.last_milestone,
            "next_stage": self.next_stage,
            "verification_status": self.verification_status,
            "workspace": self.workspace,
            "workspace_branch": self.workspace_branch,
            "handoff_summary": self.handoff_summary,
            "open_risks": self.open_risks,
            "recent_changes": self.recent_changes,
            "related_tests": self.related_tests,
            "last_verification": self.last_verification,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def touch(self) -> None:
        self.updated_at = utc_now()
