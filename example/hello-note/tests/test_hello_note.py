"""入库笔记的判断逻辑：不启动 MovieClaw。"""

from __future__ import annotations

import unittest

from hello_note import remember, should_note


class ShouldNoteTest(unittest.TestCase):
    def test_disabled(self) -> None:
        self.assertFalse(should_note("沙丘", enabled=False, prefix=""))
        self.assertFalse(should_note("沙丘", enabled=False, prefix="沙"))

    def test_empty_prefix_matches_everything(self) -> None:
        self.assertTrue(should_note("沙丘", enabled=True, prefix=""))
        self.assertTrue(should_note("", enabled=True, prefix=""))

    def test_prefix(self) -> None:
        self.assertTrue(should_note("沙丘 2", enabled=True, prefix="沙丘"))
        self.assertFalse(should_note("星际穿越", enabled=True, prefix="沙丘"))


class RememberTest(unittest.TestCase):
    def test_new_event_is_prepended(self) -> None:
        self.assertEqual(remember(["b"], "a"), ["a", "b"])

    def test_duplicate_is_skipped(self) -> None:
        self.assertIsNone(remember(["a", "b"], "a"))

    def test_missing_event_id_cannot_dedupe(self) -> None:
        seen = ["a"]
        self.assertEqual(remember(seen, None), ["a"])
        self.assertEqual(seen, ["a"])

    def test_limit(self) -> None:
        self.assertEqual(remember(["b", "c"], "a", limit=2), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
