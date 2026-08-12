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
            patch.object(review, "_load_config", return_value={"system_start_date": None, "auto_forgot_after_days": 14, "daily_show_limit": 3}),
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
            patch.object(review, "_load_config", return_value={"system_start_date": None, "auto_forgot_after_days": 14, "daily_show_limit": 3}),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, ["three-sum"])
        self.assertEqual(updated["three-sum"]["next_review"], "2026-08-05")

    # ------------------------------------------------------------------
    # Cutoff enforcement
    # ------------------------------------------------------------------

    def test_problem_before_system_start_date_is_skipped(self):
        today = date(2026, 8, 6)
        repo_root = Path("/repo")
        reviews = {}
        discovered = {
            "old-problem": {"topic": "Data Structures & Algorithms", "difficulty": "Easy"},
        }
        with (
            patch.object(review, "discover_problems", return_value=discovered),
            patch.object(review, "_problem_solution_files", return_value=[repo_root / "old-problem" / "s.py"]),
            patch.object(review, "_first_commit_date", return_value=date(2026, 8, 5)),
            patch.object(review, "_load_config", return_value={
                "system_start_date": "2026-08-06",
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, [])
        self.assertNotIn("old-problem", updated)

    def test_problem_on_system_start_date_is_registered(self):
        today = date(2026, 8, 6)
        repo_root = Path("/repo")
        reviews = {}
        discovered = {
            "new-problem": {"topic": "Data Structures & Algorithms", "difficulty": "Medium"},
        }
        with (
            patch.object(review, "discover_problems", return_value=discovered),
            patch.object(review, "_problem_solution_files", return_value=[repo_root / "new-problem" / "s.py"]),
            patch.object(review, "_first_commit_date", return_value=date(2026, 8, 6)),
            patch.object(review, "_load_config", return_value={
                "system_start_date": "2026-08-06",
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, ["new-problem"])
        self.assertIn("new-problem", updated)

    def test_problem_after_system_start_date_is_registered(self):
        today = date(2026, 8, 10)
        repo_root = Path("/repo")
        reviews = {}
        discovered = {
            "newer-problem": {"topic": "Data Structures & Algorithms", "difficulty": "Hard"},
        }
        with (
            patch.object(review, "discover_problems", return_value=discovered),
            patch.object(review, "_problem_solution_files", return_value=[repo_root / "newer-problem" / "s.py"]),
            patch.object(review, "_first_commit_date", return_value=date(2026, 8, 8)),
            patch.object(review, "_load_config", return_value={
                "system_start_date": "2026-08-06",
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, ["newer-problem"])

    def test_already_present_problem_not_removed_by_cutoff(self):
        """Problems already in reviews.json are untouched even if their commit predates the cutoff."""
        today = date(2026, 8, 6)
        repo_root = Path("/repo")
        reviews = {
            "coin-change-ii": {
                "difficulty": "Medium",
                "ease_factor": 2.5,
                "interval": 1,
                "last_review": "2026-08-04",
                "next_review": "2026-08-05",
                "review_count": 1,
                "topic": "Data Structures & Algorithms",
            }
        }
        discovered = {
            "coin-change-ii": {"topic": "Data Structures & Algorithms", "difficulty": "Medium"},
        }
        with (
            patch.object(review, "discover_problems", return_value=discovered),
            patch.object(review, "_load_config", return_value={
                "system_start_date": "2026-08-06",
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, [])
        self.assertIn("coin-change-ii", updated)
        self.assertEqual(updated["coin-change-ii"]["review_count"], 1)

    # ------------------------------------------------------------------
    # Auto-forgot sweep
    # ------------------------------------------------------------------

    def test_auto_forgot_applied_for_heavily_overdue_problem(self):
        today = date(2026, 8, 6)
        # next_review 15 days ago → overdue > 14
        entry = {
            "difficulty": "Medium",
            "ease_factor": 2.5,
            "interval": 4,
            "last_review": "2026-07-15",
            "next_review": "2026-07-22",  # 15 days overdue
            "review_count": 2,
            "topic": "Data Structures & Algorithms",
        }
        reviews = {"hard-problem": dict(entry)}

        with (
            patch.object(review, "discover_problems", return_value={}),
            patch.object(review, "_load_config", return_value={
                "system_start_date": "2026-08-06",
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
            patch.object(review, "_load_reviews", return_value=reviews),
            patch.object(review, "_save_reviews"),
        ):
            review.run_daily(today)

        updated = reviews["hard-problem"]
        self.assertEqual(updated["interval"], 1)
        self.assertEqual(updated["next_review"], "2026-08-07")  # today + 1
        self.assertEqual(updated["review_count"], 3)
        self.assertLess(updated["ease_factor"], 2.5)

    def test_auto_forgot_not_applied_for_slightly_overdue_problem(self):
        today = date(2026, 8, 6)
        entry = {
            "difficulty": "Easy",
            "ease_factor": 2.5,
            "interval": 2,
            "last_review": "2026-07-25",
            "next_review": "2026-07-27",  # 10 days overdue — within threshold
            "review_count": 1,
            "topic": "Data Structures & Algorithms",
        }
        reviews = {"easy-problem": dict(entry)}

        saved: list[dict] = []

        with (
            patch.object(review, "discover_problems", return_value={}),
            patch.object(review, "_load_config", return_value={
                "system_start_date": "2026-08-06",
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
            patch.object(review, "_load_reviews", return_value=reviews),
            patch.object(review, "_save_reviews", side_effect=lambda r: saved.append(dict(r))),
        ):
            review.run_daily(today)

        # Entry should be unchanged (not auto-forgotten)
        saved_entry = saved[-1]["easy-problem"]
        self.assertEqual(saved_entry["interval"], 2)
        self.assertEqual(saved_entry["review_count"], 1)

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def test_load_config_missing_file_returns_defaults(self):
        with patch.object(review, "_CONFIG_PATH", Path("/nonexistent/config.json")):
            config = review._load_config()
        self.assertIsNone(config["system_start_date"])
        self.assertEqual(config["auto_forgot_after_days"], 14)
        self.assertEqual(config["daily_show_limit"], 3)

    def test_load_config_bad_json_returns_defaults(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            tmp_path = Path(f.name)
        try:
            with patch.object(review, "_CONFIG_PATH", tmp_path):
                config = review._load_config()
            self.assertEqual(config["auto_forgot_after_days"], 14)
        finally:
            os.unlink(tmp_path)

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def test_run_daily_twice_same_day_does_not_double_apply_auto_forgot(self):
        today = date(2026, 8, 6)
        # overdue > 14 days
        entry = {
            "difficulty": "Medium",
            "ease_factor": 2.5,
            "interval": 4,
            "last_review": "2026-07-15",
            "next_review": "2026-07-22",
            "review_count": 2,
            "topic": "Data Structures & Algorithms",
        }
        reviews = {"some-problem": dict(entry)}

        config = {
            "system_start_date": "2026-08-06",
            "auto_forgot_after_days": 14,
            "daily_show_limit": 3,
        }

        # First run
        with (
            patch.object(review, "discover_problems", return_value={}),
            patch.object(review, "_load_config", return_value=config),
            patch.object(review, "_load_reviews", return_value={k: dict(v) for k, v in reviews.items()}),
            patch.object(review, "_save_reviews", side_effect=lambda r: reviews.update(r)),
        ):
            review.run_daily(today)

        ease_after_first = reviews["some-problem"]["ease_factor"]
        count_after_first = reviews["some-problem"]["review_count"]
        next_review_after_first = reviews["some-problem"]["next_review"]

        # Second run on same day — next_review is now tomorrow so not overdue
        with (
            patch.object(review, "discover_problems", return_value={}),
            patch.object(review, "_load_config", return_value=config),
            patch.object(review, "_load_reviews", return_value={k: dict(v) for k, v in reviews.items()}),
            patch.object(review, "_save_reviews", side_effect=lambda r: reviews.update(r)),
        ):
            review.run_daily(today)

        self.assertEqual(reviews["some-problem"]["ease_factor"], ease_after_first)
        self.assertEqual(reviews["some-problem"]["review_count"], count_after_first)
        self.assertEqual(reviews["some-problem"]["next_review"], next_review_after_first)

    # ------------------------------------------------------------------
    # Pruning of stale entries (retroactive system_start_date enforcement)
    # ------------------------------------------------------------------

    def test_stale_entry_no_history_before_start_date_is_pruned(self):
        """Pre-seeded entry with no review history is removed when its commit predates system_start_date."""
        today = date(2026, 8, 12)
        repo_root = Path("/repo")
        reviews = {
            "old-seeded": {
                "difficulty": "Easy",
                "ease_factor": 2.5,
                "interval": 1,
                "last_review": None,
                "next_review": "2026-08-12",
                "review_count": 0,
                "topic": "Data Structures & Algorithms",
            }
        }
        with (
            patch.object(review, "discover_problems", return_value={}),
            patch.object(
                review,
                "_problem_solution_files",
                return_value=[repo_root / "old-seeded" / "s.py"],
            ),
            patch.object(review, "_first_commit_date", return_value=date(2026, 7, 1)),
            patch.object(review, "_load_config", return_value={
                "system_start_date": "2026-08-06",
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertNotIn("old-seeded", updated)
        self.assertEqual(new_ids, [])

    def test_stale_entry_with_review_history_is_preserved(self):
        """Entry with review_count > 0 is never pruned regardless of commit date."""
        today = date(2026, 8, 12)
        repo_root = Path("/repo")
        reviews = {
            "coin-change-ii": {
                "difficulty": "Medium",
                "ease_factor": 2.65,
                "interval": 3,
                "last_review": "2026-08-10",
                "next_review": "2026-08-13",
                "review_count": 2,
                "topic": "Data Structures & Algorithms",
            }
        }
        with (
            patch.object(review, "discover_problems", return_value={}),
            patch.object(review, "_load_config", return_value={
                "system_start_date": "2026-08-06",
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertIn("coin-change-ii", updated)
        self.assertEqual(updated["coin-change-ii"]["review_count"], 2)

    def test_stale_entry_last_review_not_null_is_preserved(self):
        """Entry with last_review set (even review_count == 0) is never pruned."""
        today = date(2026, 8, 12)
        repo_root = Path("/repo")
        reviews = {
            "some-problem": {
                "difficulty": "Easy",
                "ease_factor": 2.5,
                "interval": 1,
                "last_review": "2026-08-07",
                "next_review": "2026-08-08",
                "review_count": 0,
                "topic": "Data Structures & Algorithms",
            }
        }
        with (
            patch.object(review, "discover_problems", return_value={}),
            patch.object(review, "_load_config", return_value={
                "system_start_date": "2026-08-06",
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertIn("some-problem", updated)

    def test_no_system_start_date_skips_pruning(self):
        """When system_start_date is None, no pruning occurs and fallback to today works."""
        today = date(2026, 8, 12)
        repo_root = Path("/repo")
        reviews = {
            "old-seeded": {
                "difficulty": "Easy",
                "ease_factor": 2.5,
                "interval": 1,
                "last_review": None,
                "next_review": "2026-08-12",
                "review_count": 0,
                "topic": "Data Structures & Algorithms",
            }
        }
        with (
            patch.object(review, "discover_problems", return_value={}),
            patch.object(review, "_load_config", return_value={
                "system_start_date": None,
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertIn("old-seeded", updated)

    def test_no_commit_dates_with_system_start_date_skips_new_problem(self):
        """When git history is unavailable and system_start_date is set, new problems are skipped."""
        today = date(2026, 8, 12)
        repo_root = Path("/repo")
        reviews = {}
        discovered = {
            "mystery-problem": {"topic": "Data Structures & Algorithms", "difficulty": "Hard"},
        }
        with (
            patch.object(review, "discover_problems", return_value=discovered),
            patch.object(review, "_problem_solution_files", return_value=[repo_root / "mystery-problem" / "s.py"]),
            patch.object(review, "_first_commit_date", return_value=None),
            patch.object(review, "_load_config", return_value={
                "system_start_date": "2026-08-06",
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertNotIn("mystery-problem", updated)
        self.assertEqual(new_ids, [])

    def test_no_commit_dates_without_system_start_date_falls_back_to_today(self):
        """When git history is unavailable and no system_start_date, problem is registered with today."""
        today = date(2026, 8, 12)
        repo_root = Path("/repo")
        reviews = {}
        discovered = {
            "mystery-problem": {"topic": "Data Structures & Algorithms", "difficulty": "Hard"},
        }
        with (
            patch.object(review, "discover_problems", return_value=discovered),
            patch.object(review, "_problem_solution_files", return_value=[repo_root / "mystery-problem" / "s.py"]),
            patch.object(review, "_first_commit_date", return_value=None),
            patch.object(review, "_load_config", return_value={
                "system_start_date": None,
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
        ):
            updated, new_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertIn("mystery-problem", updated)
        self.assertEqual(new_ids, ["mystery-problem"])
        # next_review should be today + 1
        self.assertEqual(updated["mystery-problem"]["next_review"], "2026-08-13")
        today = date(2026, 8, 6)
        # overdue > 14 days
        entry = {
            "difficulty": "Medium",
            "ease_factor": 2.5,
            "interval": 4,
            "last_review": "2026-07-15",
            "next_review": "2026-07-22",
            "review_count": 2,
            "topic": "Data Structures & Algorithms",
        }
        reviews = {"some-problem": dict(entry)}

        config = {
            "system_start_date": "2026-08-06",
            "auto_forgot_after_days": 14,
            "daily_show_limit": 3,
        }

        # First run
        with (
            patch.object(review, "discover_problems", return_value={}),
            patch.object(review, "_load_config", return_value=config),
            patch.object(review, "_load_reviews", return_value={k: dict(v) for k, v in reviews.items()}),
            patch.object(review, "_save_reviews", side_effect=lambda r: reviews.update(r)),
        ):
            review.run_daily(today)

        ease_after_first = reviews["some-problem"]["ease_factor"]
        count_after_first = reviews["some-problem"]["review_count"]
        next_review_after_first = reviews["some-problem"]["next_review"]

        # Second run on same day — next_review is now tomorrow so not overdue
        with (
            patch.object(review, "discover_problems", return_value={}),
            patch.object(review, "_load_config", return_value=config),
            patch.object(review, "_load_reviews", return_value={k: dict(v) for k, v in reviews.items()}),
            patch.object(review, "_save_reviews", side_effect=lambda r: reviews.update(r)),
        ):
            review.run_daily(today)

        self.assertEqual(reviews["some-problem"]["ease_factor"], ease_after_first)
        self.assertEqual(reviews["some-problem"]["review_count"], count_after_first)
        self.assertEqual(reviews["some-problem"]["next_review"], next_review_after_first)


if __name__ == "__main__":
    unittest.main()
