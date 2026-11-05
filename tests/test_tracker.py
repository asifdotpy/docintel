"""Tracker integrity checks for docintel."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "board.json"
VALID_STATUSES = {"pending", "ready", "in_progress", "blocked", "done"}


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(BOARD.read_text())
        self.tasks = self.data["tasks"]
        self.ids = [t["id"] for t in self.tasks]

    def test_unique_ids(self):
        self.assertEqual(len(self.ids), len(set(self.ids)))

    def test_statuses_valid(self):
        for t in self.tasks:
            self.assertIn(t["status"], VALID_STATUSES, t["id"])

    def test_dependencies_exist(self):
        known = set(self.ids)
        for t in self.tasks:
            for dep in t.get("depends_on", []):
                self.assertIn(dep, known, f"{t['id']} -> {dep}")

    def test_briefs_exist(self):
        for t in self.tasks:
            brief = ROOT / t["brief"]
            self.assertTrue(brief.is_file(), f"missing brief: {brief}")

    def test_owns_nonempty(self):
        for t in self.tasks:
            self.assertTrue(t.get("owns"), f"{t['id']} has no owns")

    def test_estimate_nonnegative(self):
        for t in self.tasks:
            self.assertGreaterEqual(t.get("estimate_min", 0), 0)

    def test_contracts_exist(self):
        for name in ("AGENTS.md", "README.md", "NOW.md"):
            self.assertTrue((ROOT / name).is_file(), name)
        for name in ("BRIEF.md", "PACKAGES.md", "DECISIONS.md", "ACCEPTANCE.md"):
            self.assertTrue((ROOT / "docs" / name).is_file(), name)

    def test_promotion_consistency(self):
        # A pending task whose deps are all done should be ready or done/in_progress/blocked.
        done = {t["id"] for t in self.tasks if t["status"] == "done"}
        for t in self.tasks:
            if t["status"] == "pending" and all(dep in done for dep in t.get("depends_on", [])):
                self.fail(f"{t['id']} should have been promoted to ready")

    def test_now_md_has_next(self):
        now = (ROOT / "NOW.md").read_text()
        self.assertIn("## Next", now)


if __name__ == "__main__":
    unittest.main()
