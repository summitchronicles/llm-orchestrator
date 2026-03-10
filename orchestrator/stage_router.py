from __future__ import annotations

from orchestrator.config import STAGE_MODEL_OWNERS, STAGE_SEQUENCE
from orchestrator.models import SessionState


class StageRouter:
    def recommended_owner(self, stage: str) -> str:
        if stage not in STAGE_MODEL_OWNERS:
            raise ValueError(f"Unknown stage: {stage}")
        return STAGE_MODEL_OWNERS[stage]

    def next_stage(self, stage: str) -> str | None:
        if stage not in STAGE_SEQUENCE:
            raise ValueError(f"Unknown stage: {stage}")
        index = STAGE_SEQUENCE.index(stage)
        if index == len(STAGE_SEQUENCE) - 1:
            return None
        return STAGE_SEQUENCE[index + 1]

    def sync_state(self, state: SessionState) -> SessionState:
        state.current_owner = self.recommended_owner(state.current_stage)
        state.next_stage = self.next_stage(state.current_stage)
        state.touch()
        return state

    def should_advance(self, milestone_text: str, force_advance: bool = False) -> bool:
        if force_advance:
            return True
        normalized = milestone_text.strip().lower()
        markers = ("complete", "completed", "done", "finished", "ready for handoff")
        return any(marker in normalized for marker in markers)

    def advance(self, state: SessionState) -> SessionState:
        next_stage = self.next_stage(state.current_stage)
        if next_stage is None:
            state.current_stage = "complete"
        else:
            state.current_stage = next_stage
        return self.sync_state(state)

    def decision(self, model: str, state: SessionState) -> dict[str, str]:
        recommended = self.recommended_owner(state.current_stage)
        if state.current_stage == "complete":
            decision = "manual"
            reason = "The workflow is complete and awaits human review."
        elif model == recommended:
            decision = "stay"
            reason = "The requested model matches the current stage owner."
        else:
            decision = "switch"
            reason = "The requested model does not match the current stage owner."
        return {
            "current_stage": state.current_stage,
            "owner": recommended,
            "current_model": model,
            "decision": decision,
            "reason": reason,
        }
