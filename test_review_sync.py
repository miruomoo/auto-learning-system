import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, call, patch

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import daily_issue_lifecycle
import issue_formatter
import process_review_comment as prc
import review
import scheduler


CONFIG = {
    "system_start_date": "2026-08-06",
    "auto_forgot_after_days": 14,
    "daily_show_limit": 3,
    "pause_until": None,
}
META = {"topic": "Data Structures & Algorithms", "difficulty": "Hard"}


def submission(commit: str, timestamp: str) -> review.SubmissionEvent:
    return review.SubmissionEvent(commit, datetime.fromisoformat(timestamp))


def untouched_entry(**overrides) -> dict:
    entry = {
        "difficulty": "Hard",
        "ease_factor": 2.5,
        "interval": 1,
        "last_review": None,
        "next_review": "2026-09-23",
        "review_count": 0,
        "topic": "Data Structures & Algorithms",
    }
    entry.update(overrides)
    return entry


class SubmissionSyncTests(unittest.TestCase):
    def sync(self, reviews: dict, events: list[review.SubmissionEvent] | None):
        with (
            patch.object(review, "discover_problems", return_value={"problem": META}),
            patch.object(review, "_submission_events", return_value=events),
            patch.object(review, "_load_config", return_value=CONFIG),
        ):
            return review.sync_new_problems(reviews, Path("/repo"), date(2026, 9, 22))

    def test_pre_cutoff_files_do_not_block_first_post_cutoff_submission(self):
        old = submission("old", "2026-04-29T12:00:00+00:00")
        new = submission("new", "2026-09-19T01:00:00+00:00")

        updated, new_ids, completed = self.sync({}, [old, new])

        self.assertEqual(new_ids, ["problem"])
        self.assertEqual(completed, ["problem"])
        self.assertEqual(updated["problem"]["processed_submission_commits"], ["new"])
        self.assertEqual(updated["problem"]["last_review"], "2026-09-19")

    def test_largest_rectangle_regression_commit_is_eligible_on_september_19_utc(self):
        events = [
            submission("ed6ccbfe", "2026-04-29T11:52:30-04:00"),
            submission(
                "08892ef2af64cc3b9282f419c8f5a6e1f8341a46",
                "2026-09-18T21:58:58-04:00",
            ),
        ]

        updated, _, _ = self.sync({}, events)

        entry = updated["problem"]
        self.assertEqual(entry["last_review"], "2026-09-19")
        self.assertEqual(entry["next_review"], "2026-09-20")
        self.assertEqual(
            entry["processed_submission_commits"],
            ["08892ef2af64cc3b9282f419c8f5a6e1f8341a46"],
        )

    def test_imported_problem_can_be_added_after_a_later_submission(self):
        old = submission("old", "2026-04-29T12:00:00+00:00")
        updated, _, _ = self.sync({"problem": untouched_entry()}, [old])
        self.assertNotIn("problem", updated)

        new = submission("new", "2026-09-20T12:00:00+00:00")
        updated, new_ids, _ = self.sync(updated, [old, new])
        self.assertEqual(new_ids, ["problem"])
        self.assertIn("problem", updated)

    def test_multiple_submissions_are_processed_chronologically(self):
        events = [
            submission("third", "2026-09-21T12:00:00+00:00"),
            submission("first", "2026-09-19T12:00:00+00:00"),
            submission("second", "2026-09-20T12:00:00+00:00"),
        ]

        updated, _, _ = self.sync({}, events)

        self.assertEqual(
            updated["problem"]["processed_submission_commits"],
            ["first", "second", "third"],
        )
        self.assertEqual(updated["problem"]["last_review"], "2026-09-21")

    def test_submission_commit_is_not_processed_twice(self):
        event = submission("once", "2026-09-19T12:00:00+00:00")
        updated, _, _ = self.sync({}, [event])
        snapshot = json.loads(json.dumps(updated))

        rerun, new_ids, completed = self.sync(updated, [event])

        self.assertEqual(rerun, snapshot)
        self.assertEqual(new_ids, [])
        self.assertEqual(completed, [])

    def test_same_day_submissions_remain_distinct_and_idempotent(self):
        events = [
            submission("bbb", "2026-09-19T12:00:00+00:00"),
            submission("aaa", "2026-09-19T12:00:00+00:00"),
        ]
        updated, _, _ = self.sync({}, events)

        self.assertEqual(updated["problem"]["processed_submission_commits"], ["aaa", "bbb"])
        snapshot = json.loads(json.dumps(updated))
        rerun, _, _ = self.sync(updated, events)
        self.assertEqual(rerun, snapshot)

    def test_migration_preserves_established_rating_history(self):
        existing = untouched_entry(
            difficulty="Medium",
            topic="Graphs",
            ease_factor=2.65,
            interval=8,
            last_review="2026-09-10",
            next_review="2026-09-18",
            review_count=4,
        )
        expected_schedule = dict(existing)
        events = [
            submission("eligible-one", "2026-08-10T12:00:00+00:00"),
            submission("eligible-two", "2026-09-12T12:00:00+00:00"),
        ]

        updated, _, completed = self.sync({"problem": existing}, events)

        for field, value in expected_schedule.items():
            self.assertEqual(updated["problem"][field], value)
        self.assertEqual(
            updated["problem"]["processed_submission_commits"],
            ["eligible-one", "eligible-two"],
        )
        self.assertEqual(completed, [])

    def test_submission_uses_current_interval_without_changing_sm2_state(self):
        entry = untouched_entry(
            ease_factor=2.8,
            interval=6,
            last_review="2026-09-01",
            next_review="2026-09-07",
            review_count=5,
            processed_submission_commits=[],
        )
        event = submission("new", "2026-09-19T23:00:00+00:00")

        updated, _, _ = self.sync({"problem": entry}, [event])

        result = updated["problem"]
        self.assertEqual(result["last_review"], "2026-09-19")
        self.assertEqual(result["next_review"], "2026-09-25")
        self.assertEqual(result["interval"], 6)
        self.assertEqual(result["ease_factor"], 2.8)
        self.assertEqual(result["review_count"], 5)

    def test_git_history_failure_leaves_metadata_unchanged(self):
        entry = untouched_entry()
        original = dict(entry)
        updated, new_ids, completed = self.sync({"problem": entry}, None)
        self.assertEqual(updated["problem"], original)
        self.assertEqual(new_ids, [])
        self.assertEqual(completed, [])

    def test_git_log_parser_deduplicates_commit_and_sorts_deterministically(self):
        output = (
            "\x1ebbb\t2026-09-19T12:00:00+00:00\n\n"
            "Data Structures & Algorithms/problem/submission-2.py\n"
            "\x1eaaa\t2026-09-19T12:00:00+00:00\n\n"
            "Data Structures & Algorithms/problem/submission-0.py\n"
            "Data Structures & Algorithms/problem/submission-1.py\n"
        )
        result = Mock(returncode=0, stdout=output, stderr="")
        with patch.object(review.subprocess, "run", return_value=result):
            events = review._submission_events(Path("/repo"), "problem", META)
        self.assertEqual([event.commit for event in events], ["aaa", "bbb"])

    def test_invalid_cutoff_fails_instead_of_importing_history(self):
        with (
            patch.object(review, "discover_problems", return_value={}),
            patch.object(review, "_load_config", return_value={"system_start_date": "bad"}),
        ):
            with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
                review.sync_new_problems({}, Path("/repo"), date(2026, 9, 22))


