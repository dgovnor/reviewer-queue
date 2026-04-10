"""Unit tests for the reviewer queue state machine and sorting.

Run with:
    .venv/bin/python -m unittest discover -s tests
"""

from __future__ import annotations

import unittest

from service.queue import (
    ACTION_APPROVE,
    ACTION_CLAIM,
    ACTION_ESCALATE,
    ACTION_REJECT,
    STATUS_APPROVED,
    STATUS_ESCALATED,
    STATUS_IN_REVIEW,
    STATUS_REJECTED,
    STATUS_UNASSIGNED,
    WorkflowError,
    active_queue,
    allowed_actions,
    apply_action,
)


def make_item(**overrides):
    base = {
        "id": "RV-1",
        "title": "Test item",
        "submitted_at": "2026-04-01T00:00:00Z",
        "risk_level": "medium",
        "customer_tier": "standard",
        "status": STATUS_UNASSIGNED,
        "assigned_reviewer": None,
        "notes_count": 0,
        "summary": "…",
    }
    base.update(overrides)
    return base


class TestActiveQueue(unittest.TestCase):
    def test_excludes_terminal_items(self):
        items = [
            make_item(id="A", status=STATUS_UNASSIGNED),
            make_item(id="B", status=STATUS_IN_REVIEW),
            make_item(id="C", status=STATUS_APPROVED),
            make_item(id="D", status=STATUS_REJECTED),
            make_item(id="E", status=STATUS_ESCALATED),
        ]
        ids = [item["id"] for item in active_queue(items)]
        self.assertEqual(set(ids), {"A", "B"})

    def test_sorts_high_risk_first(self):
        items = [
            make_item(id="LOW", risk_level="low"),
            make_item(id="HIGH", risk_level="high"),
            make_item(id="MED", risk_level="medium"),
        ]
        order = [item["id"] for item in active_queue(items)]
        self.assertEqual(order, ["HIGH", "MED", "LOW"])

    def test_priority_customers_outrank_standard_within_same_risk(self):
        items = [
            make_item(id="STD", risk_level="high", customer_tier="standard"),
            make_item(id="PRI", risk_level="high", customer_tier="priority"),
        ]
        order = [item["id"] for item in active_queue(items)]
        self.assertEqual(order, ["PRI", "STD"])

    def test_older_items_outrank_newer_within_same_bucket(self):
        items = [
            make_item(id="NEW", submitted_at="2026-04-05T00:00:00Z"),
            make_item(id="OLD", submitted_at="2026-04-01T00:00:00Z"),
        ]
        order = [item["id"] for item in active_queue(items)]
        self.assertEqual(order, ["OLD", "NEW"])

    def test_full_ordering_applies_all_three_rules(self):
        items = [
            make_item(id="A", risk_level="low", customer_tier="priority",
                      submitted_at="2026-03-01T00:00:00Z"),
            make_item(id="B", risk_level="high", customer_tier="standard",
                      submitted_at="2026-04-02T00:00:00Z"),
            make_item(id="C", risk_level="high", customer_tier="priority",
                      submitted_at="2026-04-03T00:00:00Z"),
            make_item(id="D", risk_level="medium", customer_tier="priority",
                      submitted_at="2026-04-01T00:00:00Z"),
        ]
        order = [item["id"] for item in active_queue(items)]
        # C (high/priority) > B (high/standard) > D (medium/priority) > A (low/priority)
        self.assertEqual(order, ["C", "B", "D", "A"])


class TestClaim(unittest.TestCase):
    def test_claim_unassigned_succeeds(self):
        item = make_item(status=STATUS_UNASSIGNED)
        updated = apply_action(item, ACTION_CLAIM, reviewer="alex")
        self.assertEqual(updated["status"], STATUS_IN_REVIEW)
        self.assertEqual(updated["assigned_reviewer"], "alex")

    def test_claim_does_not_mutate_original(self):
        item = make_item(status=STATUS_UNASSIGNED)
        apply_action(item, ACTION_CLAIM, reviewer="alex")
        self.assertEqual(item["status"], STATUS_UNASSIGNED)
        self.assertIsNone(item["assigned_reviewer"])

    def test_cannot_claim_in_review_item(self):
        item = make_item(status=STATUS_IN_REVIEW, assigned_reviewer="sam")
        with self.assertRaises(WorkflowError):
            apply_action(item, ACTION_CLAIM, reviewer="alex")

    def test_cannot_claim_terminal_item(self):
        for status in (STATUS_APPROVED, STATUS_REJECTED, STATUS_ESCALATED):
            with self.subTest(status=status):
                item = make_item(status=status)
                with self.assertRaises(WorkflowError):
                    apply_action(item, ACTION_CLAIM, reviewer="alex")


class TestTerminalTransitions(unittest.TestCase):
    def test_approve_in_review(self):
        item = make_item(status=STATUS_IN_REVIEW, assigned_reviewer="alex")
        updated = apply_action(item, ACTION_APPROVE, reviewer="alex")
        self.assertEqual(updated["status"], STATUS_APPROVED)

    def test_reject_in_review(self):
        item = make_item(status=STATUS_IN_REVIEW, assigned_reviewer="alex")
        updated = apply_action(item, ACTION_REJECT, reviewer="alex")
        self.assertEqual(updated["status"], STATUS_REJECTED)

    def test_escalate_in_review(self):
        item = make_item(status=STATUS_IN_REVIEW, assigned_reviewer="alex")
        updated = apply_action(item, ACTION_ESCALATE, reviewer="alex")
        self.assertEqual(updated["status"], STATUS_ESCALATED)

    def test_cannot_approve_unassigned(self):
        item = make_item(status=STATUS_UNASSIGNED)
        with self.assertRaises(WorkflowError):
            apply_action(item, ACTION_APPROVE, reviewer="alex")

    def test_cannot_re_transition_terminal_item(self):
        for status in (STATUS_APPROVED, STATUS_REJECTED, STATUS_ESCALATED):
            for action in (ACTION_APPROVE, ACTION_REJECT, ACTION_ESCALATE):
                with self.subTest(status=status, action=action):
                    item = make_item(status=status, assigned_reviewer="alex")
                    with self.assertRaises(WorkflowError):
                        apply_action(item, action, reviewer="alex")

    def test_unknown_action_raises(self):
        item = make_item(status=STATUS_IN_REVIEW, assigned_reviewer="alex")
        with self.assertRaises(WorkflowError):
            apply_action(item, "delete", reviewer="alex")


class TestAllowedActions(unittest.TestCase):
    def test_unassigned_allows_only_claim(self):
        item = make_item(status=STATUS_UNASSIGNED)
        self.assertEqual(allowed_actions(item), [ACTION_CLAIM])

    def test_in_review_allows_terminal_transitions(self):
        item = make_item(status=STATUS_IN_REVIEW, assigned_reviewer="alex")
        self.assertEqual(
            set(allowed_actions(item)),
            {ACTION_APPROVE, ACTION_REJECT, ACTION_ESCALATE},
        )

    def test_terminal_allows_nothing(self):
        for status in (STATUS_APPROVED, STATUS_REJECTED, STATUS_ESCALATED):
            with self.subTest(status=status):
                item = make_item(status=status)
                self.assertEqual(allowed_actions(item), [])


if __name__ == "__main__":
    unittest.main()
