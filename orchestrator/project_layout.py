from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orchestrator.config import (
    AGENTS_FILENAME,
    CLAUDE_FILENAME,
    CONFIG_FILENAME,
    CURRENT_TASK_FILENAME,
    DEFAULT_RUNTIME_DIRNAME,
    GEMINI_FILENAME,
    HANDOFF_FILENAME,
    REPAIR_PROMPT_FILENAME,
    RUNTIME_FILENAMES,
    STATE_FILENAME,
    TASK_LOG_FILENAME,
    TRAJECTORY_FILENAME,
)

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    tomllib = None


@dataclass(frozen=True)
class ProjectConfig:
    version: int = 1
    runtime_dir: str = DEFAULT_RUNTIME_DIRNAME
    agents_path: str = AGENTS_FILENAME
    claude_path: str = CLAUDE_FILENAME
    gemini_path: str = GEMINI_FILENAME


class ProjectConfigManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / CONFIG_FILENAME

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> ProjectConfig:
        if not self.exists():
            return ProjectConfig()

        raw = self.path.read_text(encoding="utf-8")
        data = _parse_toml(raw)
        runtime = data.get("runtime", {})
        instructions = data.get("instructions", {})
        return ProjectConfig(
            version=int(data.get("version", 1)),
            runtime_dir=str(runtime.get("directory", DEFAULT_RUNTIME_DIRNAME)),
            agents_path=str(instructions.get("agents", AGENTS_FILENAME)),
            claude_path=str(instructions.get("claude", CLAUDE_FILENAME)),
            gemini_path=str(instructions.get("gemini", GEMINI_FILENAME)),
        )

    def write_if_missing(self, config: ProjectConfig | None = None) -> None:
        if self.exists():
            return
        self.path.write_text(self.dumps(config or ProjectConfig()), encoding="utf-8")

    def dumps(self, config: ProjectConfig) -> str:
        return (
            f'version = {config.version}\n\n'
            "[runtime]\n"
            f'directory = "{config.runtime_dir}"\n\n'
            "[instructions]\n"
            f'agents = "{config.agents_path}"\n'
            f'claude = "{config.claude_path}"\n'
            f'gemini = "{config.gemini_path}"\n'
        )


class ProjectLayout:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.config_manager = ProjectConfigManager(root)
        self.config = self.config_manager.load()
        self.runtime_dir = root / self.config.runtime_dir
        self.runtime_mode = self._detect_runtime_mode()

    def _detect_runtime_mode(self) -> str:
        if self.config_manager.exists() or self.runtime_dir.exists():
            return "managed"
        if any((self.root / name).exists() for name in RUNTIME_FILENAMES):
            return "legacy"
        return "managed"

    def activate_managed_layout(self) -> None:
        self.config_manager.write_if_missing(self.config)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_mode = "managed"

    @property
    def config_path(self) -> Path:
        return self.config_manager.path

    @property
    def agents_path(self) -> Path:
        return self.root / self.config.agents_path

    @property
    def claude_path(self) -> Path:
        return self.root / self.config.claude_path

    @property
    def gemini_path(self) -> Path:
        return self.root / self.config.gemini_path

    @property
    def state_path(self) -> Path:
        return self._runtime_path(STATE_FILENAME)

    @property
    def current_task_path(self) -> Path:
        return self._runtime_path(CURRENT_TASK_FILENAME)

    @property
    def task_log_path(self) -> Path:
        return self._runtime_path(TASK_LOG_FILENAME)

    @property
    def handoff_path(self) -> Path:
        return self._runtime_path(HANDOFF_FILENAME)

    @property
    def trajectory_path(self) -> Path:
        return self._runtime_path(TRAJECTORY_FILENAME)

    @property
    def repair_prompt_path(self) -> Path:
        return self._runtime_path(REPAIR_PROMPT_FILENAME)

    def is_runtime_artifact(self, relative_path: str) -> bool:
        normalized = relative_path.replace("\\", "/").lstrip("./")
        runtime_prefix = f"{self.config.runtime_dir.strip('/')}/"
        if normalized.startswith(runtime_prefix):
            return True
        return normalized in RUNTIME_FILENAMES

    def _runtime_path(self, filename: str) -> Path:
        if self.runtime_mode == "legacy":
            return self.root / filename
        return self.runtime_dir / filename


def _parse_toml(raw: str) -> dict[str, Any]:
    if tomllib is not None:
        return tomllib.loads(raw)
    return _parse_toml_fallback(raw)


def _parse_toml_fallback(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current = data
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section_name = stripped[1:-1].strip()
            current = data.setdefault(section_name, {})
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            parsed: Any = value[1:-1]
        else:
            parsed = int(value)
        current[key] = parsed
    return data