class FormatterAuthorityTests(unittest.TestCase):
    def test_formatter_does_not_recreate_excluded_entry(self):
        with (
            patch.object(issue_formatter, "_load_reviews", return_value={}),
            patch.object(issue_formatter, "_load_config", return_value={"daily_show_limit": 3}),
        ):
            body, shown = issue_formatter.build_issue_body(date(2026, 9, 22))

        self.assertEqual(shown, [])
        self.assertIn("No reviews scheduled", body)
        self.assertFalse(hasattr(issue_formatter, "_sync"))

    def test_pruned_entry_stays_absent_during_formatting(self):
        old = submission("old", "2026-04-29T12:00:00+00:00")
        with (
            patch.object(review, "discover_problems", return_value={"problem": META}),
            patch.object(review, "_submission_events", return_value=[old]),
            patch.object(review, "_load_config", return_value=CONFIG),
        ):
            synchronized, _, _ = review.sync_new_problems(
                {"problem": untouched_entry()},
                Path("/repo"),
                date(2026, 9, 22),
            )
        with (
            patch.object(issue_formatter, "_load_reviews", return_value=synchronized),
            patch.object(issue_formatter, "_load_config", return_value={"daily_show_limit": 3}),
        ):
            _, shown = issue_formatter.build_issue_body(date(2026, 9, 22))
        self.assertEqual(synchronized, {})
        self.assertEqual(shown, [])

    def test_nonempty_body_preserves_hidden_problem_map(self):
        entry = untouched_entry(next_review="2026-09-22")
        with (
            patch.object(issue_formatter, "_load_reviews", return_value={"problem": entry}),
            patch.object(issue_formatter, "_load_config", return_value={"daily_show_limit": 3}),
        ):
            body, shown = issue_formatter.build_issue_body(date(2026, 9, 22))
        self.assertEqual(len(shown), 1)
        self.assertIn('<!-- problem-map: {"1": "problem"} -->', body)

    def test_cli_writes_machine_readable_has_reviews_output(self):
        with tempfile.TemporaryDirectory() as directory:
            body_path = Path(directory) / "body.md"
            output_path = Path(directory) / "output"
            with (
                patch.object(issue_formatter, "build_issue_body", return_value=("body", [])),
                patch.object(
                    sys,
                    "argv",
                    [
                        "issue_formatter.py",
                        "--body-file",
                        str(body_path),
                        "--github-output",
                        str(output_path),
                    ],
                ),
            ):
                issue_formatter.main()
            self.assertEqual(body_path.read_text(), "body\n")
            self.assertEqual(
                output_path.read_text(),
                "has_reviews=false\npaused=false\n",
            )


