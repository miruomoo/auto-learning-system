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
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, ["two-sum"])
        self.assertEqual(backfilled_ids, [])
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
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, ["three-sum"])
        self.assertEqual(backfilled_ids, [])
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
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, [])
        self.assertEqual(backfilled_ids, [])
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
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, ["new-problem"])
        self.assertEqual(backfilled_ids, [])
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
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, ["newer-problem"])
        self.assertEqual(backfilled_ids, [])

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
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, [])
        self.assertEqual(backfilled_ids, [])
        self.assertIn("coin-change-ii", updated)
        self.assertEqual(updated["coin-change-ii"]["review_count"], 1)

    def test_existing_zero_review_problem_backfills_last_review_from_post_start_commit(self):
        today = date(2026, 8, 12)
        repo_root = Path("/repo")
        reviews = {
            "valid-problem": {
                "difficulty": "Unknown",
                "ease_factor": 2.5,
                "interval": 3,
                "last_review": None,
                "next_review": "2026-08-12",
                "review_count": 0,
                "topic": "Unknown",
            }
        }
        discovered = {
            "valid-problem": {"topic": "Data Structures & Algorithms", "difficulty": "Medium"},
        }
        with (
            patch.object(review, "discover_problems", return_value=discovered),
            patch.object(review, "_problem_solution_files", return_value=[repo_root / "valid-problem" / "s.py"]),
            patch.object(review, "_first_commit_date", return_value=date(2026, 8, 8)),
            patch.object(review, "_load_config", return_value={
                "system_start_date": "2026-08-06",
                "auto_forgot_after_days": 14,
                "daily_show_limit": 3,
            }),
        ):
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertEqual(new_ids, [])
        self.assertEqual(backfilled_ids, ["valid-problem"])
        self.assertEqual(updated["valid-problem"]["last_review"], "2026-08-08")
        self.assertEqual(updated["valid-problem"]["next_review"], "2026-08-11")
        self.assertEqual(updated["valid-problem"]["review_count"], 0)
        self.assertEqual(updated["valid-problem"]["ease_factor"], 2.5)
        self.assertEqual(updated["valid-problem"]["difficulty"], "Medium")
        self.assertEqual(updated["valid-problem"]["topic"], "Data Structures & Algorithms")

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
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertNotIn("old-seeded", updated)
        self.assertEqual(new_ids, [])
        self.assertEqual(backfilled_ids, [])

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
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertIn("coin-change-ii", updated)
        self.assertEqual(backfilled_ids, [])
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
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertIn("some-problem", updated)
        self.assertEqual(backfilled_ids, [])

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
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertIn("old-seeded", updated)
        self.assertEqual(backfilled_ids, [])

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
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertNotIn("mystery-problem", updated)
        self.assertEqual(new_ids, [])
        self.assertEqual(backfilled_ids, [])

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
            updated, new_ids, backfilled_ids = review.sync_new_problems(reviews, repo_root, today)

        self.assertIn("mystery-problem", updated)
        self.assertEqual(new_ids, ["mystery-problem"])
        self.assertEqual(backfilled_ids, [])
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

    # ------------------------------------------------------------------
    # Pause feature
    # ------------------------------------------------------------------

    def test_is_paused_returns_true_when_today_before_pause_until(self):
        config = {"pause_until": "2026-08-25"}
        self.assertTrue(review.is_paused(config, date(2026, 8, 18)))

    def test_is_paused_returns_true_on_pause_until_date(self):
        config = {"pause_until": "2026-08-25"}
        self.assertTrue(review.is_paused(config, date(2026, 8, 25)))

    def test_is_paused_returns_false_after_pause_until(self):
        config = {"pause_until": "2026-08-25"}
        self.assertFalse(review.is_paused(config, date(2026, 8, 26)))

    def test_is_paused_returns_false_when_no_pause_until(self):
        self.assertFalse(review.is_paused({}, date(2026, 8, 18)))
        self.assertFalse(review.is_paused({"pause_until": None}, date(2026, 8, 18)))

    def test_is_paused_returns_false_on_invalid_date(self):
        config = {"pause_until": "not-a-date"}
        self.assertFalse(review.is_paused(config, date(2026, 8, 18)))

    def test_run_daily_skips_when_paused(self):
        """run_daily should print the pause message and return without touching reviews."""
        today = date(2026, 8, 18)
        config = {
            "system_start_date": None,
            "auto_forgot_after_days": 14,
            "daily_show_limit": 3,
            "pause_until": "2026-08-20",
        }
        save_called = []
        with (
            patch.object(review, "_load_config", return_value=config),
            patch.object(review, "_load_reviews", return_value={}),
            patch.object(review, "_save_reviews", side_effect=lambda r: save_called.append(r)),
        ):
            review.run_daily(today)

        # reviews should never be saved when paused
        self.assertEqual(save_called, [])


