"""Read-only schemas for exposing a lifecycle spec as data — drives the
`GET /lifecycle` endpoint and any future front-end lifecycle viewer.

Shared by every lifecycle slice so the response shape is defined once."""

from typing import Any

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