class DailyIssueLifecycleTests(unittest.TestCase):
    def test_empty_day_closes_only_older_matching_daily_issues(self):
        issues = [
            {"number": 1, "title": "📚 Daily LeetCode Review — 2026-09-21"},
            {"number": 2, "title": "📚 Daily LeetCode Review — 2026-09-22"},
            {"number": 3, "title": "Unrelated issue"},
            {"number": 4, "title": "📚 Daily LeetCode Review — invalid"},
            {"number": 5, "title": "📚 Daily LeetCode Review — 2026-09-23"},
        ]
        self.assertEqual(
            daily_issue_lifecycle.older_daily_issues(issues, date(2026, 9, 22)),
            [1],
        )

    def test_current_day_issue_remains_open(self):
        issues = [{"number": 49, "title": "📚 Daily LeetCode Review — 2026-09-22"}]
        self.assertEqual(
            daily_issue_lifecycle.older_daily_issues(issues, date(2026, 9, 22)),
            [],
        )

    def test_unrelated_issue_remains_open(self):
        issues = [{"number": 8, "title": "Fix 📚 Daily LeetCode Review — 2026-09-01"}]
        self.assertEqual(
            daily_issue_lifecycle.older_daily_issues(issues, date(2026, 9, 22)),
            [],
        )

    def test_nonempty_run_does_not_query_or_close_issues(self):
        with patch.object(daily_issue_lifecycle.subprocess, "run") as run:
            closed = daily_issue_lifecycle.close_stale_daily_issues(
                "owner/repo", date(2026, 9, 22), has_reviews=True
            )
        self.assertEqual(closed, [])
        run.assert_not_called()

    def test_paused_run_does_not_query_or_close_issues(self):
        with patch.object(daily_issue_lifecycle.subprocess, "run") as run:
            closed = daily_issue_lifecycle.close_stale_daily_issues(
                "owner/repo",
                date(2026, 9, 22),
                has_reviews=False,
                paused=True,
            )
        self.assertEqual(closed, [])
        run.assert_not_called()

    def test_closing_issues_adds_explanatory_comment(self):
        listed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [{"number": 7, "title": "📚 Daily LeetCode Review — 2026-09-21"}]
            ),
            stderr="",
        )
        with patch.object(
            daily_issue_lifecycle.subprocess,
            "run",
            side_effect=[listed, subprocess.CompletedProcess(args=[], returncode=0)],
        ) as run:
            closed = daily_issue_lifecycle.close_stale_daily_issues(
                "owner/repo", date(2026, 9, 22), has_reviews=False
            )
        self.assertEqual(closed, [7])
        close_command = run.call_args_list[1].args[0]
        self.assertIn("--comment", close_command)
        self.assertIn(daily_issue_lifecycle.CLOSING_COMMENT, close_command)

    def test_repeated_empty_run_has_no_duplicate_close_action(self):
        first = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [{"number": 7, "title": "📚 Daily LeetCode Review — 2026-09-21"}]
            ),
            stderr="",
        )
        closed = subprocess.CompletedProcess(args=[], returncode=0)
        second = subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr="")
        with patch.object(
            daily_issue_lifecycle.subprocess,
            "run",
            side_effect=[first, closed, second],
        ) as run:
            daily_issue_lifecycle.close_stale_daily_issues(
                "owner/repo", date(2026, 9, 22), has_reviews=False
            )
            daily_issue_lifecycle.close_stale_daily_issues(
                "owner/repo", date(2026, 9, 22), has_reviews=False
            )
        close_calls = [
            invocation
            for invocation in run.call_args_list
            if invocation.args[0][:3] == ["gh", "issue", "close"]
        ]
        self.assertEqual(len(close_calls), 1)