import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import process_review_comment as prc
import scheduler


class ResetEntryTests(unittest.TestCase):
    def test_reset_clears_scheduling_fields(self):
        today = date(2026, 8, 26)
        entry = {
            "difficulty": "Hard",
            "topic": "Graphs",
            "last_review": "2026-08-20",
            "next_review": "2026-08-30",
            "interval": 15,
            "ease_factor": 3.0,
            "review_count": 7,
        }
        result = scheduler.reset_entry(entry, today)
        self.assertIsNone(result["last_review"])
        self.assertEqual(result["next_review"], "2026-08-27")
        self.assertEqual(result["interval"], 1)
        self.assertEqual(result["ease_factor"], 2.5)
        self.assertEqual(result["review_count"], 0)

    def test_reset_preserves_difficulty_and_topic(self):
        today = date(2026, 8, 26)
        entry = {
            "difficulty": "Hard",
            "topic": "Graphs",
            "last_review": "2026-08-20",
            "next_review": "2026-08-30",
            "interval": 15,
            "ease_factor": 3.0,
            "review_count": 7,
        }
        result = scheduler.reset_entry(entry, today)
        self.assertEqual(result["difficulty"], "Hard")
        self.assertEqual(result["topic"], "Graphs")

    def test_reset_does_not_mutate_original(self):
        today = date(2026, 8, 26)
        entry = {
            "difficulty": "Medium",
            "topic": "Arrays",
            "last_review": "2026-08-10",
            "next_review": "2026-08-20",
            "interval": 10,
            "ease_factor": 2.8,
            "review_count": 3,
        }
        scheduler.reset_entry(entry, today)
        self.assertEqual(entry["interval"], 10)
        self.assertEqual(entry["review_count"], 3)

    def test_reset_uses_today_by_default(self):
        entry = {"difficulty": "Easy", "topic": "Arrays", "interval": 5, "ease_factor": 2.5, "review_count": 2}
        result = scheduler.reset_entry(entry)
        # next_review should be tomorrow
        from datetime import timedelta
        self.assertEqual(result["next_review"], (date.today() + timedelta(days=1)).isoformat())


class ResetParseCommandsTests(unittest.TestCase):
    def test_parse_reset_command(self):
        commands = prc.parse_commands("review 3 reset")
        self.assertEqual(commands, [(3, "Reset")])

    def test_parse_reset_case_insensitive(self):
        commands = prc.parse_commands("review 2 RESET")
        self.assertEqual(commands, [(2, "Reset")])

    def test_reset_alongside_other_commands(self):
        body = "review 1 easy\nreview 2 reset\nreview 3 forgot"
        commands = prc.parse_commands(body)
        self.assertEqual(commands, [(1, "Easy"), (2, "Reset"), (3, "Forgot")])


