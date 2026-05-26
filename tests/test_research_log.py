import tempfile
import unittest
from pathlib import Path

from sports_middling.research_log import (
    count_observations,
    fetch_observations,
    make_candidate_hash,
    save_observations,
    update_observation_review,
)


class ResearchLogTests(unittest.TestCase):
    def test_saves_and_fetches_observations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "research.sqlite3"
            candidate_hash = make_candidate_hash(["scan-1", "middle", "event-1"])

            saved = save_observations(
                db_path,
                [
                    {
                        "created_at": "2026-05-27T10:00:00+00:00",
                        "scan_id": "scan-1",
                        "sport_key": "basketball_nba",
                        "sport_label": "NBA",
                        "regions": "us",
                        "market_mode": "middles",
                        "market_keys": "player_points",
                        "opportunity_type": "middle",
                        "signal": "TAKE",
                        "event_id": "event-1",
                        "event_label": "Away at Home",
                        "market_key": "player_points",
                        "participant": "Example Player",
                        "books": "Book A / Book B",
                        "lines": "O20.5 / U23.5",
                        "odds": "-110 / -115",
                        "expected_value": 12.5,
                        "candidate_hash": candidate_hash,
                    }
                ],
            )

            self.assertEqual(saved, 1)
            self.assertEqual(count_observations(db_path), 1)
            rows = fetch_observations(db_path, signal="TAKE")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["event_label"], "Away at Home")
            self.assertEqual(rows[0]["review_status"], "New")

    def test_duplicate_hash_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "research.sqlite3"
            observation = {
                "scan_id": "scan-1",
                "opportunity_type": "middle",
                "signal": "WATCH",
                "candidate_hash": "duplicate",
            }

            self.assertEqual(save_observations(db_path, [observation]), 1)
            self.assertEqual(save_observations(db_path, [observation]), 0)
            self.assertEqual(count_observations(db_path), 1)

    def test_updates_review_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "research.sqlite3"
            save_observations(
                db_path,
                [
                    {
                        "scan_id": "scan-1",
                        "opportunity_type": "outright",
                        "signal": "PASS",
                        "candidate_hash": "candidate-1",
                    }
                ],
            )
            row = fetch_observations(db_path)[0]

            update_observation_review(
                db_path,
                row["id"],
                review_status="Ignored",
                notes="Too much omitted-field risk.",
                final_result="Not tracked",
            )

            updated = fetch_observations(db_path, review_status="Ignored")[0]
            self.assertEqual(updated["notes"], "Too much omitted-field risk.")
            self.assertEqual(updated["final_result"], "Not tracked")


if __name__ == "__main__":
    unittest.main()