class DailyReviewTests(unittest.TestCase):
    def test_auto_forgot_is_idempotent(self):
        today = date(2026, 8, 6)
        reviews = {
            "problem": untouched_entry(
                ease_factor=2.5,
                interval=4,
                last_review="2026-07-15",
                next_review="2026-07-22",
                review_count=2,
                processed_submission_commits=[],
            )
        }
        config = {**CONFIG, "system_start_date": None}

        for _ in range(2):
            with (
                patch.object(review, "_load_config", return_value=config),
                patch.object(review, "_load_reviews", return_value=reviews),
                patch.object(review, "sync_new_problems", return_value=(reviews, [], [])),
                patch.object(review, "_save_reviews"),
            ):
                review.run_daily(today)

        self.assertEqual(reviews["problem"]["review_count"], 3)
        self.assertEqual(reviews["problem"]["next_review"], "2026-08-07")

    def test_run_daily_skips_when_paused(self):
        config = {**CONFIG, "pause_until": "2026-08-20"}
        with (
            patch.object(review, "_load_config", return_value=config),
            patch.object(review, "_load_reviews") as load,
        ):
            review.run_daily(date(2026, 8, 18))
        load.assert_not_called()

    def test_load_config_missing_file_returns_defaults(self):
        with patch.object(review, "_CONFIG_PATH", Path("/nonexistent/config.json")):
            config = review._load_config()
        self.assertIsNone(config["system_start_date"])
        self.assertEqual(config["daily_show_limit"], 3)


class SchedulerAndCommentTests(unittest.TestCase):
    def test_reset_preserves_metadata_and_resets_schedule(self):
        entry = untouched_entry(
            difficulty="Hard",
            topic="Graphs",
            last_review="2026-08-20",
            next_review="2026-08-30",
            interval=15,
            ease_factor=3.0,
            review_count=7,
            processed_submission_commits=["existing"],
        )
        result = scheduler.reset_entry(entry, date(2026, 8, 26))
        self.assertEqual(result["difficulty"], "Hard")
        self.assertEqual(result["topic"], "Graphs")
        self.assertIsNone(result["last_review"])
        self.assertEqual(result["next_review"], "2026-08-27")
        self.assertEqual(result["review_count"], 0)
        self.assertEqual(result["processed_submission_commits"], ["existing"])
        self.assertEqual(entry["review_count"], 7)

    def test_reset_cursor_prevents_historical_submission_replay(self):
        events = [submission("existing", "2026-09-19T12:00:00+00:00")]
        reset = scheduler.reset_entry(
            untouched_entry(processed_submission_commits=["existing"]),
            date(2026, 9, 22),
        )
        with (
            patch.object(review, "discover_problems", return_value={"problem": META}),
            patch.object(review, "_submission_events", return_value=events),
            patch.object(review, "_load_config", return_value=CONFIG),
        ):
            updated, _, completed = review.sync_new_problems(
                {"problem": reset},
                Path("/repo"),
                date(2026, 9, 22),
            )
        self.assertEqual(updated["problem"]["next_review"], "2026-09-23")
        self.assertEqual(completed, [])

    def test_parse_ratings_reset_remove_and_pause(self):
        self.assertEqual(
            prc.parse_commands(
                "review 1 easy\nreview 2 MEDIUM\nreview 3 forgot\nreview 4 reset\nreview 5 remove"
            ),
            [(1, "Easy"), (2, "Medium"), (3, "Forgot"), (4, "Reset"), (5, "Remove")],
        )
        self.assertEqual(prc.parse_pause_command("pause 999"), 365)

    def test_process_rating_updates_entry(self):
        reviews = {"problem": untouched_entry()}
        results, errors = prc.process_commands(
            [(1, "Easy")], {"1": "problem"}, reviews, date(2026, 9, 22)
        )
        self.assertEqual(errors, [])
        self.assertEqual(results[0]["rating"], "Easy")
        self.assertEqual(reviews["problem"]["review_count"], 1)

    def test_process_reset_and_remove(self):
        reviews = {
            "reset-me": untouched_entry(review_count=2),
            "remove-me": untouched_entry(review_count=2),
        }
        results, errors = prc.process_commands(
            [(1, "Reset"), (2, "Remove")],
            {"1": "reset-me", "2": "remove-me"},
            reviews,
            date(2026, 9, 22),
        )
        self.assertEqual(errors, [])
        self.assertEqual([result["rating"] for result in results], ["Reset", "Remove"])
        self.assertEqual(reviews["reset-me"]["review_count"], 0)
        self.assertNotIn("remove-me", reviews)


if __name__ == "__main__":
    unittest.main()
