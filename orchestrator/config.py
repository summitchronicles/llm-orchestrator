from __future__ import annotations

from pathlib import Path

STAGE_SEQUENCE = [
    "planning",
    "backend",
    "frontend",
    "security",
    "documentation",
    "testing",
    "complete",
]

STAGE_MODEL_OWNERS = {
    "planning": "codex",
    "backend": "codex",
    "frontend": "claude",
    "security": "claude",
    "documentation": "gemini",
    "testing": "gemini",
    "complete": "human",
}

KNOWN_MODELS = ("codex", "claude", "gemini")

CONFIG_FILENAME = "orchestrator.toml"
STATE_FILENAME = "SESSION_STATE.json"
CURRENT_TASK_FILENAME = "CURRENT_TASK.md"
TASK_LOG_FILENAME = "TASK_LOG.md"
HANDOFF_FILENAME = "HANDOFF.md"
TRAJECTORY_FILENAME = "trajectory.jsonl"
REPAIR_PROMPT_FILENAME = "REPAIR_PROMPT.md"
AGENTS_FILENAME = "AGENTS.md"
CLAUDE_FILENAME = "CLAUDE.md"
GEMINI_FILENAME = "GEMINI.md"

DEFAULT_RUNTIME_DIRNAME = ".orchestrator"
WORKSPACES_DIRNAME = ".workspaces"

CONTEXT_FILE_LIMIT = 8
CONTEXT_SNIPPET_BYTES = 4_000

RUNTIME_FILENAMES = (
    STATE_FILENAME,
    CURRENT_TASK_FILENAME,
    TASK_LOG_FILENAME,
    HANDOFF_FILENAME,
    TRAJECTORY_FILENAME,
    REPAIR_PROMPT_FILENAME,
)


def project_path(root: Path, filename: str) -> Path:
    return root / filename
