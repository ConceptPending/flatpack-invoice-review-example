from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, computed_field


class LifecycleEventResponse(BaseModel):
    id: UUID
    occurred_at: datetime
    entity_type: str
    entity_id: UUID
    action: str
    transition_control_id: str
    previous_state: str
    new_state: str
    outcome: str
    actor_id: UUID | None
    actor_roles: list[str]
    spec_name: str
    spec_version: int
    spec_digest: str
    entity_version_before: int
    entity_version_after: int
    request_id: str | None
    guard_results: list[dict[str, Any]]
    invariant_results: list[dict[str, Any]]

    model_config = {"from_attributes": True}

    @computed_field  # a one-line human summary for the viewer
    @property
    def summary(self) -> str:
        who = self.actor_id or "system"
        return (
            f"{self.action} ({self.previous_state}→{self.new_state}) by {who} "
            f"under {self.spec_name} v{self.spec_version} "
            f"[{self.spec_digest[:12]}…]"
        )
