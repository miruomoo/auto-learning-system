import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import review


class SyncNewProblemsTests(unittest.TestCase):
    def test_new_problem_uses_earliest_solution_commit_date(self):
        today = date(2026, 8, 4)
        repo_root = Path("/repo")
        reviews = {}
        discovered = {
            "two-sum": {
                "topic": "Data Structures & Algorithms",
                "difficulty": "Easy",
            }
        }

        with (
            patch.object(review, "discover_problems", return_value=discovered),
            patch.object(
                review,
                "_problem_solution_files",
                return_value=[
                    repo_root / "Data Structures & Algorithms" / "two-sum" / "submission-0.py",
                    repo_root / "Data Structures & Algorithms" / "two-sum" / "submission-1.py",
                ],
            ),
            patch.object(
                review,
                "_first_commit_date",
                side_effect=[date(2026, 7, 28), date(2026, 7, 30)],
            ),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, ["two-sum"])
        self.assertEqual(updated["two-sum"]["next_review"], "2026-07-29")
        self.assertEqual(updated["two-sum"]["difficulty"], "Easy")
        self.assertEqual(updated["two-sum"]["topic"], "Data Structures & Algorithms")

    def test_new_problem_falls_back_to_today_when_commit_dates_missing(self):
        today = date(2026, 8, 4)
        repo_root = Path("/repo")
        reviews = {}
        discovered = {
            "three-sum": {
                "topic": "Data Structures & Algorithms",
                "difficulty": "Medium",
            }
        }

        with (
            patch.object(review, "discover_problems", return_value=discovered),
            patch.object(
                review,
                "_problem_solution_files",
                return_value=[repo_root / "Data Structures & Algorithms" / "three-sum" / "submission-0.py"],
            ),
            patch.object(review, "_first_commit_date", return_value=None),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, ["three-sum"])
        self.assertEqual(updated["three-sum"]["next_review"], "2026-08-05")


if __name__ == "__main__":
    unittest.main()
