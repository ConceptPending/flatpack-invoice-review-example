"""The application's role vocabulary — who-can-be-what.

Roles are held per-user (`User.roles`) and referenced by lifecycle specs (see
`app/statespec/batch_spec.py`) to gate transitions. `is_admin` and roles are
orthogonal: `is_admin` gates the admin area at all; roles say which lifecycle
actions an admin may perform (an admin can hold zero roles).

Stored on the row as a sorted, comma-separated string so the column is portable
across SQLite (tests) and Postgres (prod) without array/JSON types.
"""

from __future__ import annotations

from collections.abc import Iterable

# Batch review roles. Separation of duties: a reviewer can triage/reject, but
# only an approver can approve a batch for downstream processing.
REVIEWER = "reviewer"
APPROVER = "approver"

# Roles a human user can be granted (bootstrap admin + role-assignment draw
# from this). ALL_ROLES is the full engine vocabulary; kept distinct so future
# synthetic actors (e.g. a SYSTEM role for scheduled jobs) can exist in the
# engine without becoming human-grantable.
HUMAN_ROLES: frozenset[str] = frozenset({REVIEWER, APPROVER})
ALL_ROLES: frozenset[str] = HUMAN_ROLES


def parse_roles(raw: str | None) -> frozenset[str]:
    """CSV string -> set of roles. Tolerant of whitespace, blanks, and None."""
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def format_roles(roles: Iterable[str]) -> str:
    """Set of roles -> canonical sorted CSV string for storage."""
    return ",".join(sorted(set(roles)))


def unknown_roles(roles: Iterable[str]) -> set[str]:
    """Roles the engine doesn't recognise (spec-level validation)."""
    return set(roles) - ALL_ROLES
