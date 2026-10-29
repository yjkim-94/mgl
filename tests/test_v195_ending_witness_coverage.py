"""Cross-check 48 ending selection witnesses from v1.8 audit artifacts.

This verifies recorded evidence, not a fresh 48-path simulation.
"""
import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {f"J{i:02}" for i in range(1, 41)} | {f"S{i:02}" for i in range(1, 9)}


def read(name):
    with (ROOT / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class EndingWitnessCoverage(unittest.TestCase):
    def test_all_48_have_recorded_selected_witness(self):
        trials = read("mgl_v18_trials.csv")
        replay = read("mgl_v18_selection_audit.csv")
        selected_trials = {
            r["focus"] for r in trials
            if r["eligible"] == "1" and r["selected"] == r["focus"]
            and r["months"] == "120"
        }
        selected_replay = {
            r["ending"] for r in replay
            if r["eligible"] == "1" and r["selected_matches_target"] == "1"
            and r["selected"] == r["ending"] and r["earth_transfer"] == "1"
        }
        self.assertEqual(len(selected_trials), 26)
        self.assertEqual(len(selected_replay), 22)
        self.assertEqual(selected_trials | selected_replay, EXPECTED)

    def test_replay_earth_transfer_and_no_duplicates(self):
        replay = read("mgl_v18_selection_audit.csv")
        self.assertEqual(len(replay), 44)
        self.assertTrue(all(r["earth_transfer"] == "1" for r in replay))
        self.assertTrue(all(r["selected_matches_target"] == "1" for r in replay))


if __name__ == "__main__":
    unittest.main()