class ProcessCommandsResetTests(unittest.TestCase):
    def test_process_reset_command_updates_entry(self):
        today = date(2026, 8, 26)
        problem_map = {"1": "two-sum"}
        reviews = {
            "two-sum": {
                "difficulty": "Easy",
                "topic": "Arrays",
                "last_review": "2026-08-20",
                "next_review": "2026-08-30",
                "interval": 15,
                "ease_factor": 3.0,
                "review_count": 7,
            }
        }
        results, errors = prc.process_commands([(1, "Reset")], problem_map, reviews, today)
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["rating"], "Reset")
        self.assertEqual(r["interval"], 1)
        from datetime import date as _date
        self.assertEqual(r["next_review"], _date(2026, 8, 27))

        entry = reviews["two-sum"]
        self.assertEqual(entry["interval"], 1)
        self.assertIsNone(entry["last_review"])
        self.assertEqual(entry["difficulty"], "Easy")
        self.assertEqual(entry["topic"], "Arrays")




class RemoveCommandTests(unittest.TestCase):
    def test_parse_remove_command(self):
        commands = prc.parse_commands("review 2 remove")
        self.assertEqual(commands, [(2, "Remove")])

    def test_parse_remove_case_insensitive(self):
        commands = prc.parse_commands("review 4 REMOVE")
        self.assertEqual(commands, [(4, "Remove")])

    def test_process_remove_deletes_entry(self):
        today = date(2026, 8, 26)
        problem_map = {"1": "two-sum"}
        reviews = {
            "two-sum": {
                "difficulty": "Easy",
                "topic": "Arrays",
                "last_review": "2026-08-20",
                "next_review": "2026-08-30",
                "interval": 15,
                "ease_factor": 3.0,
                "review_count": 7,
            }
        }
        results, errors = prc.process_commands([(1, "Remove")], problem_map, reviews, today)
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["rating"], "Remove")
        self.assertEqual(results[0]["name"], "Two Sum")
        self.assertNotIn("two-sum", reviews)

    def test_process_remove_result_has_no_next_review_or_interval(self):
        today = date(2026, 8, 26)
        problem_map = {"1": "two-sum"}
        reviews = {"two-sum": {"difficulty": "Easy", "topic": "Arrays", "interval": 5, "ease_factor": 2.5, "review_count": 1}}
        results, _ = prc.process_commands([(1, "Remove")], problem_map, reviews, today)
        self.assertNotIn("next_review", results[0])
        self.assertNotIn("interval", results[0])

    def test_build_reply_remove_single(self):
        results = [{"num": 1, "name": "Two Sum", "rating": "Remove"}]
        reply = prc.build_reply(results, [])
        self.assertIn("Remove", reply)
        self.assertIn("The problem has been removed from the review pool.", reply)
        self.assertNotIn("Next review", reply)

    def test_build_reply_remove_multi(self):
        results = [
            {"num": 1, "name": "Two Sum", "rating": "Remove"},
            {"num": 2, "name": "Binary Search", "rating": "Easy",
             "next_review": date(2026, 9, 5), "interval": 10},
        ]
        reply = prc.build_reply(results, [])
        self.assertIn("Removed from the review pool", reply)
        self.assertIn("Binary Search", reply)


class PauseCommandParsingTests(unittest.TestCase):
    def test_parse_pause_command_basic(self):
        self.assertEqual(prc.parse_pause_command("pause 7"), 7)

    def test_parse_pause_command_case_insensitive(self):
        self.assertEqual(prc.parse_pause_command("PAUSE 3"), 3)

    def test_parse_pause_command_leading_whitespace(self):
        self.assertEqual(prc.parse_pause_command("  pause 5  "), 5)

    def test_parse_pause_command_not_present(self):
        self.assertIsNone(prc.parse_pause_command("review 1 easy"))
        self.assertIsNone(prc.parse_pause_command("hello world"))

    def test_parse_pause_command_clamps_min(self):
        self.assertEqual(prc.parse_pause_command("pause 0"), 1)

    def test_parse_pause_command_clamps_max(self):
        self.assertEqual(prc.parse_pause_command("pause 999"), 365)

    def test_parse_pause_command_multiline_picks_first(self):
        body = "some text\npause 10\npause 20"
        self.assertEqual(prc.parse_pause_command(body), 10)


if __name__ == "__main__":
    unittest.main()
