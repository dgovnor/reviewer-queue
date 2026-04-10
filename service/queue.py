from __future__ import annotations

from copy import deepcopy
from typing import Iterable

STATUS_UNASSIGNED = "unassigned"
STATUS_IN_REVIEW = "in_review"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_ESCALATED = "escalated"

TERMINAL_STATUSES = frozenset({STATUS_APPROVED, STATUS_REJECTED, STATUS_ESCALATED})
ACTIVE_STATUSES = frozenset({STATUS_UNASSIGNED, STATUS_IN_REVIEW})

ACTION_CLAIM = "claim"
ACTION_APPROVE = "approve"
ACTION_REJECT = "reject"
ACTION_ESCALATE = "escalate"
VALID_ACTIONS = frozenset(
    {ACTION_CLAIM, ACTION_APPROVE, ACTION_REJECT, ACTION_ESCALATE}
)

_RISK_RANK = {"high": 0, "medium": 1, "low": 2}
_TIER_RANK = {"priority": 0, "standard": 1}


class WorkflowError(Exception):
    """Raised when an action is not allowed for the given item state."""


def active_queue(items: Iterable[dict]) -> list[dict]:
    """Return non-terminal items sorted by urgency."""
    active = [item for item in items if item["status"] not in TERMINAL_STATUSES]
    active.sort(key=_urgency_key)
    return active


def _urgency_key(item: dict) -> tuple:
    return (
        _RISK_RANK.get(item["risk_level"], 99),
        _TIER_RANK.get(item["customer_tier"], 99),
        item["submitted_at"],
    )


def allowed_actions(item: dict) -> list[str]:
    status = item["status"]
    if status == STATUS_UNASSIGNED:
        return [ACTION_CLAIM]
    if status == STATUS_IN_REVIEW:
        return [ACTION_APPROVE, ACTION_REJECT, ACTION_ESCALATE]
    return []


def apply_action(item: dict, action: str, reviewer: str) -> dict:
    """Return a new item with the action applied, or raise WorkflowError."""
    if action not in VALID_ACTIONS:
        raise WorkflowError(f"Unknown action '{action}'.")

    status = item["status"]
    updated = deepcopy(item)

    if action == ACTION_CLAIM:
        if status != STATUS_UNASSIGNED:
            raise WorkflowError(
                f"Cannot claim item in status '{status}'. Only unassigned items can be claimed."
            )
        updated["status"] = STATUS_IN_REVIEW
        updated["assigned_reviewer"] = reviewer
        return updated

    # approve / reject / escalate
    if status != STATUS_IN_REVIEW:
        raise WorkflowError(
            f"Cannot {action} item in status '{status}'. "
            "Only items currently in_review can be approved, rejected, or escalated."
        )

    terminal_for = {
        ACTION_APPROVE: STATUS_APPROVED,
        ACTION_REJECT: STATUS_REJECTED,
        ACTION_ESCALATE: STATUS_ESCALATED,
    }
    updated["status"] = terminal_for[action]
    return updated
