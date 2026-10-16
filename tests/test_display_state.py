"""Protocol state checks only; no hardware or pygame display is exercised."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "display"))
from display_app import DisplayState, DEFAULT_ITEMS, load_catalog


class DisplayStateTests(unittest.TestCase):
    def setUp(self):
        self.state = DisplayState(load_catalog(DEFAULT_ITEMS))
        self.event = dict(event="DISPLAY_COMMIT", item_id="part-1", key="red_cylinder", drop_ok=True)

    def assert_rejected_without_commit(self, event):
        before = (self.state.success_count, copy.deepcopy(self.state.current), set(self.state.accepted_ids))
        self.assertFalse(self.state.commit(event))
        self.assertEqual(before, (self.state.success_count, self.state.current, self.state.accepted_ids))

    def test_only_confirmed_unique_event_increments(self):
        self.assertTrue(self.state.commit(self.event))
        self.assertEqual(self.state.current["sequence"], 1)
        self.assert_rejected_without_commit(dict(self.event, count=2))
        self.assertEqual(self.state.success_count, 1)
        self.assertTrue(self.state.commit(dict(self.event, item_id="part-2", count=2)))

    def test_jump_and_stale_count_do_not_consume_id(self):
        self.assert_rejected_without_commit(dict(self.event, count=1000))
        self.assert_rejected_without_commit(dict(self.event, count=0))
        self.assertTrue(self.state.commit(dict(self.event, count=1)))

    def test_count_must_be_exact_integer(self):
        for count in (True, False, 1.0, "1", None, -1):
            with self.subTest(count=count):
                self.assert_rejected_without_commit(dict(self.event, count=count))

    def test_drop_assertion_must_be_true_boolean(self):
        for flag in (False, 1, "true", None):
            with self.subTest(flag=flag):
                self.assert_rejected_without_commit(dict(self.event, drop_ok=flag))

    def test_item_id_must_be_nonempty_string(self):
        for item_id in (None, 1, True, [], {}, "", "   "):
            with self.subTest(item_id=item_id):
                self.assert_rejected_without_commit(dict(self.event, item_id=item_id))

    def test_unknown_class_and_incomplete_display_are_rejected(self):
        self.assert_rejected_without_commit(dict(self.event, key="unknown"))
        self.assert_rejected_without_commit(dict(self.event, name="   "))
        self.assert_rejected_without_commit(dict(self.event, category="   "))
        self.assert_rejected_without_commit(dict(self.event, image="no-such-image.png"))

    def test_box_must_be_configured_range_integer(self):
        for box_id in (0, 7, True, "1", 1.0):
            with self.subTest(box_id=box_id):
                self.assert_rejected_without_commit(dict(self.event, box_id=box_id))

    def test_restart_does_not_claim_automatic_recovery(self):
        self.assertTrue(self.state.commit(dict(self.event, count=1)))
        restarted = DisplayState(self.state.catalog)
        self.assertFalse(restarted.commit(dict(self.event, item_id="part-2", count=2)))
        self.assertEqual(restarted.success_count, 0)


if __name__ == "__main__":
    unittest.main()
