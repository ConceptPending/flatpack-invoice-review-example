"""Read-only schemas for exposing a lifecycle spec as data — drives the
`GET /lifecycle` endpoint and any future front-end lifecycle viewer."""

from pydantic import BaseModel, Field


class TransitionInfo(BaseModel):
    name: str
    label: str
    from_: list[str] = Field(alias="from")
    to: str
    roles: list[str]
    guard: str | None

    model_config = {"populate_by_name": True}


class StateInfo(BaseModel):
    id: str
    description: str


class InvariantInfo(BaseModel):
    name: str
    label: str


class LifecycleSpecResponse(BaseModel):
    name: str
    title: str
    initial: str
    terminal: list[str]
    states: list[StateInfo]
    transitions: list[TransitionInfo]
    invariants: list[InvariantInfo]
