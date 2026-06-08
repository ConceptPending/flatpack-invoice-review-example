"""Read-only schemas for exposing a lifecycle spec as data — drives the
`GET /lifecycle` endpoint and any future front-end lifecycle viewer.

Shared by every lifecycle slice so the response shape is defined once."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TransitionInfo(BaseModel):
    name: str
    label: str
    from_: list[str] = Field(alias="from")
    to: str
    roles: list[str]
    # The guard condition as a structured expression tree (for tooling/diff)
    # and as rendered text (for humans). Null when the transition is unguarded.
    guard: dict[str, Any] | None
    guard_text: str | None

    model_config = {"populate_by_name": True}


class StateInfo(BaseModel):
    id: str
    description: str


class FieldInfo(BaseModel):
    name: str
    type: str


class InvariantInfo(BaseModel):
    name: str
    label: str
    text: str
    condition: dict[str, Any]


class LifecycleSpecResponse(BaseModel):
    name: str
    title: str
    version: int
    digest: str
    initial: str
    terminal: list[str]
    states: list[StateInfo]
    fields: list[FieldInfo]
    transitions: list[TransitionInfo]
    invariants: list[InvariantInfo]


# --- Case simulator: what's allowed right now, and why ----------------------


class AvailableAction(BaseModel):
    action: str
    control_id: str
    to: str
    allowed: bool
    reason: str  # "ok", or why the transition is refused


class AvailableActionsResponse(BaseModel):
    batch_id: UUID
    status: str
    version: int          # the entity's optimistic-lock version
    spec_version: int     # the policy version in force
    spec_digest: str
    actions: list[AvailableAction]
