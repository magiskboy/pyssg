"""Exhaustive unit tests for ``coalesce``.

``coalesce`` is a pure function (no IO, no clock), so every merge rule and the
order-preservation guarantee can be asserted directly.
"""

from __future__ import annotations

import unittest

from pyssg.watch import FsEvent, coalesce


class CoalesceTest(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(coalesce([]), [])

    def test_multiple_modify_collapse_to_one(self) -> None:
        events = [FsEvent("modify", "a.md"), FsEvent("modify", "a.md"), FsEvent("modify", "a.md")]
        self.assertEqual(coalesce(events), [FsEvent("modify", "a.md")])

    def test_add_then_modify_stays_add(self) -> None:
        events = [FsEvent("add", "a.md"), FsEvent("modify", "a.md")]
        self.assertEqual(coalesce(events), [FsEvent("add", "a.md")])

    def test_add_then_multiple_modify_stays_add(self) -> None:
        events = [FsEvent("add", "a.md"), FsEvent("modify", "a.md"), FsEvent("modify", "a.md")]
        self.assertEqual(coalesce(events), [FsEvent("add", "a.md")])

    def test_modify_then_delete_becomes_delete(self) -> None:
        events = [FsEvent("modify", "a.md"), FsEvent("delete", "a.md")]
        self.assertEqual(coalesce(events), [FsEvent("delete", "a.md")])

    def test_add_then_delete_drops_entirely(self) -> None:
        events = [FsEvent("add", "a.md"), FsEvent("delete", "a.md")]
        self.assertEqual(coalesce(events), [])

    def test_add_modify_delete_drops_entirely(self) -> None:
        events = [FsEvent("add", "a.md"), FsEvent("modify", "a.md"), FsEvent("delete", "a.md")]
        self.assertEqual(coalesce(events), [])

    def test_delete_then_add_becomes_modify(self) -> None:
        """Documented extension: a file replaced in place reads as a modify."""
        events = [FsEvent("delete", "a.md"), FsEvent("add", "a.md")]
        self.assertEqual(coalesce(events), [FsEvent("modify", "a.md")])

    def test_delete_add_modify_becomes_modify(self) -> None:
        events = [FsEvent("delete", "a.md"), FsEvent("add", "a.md"), FsEvent("modify", "a.md")]
        self.assertEqual(coalesce(events), [FsEvent("modify", "a.md")])

    def test_move_is_preserved_verbatim(self) -> None:
        events = [FsEvent("move", "old.md", "new.md")]
        self.assertEqual(coalesce(events), [FsEvent("move", "old.md", "new.md")])

    def test_distinct_moves_are_not_merged(self) -> None:
        events = [
            FsEvent("move", "a.md", "b.md"),
            FsEvent("move", "c.md", "d.md"),
        ]
        self.assertEqual(coalesce(events), events)

    def test_duplicate_move_collapses(self) -> None:
        events = [FsEvent("move", "a.md", "b.md"), FsEvent("move", "a.md", "b.md")]
        self.assertEqual(coalesce(events), [FsEvent("move", "a.md", "b.md")])

    def test_move_source_and_dest_are_independent_keys(self) -> None:
        """A modify on the move destination is tracked separately from the move."""
        events = [FsEvent("move", "a.md", "b.md"), FsEvent("modify", "b.md")]
        self.assertEqual(
            coalesce(events), [FsEvent("move", "a.md", "b.md"), FsEvent("modify", "b.md")]
        )

    def test_order_preserved_by_first_appearance(self) -> None:
        events = [
            FsEvent("modify", "c.md"),
            FsEvent("add", "a.md"),
            FsEvent("modify", "b.md"),
            FsEvent("modify", "a.md"),  # later touch of a.md must not reorder it
            FsEvent("modify", "c.md"),
        ]
        self.assertEqual(
            coalesce(events),
            [
                FsEvent("modify", "c.md"),
                FsEvent("add", "a.md"),
                FsEvent("modify", "b.md"),
            ],
        )

    def test_dropped_path_does_not_reserve_slot_when_no_reappearance(self) -> None:
        events = [
            FsEvent("add", "gone.md"),
            FsEvent("delete", "gone.md"),
            FsEvent("modify", "x.md"),
        ]
        self.assertEqual(coalesce(events), [FsEvent("modify", "x.md")])

    def test_dropped_then_recreated_path_reuses_first_slot_and_emits(self) -> None:
        """add+delete cancels, then a fresh add later re-establishes the file."""
        events = [
            FsEvent("add", "a.md"),
            FsEvent("delete", "a.md"),
            FsEvent("modify", "b.md"),
            FsEvent("add", "a.md"),
        ]
        # ``a.md`` first appeared before ``b.md``, so it keeps the earlier slot.
        self.assertEqual(coalesce(events), [FsEvent("add", "a.md"), FsEvent("modify", "b.md")])

    def test_mixed_burst(self) -> None:
        events = [
            FsEvent("add", "new.md"),
            FsEvent("modify", "new.md"),
            FsEvent("modify", "edited.md"),
            FsEvent("modify", "edited.md"),
            FsEvent("move", "old.md", "renamed.md"),
            FsEvent("modify", "doomed.md"),
            FsEvent("delete", "doomed.md"),
            FsEvent("add", "flicker.md"),
            FsEvent("delete", "flicker.md"),
        ]
        self.assertEqual(
            coalesce(events),
            [
                FsEvent("add", "new.md"),
                FsEvent("modify", "edited.md"),
                FsEvent("move", "old.md", "renamed.md"),
                FsEvent("delete", "doomed.md"),
            ],
        )

    def test_coalesce_does_not_mutate_input(self) -> None:
        events = [FsEvent("add", "a.md"), FsEvent("modify", "a.md")]
        snapshot = list(events)
        coalesce(events)
        self.assertEqual(events, snapshot)
