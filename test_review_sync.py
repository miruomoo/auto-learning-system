import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import daily_issue_lifecycle
import issue_formatter
import process_review_comment as prc
import review
import review_day_preflight
import scheduler


CONFIG = {
    "system_start_date": "2026-08-06",
    "auto_forgot_after_days": 14,
    "daily_show_limit": 3,
    "pause_until": None,
    "weekend_enabled": False,
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


def daily_issue(
    issue_date: str, problem_map: dict, required_problem_map: dict | None = None
) -> dict:
    body = f"<!-- problem-map: {json.dumps(problem_map)} -->"
    if required_problem_map is not None:
        body += f"\n<!-- required-problem-map: {json.dumps(required_problem_map)} -->"
    return {"title": f"📚 Daily LeetCode Review — {issue_date}", "body": body}


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
        self.assertEqual(entry["next_review"], "2026-09-21")
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

    def test_submission_scheduling_uses_weekend_setting(self):
        event = submission("weekend", "2026-10-02T12:00:00+00:00")
        with (
            patch.object(review, "discover_problems", return_value={"problem": META}),
            patch.object(review, "_submission_events", return_value=[event]),
            patch.object(
                review,
                "_load_config",
                return_value={**CONFIG, "weekend_enabled": True},
            ),
        ):
            updated, _, _ = review.sync_new_problems(
                {}, Path("/repo"), date(2026, 10, 2)
            )

        self.assertEqual(updated["problem"]["next_review"], "2026-10-03")

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
    def build_due_issue(self, problem_ids: list[str], limit: int) -> tuple[str, list]:
        reviews = {
            problem_id: untouched_entry(next_review="2026-09-22")
            for problem_id in problem_ids
        }
        with (
            patch.object(issue_formatter, "_load_reviews", return_value=reviews),
            patch.object(
                issue_formatter, "_load_config", return_value={"daily_show_limit": limit}
            ),
        ):
            return issue_formatter.build_issue_body(date(2026, 9, 22))

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
        self.assertIn('<!-- required-problem-map: {"1": "problem"} -->', body)

    def test_formatter_includes_weekend_due_items_only_when_enabled(self):
        saturday = date(2026, 10, 3)
        reviews = {"problem": untouched_entry(next_review="2026-10-03")}

        for weekend_enabled, expected_count in ((False, 0), (True, 1)):
            with self.subTest(weekend_enabled=weekend_enabled):
                with (
                    patch.object(issue_formatter, "_load_reviews", return_value=reviews),
                    patch.object(
                        issue_formatter,
                        "_load_config",
                        return_value={
                            "daily_show_limit": 3,
                            "pause_until": None,
                            "weekend_enabled": weekend_enabled,
                        },
                    ),
                ):
                    _, shown = issue_formatter.build_issue_body(saturday)
                self.assertEqual(len(shown), expected_count)

    def test_formatter_sorts_and_labels_weekend_overdue_items(self):
        reviews = {
            "saturday": untouched_entry(next_review="2026-10-03"),
            "sunday": untouched_entry(next_review="2026-10-04"),
        }
        with (
            patch.object(issue_formatter, "_load_reviews", return_value=reviews),
            patch.object(
                issue_formatter,
                "_load_config",
                return_value={
                    "daily_show_limit": 3,
                    "pause_until": None,
                    "weekend_enabled": True,
                },
            ),
        ):
            body, shown = issue_formatter.build_issue_body(date(2026, 10, 4))

        self.assertEqual([problem_id for problem_id, _ in shown], ["saturday", "sunday"])
        self.assertIn("Due: 1 day overdue", body)
        self.assertIn("Due: Today", body)

    def test_one_deferred_problem_is_numbered_and_mapped_but_not_returned(self):
        problem_ids = [f"problem-{number}" for number in range(1, 7)]

        body, shown = self.build_due_issue(problem_ids, limit=5)

        deferred_section = body.split("### ⏭️ Deferred to Tomorrow", 1)[1]
        self.assertIn("6. 🔴 **Problem 6**", deferred_section)
        self.assertIn("`review 6 easy`", deferred_section)
        self.assertIn(
            '<!-- problem-map: {"1": "problem-1", "2": "problem-2", '
            '"3": "problem-3", "4": "problem-4", "5": "problem-5", '
            '"6": "problem-6"} -->',
            body,
        )
        self.assertIn(
            '<!-- required-problem-map: {"1": "problem-1", "2": "problem-2", '
            '"3": "problem-3", "4": "problem-4", "5": "problem-5"} -->',
            body,
        )
        self.assertEqual([problem_id for problem_id, _ in shown], problem_ids[:5])

    def test_multiple_deferred_problems_keep_sorted_order_and_continuous_numbers(self):
        problem_ids = [
            "hard-one",
            "hard-two",
            "hard-three",
            "hard-four",
            "hard-five",
            "hard-six",
        ]

        body, shown = self.build_due_issue(problem_ids, limit=3)

        deferred_section = body.split("### ⏭️ Deferred to Tomorrow", 1)[1]
        for number, problem_id in enumerate(problem_ids[3:], start=4):
            self.assertIn(
                f"{number}. 🔴 **{problem_id.replace('-', ' ').title()}**",
                deferred_section,
            )
        self.assertEqual(
            prc.extract_problem_map(body),
            {str(number): problem_id for number, problem_id in enumerate(problem_ids, 1)},
        )
        self.assertEqual(
            prc.extract_required_problem_map(body, prc.extract_problem_map(body)),
            {
                str(number): problem_id
                for number, problem_id in enumerate(problem_ids[:3], 1)
            },
        )
        self.assertEqual([problem_id for problem_id, _ in shown], problem_ids[:3])

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

    def test_nonempty_run_closes_older_issues_as_superseded(self):
        listed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [
                    {"number": 7, "title": "📚 Daily LeetCode Review — 2026-09-21"},
                    {"number": 9, "title": "📚 Daily LeetCode Review — 2026-09-22"},
                    {"number": 8, "title": "Unrelated issue"},
                ]
            ),
            stderr="",
        )
        with patch.object(
            daily_issue_lifecycle.subprocess,
            "run",
            side_effect=[listed, subprocess.CompletedProcess(args=[], returncode=0)],
        ) as run:
            closed = daily_issue_lifecycle.close_stale_daily_issues(
                "owner/repo", date(2026, 9, 22), has_reviews=True, current_issue=9
            )
        self.assertEqual(closed, [7])
        close_command = run.call_args_list[1].args[0]
        self.assertEqual(close_command[:4], ["gh", "issue", "close", "7"])
        comment = close_command[close_command.index("--comment") + 1]
        self.assertEqual(comment, daily_issue_lifecycle.superseded_comment(9))
        self.assertIn("superseded by #9", comment)
        self.assertIn("review <number> <result>", comment)

    def test_current_issue_is_never_closed(self):
        listed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [{"number": 9, "title": "📚 Daily LeetCode Review — 2026-09-21"}]
            ),
            stderr="",
        )
        with patch.object(
            daily_issue_lifecycle.subprocess, "run", side_effect=[listed]
        ) as run:
            closed = daily_issue_lifecycle.close_stale_daily_issues(
                "owner/repo", date(2026, 9, 22), has_reviews=True, current_issue=9
            )
        self.assertEqual(closed, [])
        self.assertEqual(run.call_count, 1)

    def test_paused_run_keeps_older_issues_open_even_with_current_issue(self):
        with patch.object(daily_issue_lifecycle.subprocess, "run") as run:
            closed = daily_issue_lifecycle.close_stale_daily_issues(
                "owner/repo",
                date(2026, 9, 22),
                has_reviews=False,
                paused=True,
                current_issue=9,
            )
        self.assertEqual(closed, [])
        run.assert_not_called()

    def test_cli_passes_optional_current_issue(self):
        for value, expected in (("12", 12), ("", None)):
            with self.subTest(value=value):
                with (
                    patch.object(
                        daily_issue_lifecycle, "close_stale_daily_issues", return_value=[]
                    ) as close,
                    patch.object(
                        sys,
                        "argv",
                        [
                            "daily_issue_lifecycle.py",
                            "--repo",
                            "owner/repo",
                            "--today",
                            "2026-09-22",
                            "--has-reviews",
                            "true",
                            "--paused",
                            "false",
                            "--current-issue",
                            value,
                        ],
                    ),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    daily_issue_lifecycle.main()
                self.assertEqual(close.call_args.kwargs["current_issue"], expected)

    def test_issue_date_from_title(self):
        self.assertEqual(
            daily_issue_lifecycle.issue_date_from_title(
                "📚 Daily LeetCode Review — 2026-10-05"
            ),
            date(2026, 10, 5),
        )
        self.assertIsNone(daily_issue_lifecycle.issue_date_from_title("Unrelated issue"))


class WeekendConfigAndPreflightTests(unittest.TestCase):
    def test_missing_weekend_setting_defaults_to_false_everywhere(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text('{"daily_show_limit": 3, "pause_until": null}')

            for module in (review, issue_formatter, prc):
                with self.subTest(module=module.__name__):
                    with patch.object(module, "_CONFIG_PATH", config_path):
                        self.assertFalse(module._load_config()["weekend_enabled"])

            self.assertFalse(review_day_preflight.load_weekend_enabled(config_path))

    def test_invalid_weekend_setting_defaults_to_false(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text('{"weekend_enabled": "true"}')

            with patch.object(review, "_CONFIG_PATH", config_path):
                self.assertFalse(review._load_config()["weekend_enabled"])
            self.assertFalse(review_day_preflight.load_weekend_enabled(config_path))
            self.assertEqual(
                scheduler.review_date(date(2026, 10, 2), 1, "true"),  # type: ignore[arg-type]
                date(2026, 10, 5),
            )

    def test_preflight_runs_weekdays_and_obeys_weekend_setting(self):
        friday = date(2026, 10, 2)
        saturday = date(2026, 10, 3)
        sunday = date(2026, 10, 4)

        self.assertTrue(review_day_preflight.should_run(friday))
        self.assertFalse(review_day_preflight.should_run(saturday, False))
        self.assertFalse(review_day_preflight.should_run(sunday, False))
        self.assertTrue(review_day_preflight.should_run(saturday, True))
        self.assertTrue(review_day_preflight.should_run(sunday, True))

    def test_workflow_gates_review_and_issue_steps_on_preflight(self):
        workflow = (
            Path(__file__).parent / ".github" / "workflows" / "main.yml"
        ).read_text()
        self.assertIn('- cron: "0 5 * * *"', workflow)
        for step_name in (
            "Run review script",
            "Format daily review issue",
            "Create or update daily review issue",
            "Commit updated review metadata",
            "Close older daily issues",
        ):
            with self.subTest(step=step_name):
                section = workflow.split(f"- name: {step_name}", 1)[1].split(
                    "\n      - name:", 1
                )[0]
                self.assertIn(
                    "if: steps.preflight.outputs.should_run == 'true'", section
                )


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

    def test_auto_forgot_scheduling_uses_weekend_setting(self):
        today = date(2026, 10, 2)
        for weekend_enabled, expected in ((False, "2026-10-05"), (True, "2026-10-03")):
            with self.subTest(weekend_enabled=weekend_enabled):
                reviews = {
                    "problem": untouched_entry(
                        last_review="2026-09-01",
                        next_review="2026-09-02",
                        processed_submission_commits=[],
                    )
                }
                config = {
                    **CONFIG,
                    "auto_forgot_after_days": 0,
                    "system_start_date": None,
                    "weekend_enabled": weekend_enabled,
                }
                with (
                    patch.object(review, "_load_config", return_value=config),
                    patch.object(review, "_load_reviews", return_value=reviews),
                    patch.object(
                        review,
                        "sync_new_problems",
                        return_value=(reviews, [], []),
                    ),
                    patch.object(review, "_save_reviews"),
                ):
                    review.run_daily(today)

                self.assertEqual(reviews["problem"]["next_review"], expected)

    def test_rate_command_uses_weekend_setting(self):
        reviews = {"problem": untouched_entry(interval=1)}
        with (
            patch.object(
                review,
                "_load_config",
                return_value={**CONFIG, "weekend_enabled": True},
            ),
            patch.object(review, "_load_reviews", return_value=reviews),
            patch.object(review, "_save_reviews"),
        ):
            review.run_rate("problem", "Forgot", date(2026, 10, 2))

        self.assertEqual(reviews["problem"]["next_review"], "2026-10-03")

    def test_run_daily_skips_when_paused(self):
        config = {**CONFIG, "pause_until": "2026-08-20"}
        with (
            patch.object(review, "_load_config", return_value=config),
            patch.object(review, "_load_reviews") as load,
        ):
            review.run_daily(date(2026, 8, 18))
        load.assert_not_called()

    def test_pause_takes_precedence_on_enabled_weekend(self):
        saturday = date(2026, 10, 3)
        config = {
            **CONFIG,
            "pause_until": saturday.isoformat(),
            "weekend_enabled": True,
        }
        self.assertTrue(review_day_preflight.should_run(saturday, True))
        with (
            patch.object(review, "_load_config", return_value=config),
            patch.object(review, "_load_reviews") as load,
        ):
            review.run_daily(saturday)
        load.assert_not_called()

    def test_load_config_missing_file_returns_defaults(self):
        with patch.object(review, "_CONFIG_PATH", Path("/nonexistent/config.json")):
            config = review._load_config()
        self.assertIsNone(config["system_start_date"])
        self.assertEqual(config["daily_show_limit"], 3)
        self.assertFalse(config["weekend_enabled"])


class SchedulerAndCommentTests(unittest.TestCase):
    def test_review_dates_roll_weekends_forward_to_monday(self):
        cases = [
            (date(2026, 9, 25), 1, date(2026, 9, 28)),
            (date(2026, 9, 26), 1, date(2026, 9, 28)),
            (date(2026, 9, 27), 1, date(2026, 9, 28)),
        ]
        for start, interval, expected in cases:
            with self.subTest(start=start):
                self.assertEqual(scheduler.review_date(start, interval), expected)

    def test_enabled_review_dates_preserve_saturday_and_sunday(self):
        cases = [
            (date(2026, 10, 2), 1, date(2026, 10, 3)),
            (date(2026, 10, 2), 2, date(2026, 10, 4)),
        ]
        for start, interval, expected in cases:
            with self.subTest(interval=interval):
                self.assertEqual(
                    scheduler.review_date(start, interval, True),
                    expected,
                )

    def test_new_ratings_and_reset_use_enabled_weekends(self):
        self.assertEqual(
            scheduler.new_entry(date(2026, 10, 2), True)["next_review"],
            "2026-10-03",
        )
        rating_cases = [
            ("Easy", date(2026, 9, 30), "2026-10-03"),
            ("Medium", date(2026, 10, 2), "2026-10-04"),
            ("Forgot", date(2026, 10, 2), "2026-10-03"),
        ]
        for rating, today, expected in rating_cases:
            with self.subTest(rating=rating):
                result = scheduler.schedule(
                    untouched_entry(interval=1),
                    rating,
                    today,
                    True,
                )
                self.assertEqual(result["next_review"], expected)

        reset = scheduler.reset_entry(
            untouched_entry(review_count=2),
            date(2026, 10, 2),
            True,
        )
        self.assertEqual(reset["next_review"], "2026-10-03")

    def test_due_and_overdue_calculations_respect_weekend_setting(self):
        saturday_entry = untouched_entry(next_review="2026-10-03")
        sunday_entry = untouched_entry(next_review="2026-10-04")

        self.assertFalse(
            scheduler.is_due(saturday_entry, date(2026, 10, 3), False)
        )
        self.assertTrue(
            scheduler.is_due(saturday_entry, date(2026, 10, 3), True)
        )
        self.assertFalse(
            scheduler.is_due(sunday_entry, date(2026, 10, 4), False)
        )
        self.assertTrue(
            scheduler.is_due(sunday_entry, date(2026, 10, 4), True)
        )
        self.assertEqual(
            scheduler.days_overdue(saturday_entry, date(2026, 10, 5), False),
            0,
        )
        self.assertEqual(
            scheduler.days_overdue(saturday_entry, date(2026, 10, 5), True),
            2,
        )
        self.assertEqual(saturday_entry["next_review"], "2026-10-03")

    def test_stored_weekend_dates_are_due_not_overdue_on_monday(self):
        monday = date(2026, 9, 28)
        for next_review in ("2026-09-26", "2026-09-27"):
            with self.subTest(next_review=next_review):
                entry = untouched_entry(next_review=next_review)
                self.assertTrue(scheduler.is_due(entry, monday))
                self.assertEqual(scheduler.days_overdue(entry, monday), 0)

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
            [(1, "Easy")],
            {"1": "problem"},
            reviews,
            date(2026, 9, 22),
            comment_id=123,
        )
        self.assertEqual(errors, [])
        self.assertEqual(results[0]["rating"], "Easy")
        self.assertEqual(reviews["problem"]["review_count"], 1)
        self.assertEqual(reviews["problem"]["processed_rating_comment_ids"], ["123"])

        repeated_results, repeated_errors = prc.process_commands(
            [(1, "Easy")],
            {"1": "problem"},
            reviews,
            date(2026, 9, 22),
            comment_id=123,
        )
        self.assertEqual(repeated_results, [])
        self.assertEqual(repeated_errors, [])
        self.assertEqual(reviews["problem"]["review_count"], 1)

    def test_comment_ratings_and_reset_use_weekend_setting(self):
        reviews = {
            "easy": untouched_entry(interval=3),
            "medium": untouched_entry(interval=1),
            "forgot": untouched_entry(interval=1),
            "reset": untouched_entry(interval=1, review_count=2),
        }
        results, errors = prc.process_commands(
            [(1, "Easy"), (2, "Medium"), (3, "Forgot"), (4, "Reset")],
            {"1": "easy", "2": "medium", "3": "forgot", "4": "reset"},
            reviews,
            date(2026, 10, 2),
            weekend_enabled=True,
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 4)
        self.assertEqual(reviews["easy"]["next_review"], "2026-10-10")
        self.assertEqual(reviews["medium"]["next_review"], "2026-10-04")
        self.assertEqual(reviews["forgot"]["next_review"], "2026-10-03")
        self.assertEqual(reviews["reset"]["next_review"], "2026-10-03")

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

    def test_deferred_rating_uses_full_problem_map(self):
        reviews = {"deferred-problem": untouched_entry()}

        results, errors = prc.process_commands(
            [(6, "Easy")],
            {"6": "deferred-problem"},
            reviews,
            date(2026, 9, 22),
        )

        self.assertEqual(errors, [])
        self.assertEqual(results[0]["num"], 6)
        self.assertEqual(results[0]["name"], "Deferred Problem")
        self.assertEqual(reviews["deferred-problem"]["review_count"], 1)

    def test_deferred_reset_uses_full_problem_map(self):
        reviews = {"deferred-problem": untouched_entry(review_count=2)}

        results, errors = prc.process_commands(
            [(6, "Reset")],
            {"6": "deferred-problem"},
            reviews,
            date(2026, 9, 22),
        )

        self.assertEqual(errors, [])
        self.assertEqual(results[0]["num"], 6)
        self.assertEqual(results[0]["rating"], "Reset")
        self.assertEqual(reviews["deferred-problem"]["review_count"], 0)

    def test_deferred_problem_is_not_required_for_completion(self):
        today = date(2026, 9, 22)
        reviews = {
            "primary": untouched_entry(last_review=today.isoformat()),
            "deferred": untouched_entry(),
        }

        self.assertTrue(
            prc.all_required_problems_reviewed(reviews, {"1": "primary"}, today)
        )

    def test_primary_problem_remains_required_for_completion(self):
        today = date(2026, 9, 22)
        reviews = {
            "primary": untouched_entry(),
            "deferred": untouched_entry(last_review=today.isoformat()),
        }

        self.assertFalse(
            prc.all_required_problems_reviewed(reviews, {"1": "primary"}, today)
        )

    def test_older_issue_uses_full_problem_map_for_completion(self):
        problem_map = {"1": "first", "2": "second"}
        issue_body = '<!-- problem-map: {"1": "first", "2": "second"} -->'
        required_map = prc.extract_required_problem_map(issue_body, problem_map)
        today = date(2026, 9, 22)
        reviews = {
            "first": untouched_entry(last_review=today.isoformat()),
            "second": untouched_entry(),
        }

        self.assertEqual(required_map, problem_map)
        self.assertFalse(prc.all_required_problems_reviewed(reviews, required_map, today))

    def test_intervals_round_halves_up(self):
        cases = [
            # 3 * 1.5 = 4.5; round() gave 4
            ("Medium", untouched_entry(interval=3), 5),
            # 2 * 2.25 = 4.5
            ("Easy", untouched_entry(interval=2, ease_factor=2.1), 5),
            # 75 * 1.38 is 103.49999999999999 as a float
            ("Easy", untouched_entry(interval=75, ease_factor=1.23), 104),
        ]
        for rating, entry, expected in cases:
            with self.subTest(rating=rating, interval=entry["interval"]):
                result = scheduler.schedule(entry, rating, date(2026, 10, 6), True)
                self.assertEqual(result["interval"], expected)

    def test_reset_keeps_completion_markers_and_clears_last_rated(self):
        entry = untouched_entry(
            processed_rating_comment_ids=["1"],
            completed_in_issues=[64],
            last_rated="2026-10-05",
        )
        result = scheduler.reset_entry(entry, date(2026, 10, 6))
        self.assertEqual(result["completed_in_issues"], [64])
        self.assertIsNot(result["completed_in_issues"], entry["completed_in_issues"])
        self.assertEqual(result["processed_rating_comment_ids"], ["1"])
        self.assertNotIn("last_rated", result)

    def test_review_on_or_after_issue_date_completes_the_issue(self):
        # Reviews that continue past midnight still count for the issue's date.
        reviews = {"problem": untouched_entry(last_review="2026-10-06")}
        required = {"1": "problem"}
        self.assertTrue(
            prc.all_required_problems_reviewed(reviews, required, date(2026, 10, 5))
        )
        self.assertFalse(
            prc.all_required_problems_reviewed(reviews, required, date(2026, 10, 7))
        )

    def test_removed_problem_counts_as_complete(self):
        today = date(2026, 10, 6)
        reviews = {
            "kept": untouched_entry(last_review="2026-10-06"),
            "gone": untouched_entry(),
        }
        required = {"1": "kept", "2": "gone"}
        self.assertFalse(prc.all_required_problems_reviewed(reviews, required, today, 70))
        prc.process_commands(
            [(2, "Remove")], required, reviews, today, issue_date=today, issue_number=70
        )
        self.assertTrue(prc.all_required_problems_reviewed(reviews, required, today, 70))

    def test_reset_problem_counts_as_complete_and_can_be_rated_again(self):
        today = date(2026, 10, 6)
        reviews = {
            "problem": untouched_entry(
                last_rated="2026-10-06",
                last_review="2026-10-06",
                review_count=3,
                completed_in_issues=[69],
            )
        }
        required = {"1": "problem"}
        prc.process_commands(
            [(1, "Reset")], required, reviews, today, comment_id=1, issue_date=today, issue_number=70
        )
        entry = reviews["problem"]
        self.assertIsNone(entry["last_review"])
        self.assertNotIn("last_rated", entry)
        self.assertEqual(entry["completed_in_issues"], [69, 70])
        self.assertTrue(prc.all_required_problems_reviewed(reviews, required, today, 70))
        self.assertFalse(prc.all_required_problems_reviewed(reviews, required, today, 71))

        results, errors = prc.process_commands(
            [(1, "Easy")], required, reviews, today, comment_id=2, issue_date=today, issue_number=70
        )
        self.assertEqual(errors, [])
        self.assertNotIn("skipped", results[0])
        self.assertEqual(reviews["problem"]["review_count"], 1)

    def test_rating_same_problem_in_two_issues_runs_sm2_once(self):
        today = date(2026, 10, 6)
        yesterday_issue = ({"4": "shared"}, date(2026, 10, 5), 69)
        today_issue = ({"1": "shared"}, today, 70)
        for first, second in ((yesterday_issue, today_issue), (today_issue, yesterday_issue)):
            with self.subTest(first_issue=first[2]):
                reviews = {"shared": untouched_entry(next_review="2026-10-05")}
                for comment_id, (problem_map, issue_date, issue_number) in enumerate(
                    (first, second), start=1
                ):
                    results, errors = prc.process_commands(
                        [(int(next(iter(problem_map))), "Easy")],
                        problem_map,
                        reviews,
                        today,
                        comment_id=comment_id,
                        issue_date=issue_date,
                        issue_number=issue_number,
                    )
                self.assertEqual(errors, [])
                self.assertIn("already rated on 2026-10-06", results[0]["skipped"])
                self.assertIn("⏭️ **Skipped**", prc.build_reply(results, errors))
                entry = reviews["shared"]
                self.assertEqual(entry["review_count"], 1)
                self.assertEqual(entry["interval"], 3)
                self.assertEqual(sorted(entry["completed_in_issues"]), [69, 70])

    def test_rating_applies_when_last_rating_is_older_than_issue(self):
        reviews = {
            "problem": untouched_entry(
                last_rated="2026-10-05",
                last_review="2026-10-05",
                next_review="2026-10-06",
                review_count=1,
            )
        }
        results, errors = prc.process_commands(
            [(1, "Medium")], {"1": "problem"}, reviews, date(2026, 10, 6)
        )
        self.assertEqual(errors, [])
        self.assertNotIn("skipped", results[0])
        self.assertEqual(reviews["problem"]["review_count"], 2)
        self.assertEqual(reviews["problem"]["last_rated"], "2026-10-06")

    def test_remove_then_rate_in_same_comment_reports_already_removed(self):
        reviews = {"problem": untouched_entry()}
        results, errors = prc.process_commands(
            [(1, "Remove"), (1, "Easy")], {"1": "problem"}, reviews, date(2026, 10, 6), comment_id=9
        )
        self.assertEqual(errors, [])
        self.assertEqual(results[1]["skipped"], "already removed earlier in this comment")
        self.assertNotIn("problem", reviews)

    def test_second_command_for_problem_in_same_comment_is_reported(self):
        reviews = {"problem": untouched_entry()}
        results, errors = prc.process_commands(
            [(1, "Easy"), (1, "Medium")], {"1": "problem"}, reviews, date(2026, 10, 6), comment_id=9
        )
        self.assertEqual(errors, [])
        self.assertEqual(results[1]["skipped"], "already handled earlier in this comment")
        self.assertEqual(reviews["problem"]["review_count"], 1)
        reply = prc.build_reply(results, errors)
        self.assertTrue(reply.startswith("✅ **Review updated**"))
        self.assertIn(
            "1. **Problem** (Medium): already handled earlier in this comment", reply
        )


class ReviewCommentMainTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.reviews_path = root / "reviews.json"
        self.config_path = root / "config.json"
        self.output_path = root / "output"
        self.config_path.write_text(json.dumps({"pause_until": None, "weekend_enabled": False}))

    def write_reviews(self, reviews: dict) -> None:
        self.reviews_path.write_text(json.dumps(reviews))

    def reviews(self) -> dict:
        return json.loads(self.reviews_path.read_text())

    def config(self) -> dict:
        return json.loads(self.config_path.read_text())

    def run_main(
        self,
        comment: str,
        issue: dict | None = None,
        *,
        today: date = date(2026, 10, 6),
        comment_id: int = 500,
        fetch_error: Exception | None = None,
        post_side_effect=None,
    ) -> SimpleNamespace:
        self.output_path.write_text("")
        fetch = Mock(side_effect=fetch_error, return_value=issue)
        post = Mock(side_effect=post_side_effect)
        stdout = io.StringIO()
        exit_code = 0
        with (
            patch.object(prc, "_REVIEWS_PATH", self.reviews_path),
            patch.object(prc, "_CONFIG_PATH", self.config_path),
            patch.object(prc, "fetch_issue", fetch),
            patch.object(prc, "post_comment", post),
            patch.object(prc, "local_today", return_value=today) as local_today,
            patch.dict(
                os.environ,
                {"REVIEW_COMMENT_BODY": comment, "GITHUB_OUTPUT": str(self.output_path)},
            ),
            patch.object(
                sys,
                "argv",
                [
                    "process_review_comment.py",
                    "--issue-number",
                    "64",
                    "--comment-id",
                    str(comment_id),
                    "--repo",
                    "owner/repo",
                ],
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            try:
                prc.main()
            except SystemExit as exc:
                exit_code = exc.code
        return SimpleNamespace(
            exit_code=exit_code,
            output=self.output_path.read_text(),
            stdout=stdout.getvalue(),
            fetch=fetch,
            post=post,
            local_today=local_today,
        )

    def test_review_and_pause_in_one_comment_are_both_applied_with_one_reply(self):
        self.config_path.write_text(json.dumps({"pause_until": None, "timezone": "Asia/Tokyo"}))
        self.write_reviews({"first": untouched_entry(next_review="2026-10-06")})
        result = self.run_main(
            "review 1 easy\npause 3", daily_issue("2026-10-06", {"1": "first"})
        )
        self.assertEqual(result.exit_code, 0)
        result.local_today.assert_called_once_with("Asia/Tokyo")
        self.assertEqual(self.config()["pause_until"], "2026-10-09")
        self.assertEqual(self.config()["timezone"], "Asia/Tokyo")
        self.assertEqual(self.reviews()["first"]["review_count"], 1)
        result.post.assert_called_once()
        reply = result.post.call_args.args[2]
        self.assertIn("✅ **Review updated**", reply)
        self.assertIn("⏸️ **Reviews paused**", reply)
        self.assertEqual(result.output, "all_reviewed=true\n")

    def test_failed_reply_is_a_warning_after_saving_and_reporting(self):
        self.write_reviews({"first": untouched_entry()})
        output_when_posting = []

        def failing_post(*_args):
            output_when_posting.append(self.output_path.read_text())
            raise RuntimeError("HTTP Error 502")

        result = self.run_main(
            "review 1 medium",
            daily_issue("2026-10-06", {"1": "first"}),
            post_side_effect=failing_post,
        )
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(output_when_posting, ["all_reviewed=true\n"])
        self.assertIn("::warning::Could not post the reply comment: HTTP Error 502", result.stdout)
        self.assertEqual(self.reviews()["first"]["review_count"], 1)

    def test_rerun_of_processed_comment_still_reports_all_reviewed(self):
        self.write_reviews({"first": untouched_entry()})
        issue = daily_issue("2026-10-06", {"1": "first"})
        self.run_main("review 1 easy", issue)
        rerun = self.run_main("review 1 easy", issue)
        rerun.post.assert_not_called()
        self.assertEqual(rerun.output, "all_reviewed=true\n")
        self.assertEqual(self.reviews()["first"]["review_count"], 1)

    def test_comment_without_commands_reports_not_reviewed(self):
        self.write_reviews({})
        result = self.run_main("Thanks!")
        result.fetch.assert_not_called()
        result.post.assert_not_called()
        self.assertEqual(result.output, "all_reviewed=false\n")

    def test_reviews_after_midnight_complete_the_issue(self):
        # Issue #64: problem 1 was reviewed on the issue date (before completion
        # markers existed) and problem 2 after midnight UTC.
        self.write_reviews(
            {
                "first": untouched_entry(last_review="2026-10-05", next_review="2026-10-08"),
                "second": untouched_entry(next_review="2026-10-05"),
            }
        )
        result = self.run_main(
            "review 2 easy",
            daily_issue("2026-10-05", {"1": "first", "2": "second"}),
            today=date(2026, 10, 6),
        )
        self.assertEqual(result.output, "all_reviewed=true\n")
        self.assertEqual(self.reviews()["second"]["completed_in_issues"], [64])
        self.assertEqual(self.reviews()["second"]["last_rated"], "2026-10-06")

    def test_issue_without_problem_map_replies_with_error_and_keeps_pause(self):
        self.write_reviews({})
        issue = {"title": "📚 Daily LeetCode Review — 2026-10-06", "body": "⏸️ Reviews are paused"}
        result = self.run_main("pause 2\nreview 1 easy", issue)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(self.config()["pause_until"], "2026-10-08")
        reply = result.post.call_args.args[2]
        self.assertIn("⏸️ **Reviews paused**", reply)
        self.assertIn("This issue has no problem list", reply)
        self.assertEqual(result.output, "all_reviewed=false\n")

    def test_fetch_failure_fails_after_saving_pause_and_reporting(self):
        self.write_reviews({})
        result = self.run_main(
            "pause 2\nreview 1 easy", fetch_error=RuntimeError("HTTP Error 500")
        )
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(self.config()["pause_until"], "2026-10-08")
        self.assertEqual(result.output, "all_reviewed=false\n")
        self.assertIn("no reviews were applied", result.post.call_args.args[2])


class TimezoneTests(unittest.TestCase):
    NOW = datetime(2026, 10, 5, 20, 30, tzinfo=timezone.utc)

    def test_local_today_uses_configured_timezone(self):
        self.assertEqual(scheduler.local_today(None, self.NOW), date(2026, 10, 5))
        self.assertEqual(scheduler.local_today("Asia/Tokyo", self.NOW), date(2026, 10, 6))
        self.assertEqual(
            scheduler.local_today(
                "America/Los_Angeles", datetime(2026, 10, 6, 3, 0, tzinfo=timezone.utc)
            ),
            date(2026, 10, 5),
        )

    def test_invalid_timezone_falls_back_to_utc_with_warning(self):
        for name in ("Mars/Olympus", "../etc", 9):
            with self.subTest(name=name):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    self.assertEqual(scheduler.local_today(name, self.NOW), date(2026, 10, 5))
                self.assertIn("using UTC", stderr.getvalue())

    def test_preflight_writes_today_in_configured_timezone(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            output_path = Path(directory) / "output"
            config_path.write_text('{"timezone": "Asia/Tokyo", "weekend_enabled": false}')
            self.assertEqual(review_day_preflight.load_timezone(config_path), "Asia/Tokyo")
            with (
                patch.object(
                    review_day_preflight, "local_today", return_value=date(2026, 10, 6)
                ) as local_today,
                patch.object(
                    sys,
                    "argv",
                    [
                        "review_day_preflight.py",
                        "--config",
                        str(config_path),
                        "--github-output",
                        str(output_path),
                    ],
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                review_day_preflight.main()
            local_today.assert_called_once_with("Asia/Tokyo")
            self.assertEqual(output_path.read_text(), "should_run=true\ntoday=2026-10-06\n")

    def test_daily_scripts_use_configured_timezone_without_a_date(self):
        config = {**CONFIG, "pause_until": "2026-12-31", "timezone": "Asia/Tokyo"}
        with (
            patch.object(review, "_load_config", return_value=config),
            patch.object(review, "local_today", return_value=date(2026, 10, 6)) as local_today,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            review.run_daily()
        local_today.assert_called_once_with("Asia/Tokyo")

        with (
            patch.object(issue_formatter, "_load_config", return_value=config),
            patch.object(
                issue_formatter, "local_today", return_value=date(2026, 10, 6)
            ) as local_today,
        ):
            body, _ = issue_formatter.build_issue_body()
        local_today.assert_called_once_with("Asia/Tokyo")
        self.assertIn("2026-10-06", body)

    def test_review_cli_passes_today_override(self):
        with (
            patch.object(review, "run_daily") as run_daily,
            patch.object(sys, "argv", ["review.py", "--today", "2026-10-06"]),
        ):
            review.main()
        run_daily.assert_called_once_with(date(2026, 10, 6))


class WorkflowSafetyTests(unittest.TestCase):
    WORKFLOWS = Path(__file__).parent / ".github" / "workflows"

    @staticmethod
    def job_header(workflow: str) -> str:
        return workflow.split("    steps:", 1)[0]

    @staticmethod
    def step(workflow: str, name: str) -> str:
        return workflow.split(f"- name: {name}", 1)[1].split("\n      - name:", 1)[0]

    def test_comment_workflow_only_processes_owner_commands_on_daily_issues(self):
        workflow = (self.WORKFLOWS / "process-review-comment.yml").read_text()
        header = self.job_header(workflow)
        self.assertIn("github.event.comment.author_association == 'OWNER'", header)
        self.assertIn(
            "startsWith(github.event.issue.title, '📚 Daily LeetCode Review')", header
        )
        # Closed issues still accept reviews; only closing requires an open issue.
        self.assertNotIn("github.event.issue.state", header)
        self.assertIn(
            "if: steps.review.outputs.all_reviewed == 'true' && "
            "github.event.issue.state == 'open'",
            self.step(workflow, "Close issue if all problems reviewed"),
        )
        self.assertIn(
            "if: ${{ !cancelled() }}", self.step(workflow, "Commit updated review metadata")
        )

    def test_metadata_workflows_share_a_queue_and_retry_pushes(self):
        for name in ("main.yml", "process-review-comment.yml"):
            with self.subTest(workflow=name):
                workflow = (self.WORKFLOWS / name).read_text()
                self.assertIn(
                    "    concurrency:\n"
                    "      group: review-metadata\n"
                    "      cancel-in-progress: false\n"
                    "      queue: max\n",
                    self.job_header(workflow),
                )
                self.assertIn(
                    "ref: ${{ github.ref }}", self.step(workflow, "Checkout repository")
                )
                commit = self.step(workflow, "Commit updated review metadata")
                self.assertIn("git pull --rebase && git push", commit)
                self.assertNotIn("\n          git push\n", commit)

    def test_daily_workflow_commits_before_closing_older_issues(self):
        workflow = (self.WORKFLOWS / "main.yml").read_text()
        self.assertLess(
            workflow.index("- name: Commit updated review metadata"),
            workflow.index("- name: Close older daily issues"),
        )
        self.assertIn(
            '--current-issue "${{ steps.issue.outputs.number }}"',
            self.step(workflow, "Close older daily issues"),
        )
        self.assertIn(
            'python scripts/review.py --today "$TODAY"',
            self.step(workflow, "Run review script"),
        )


if __name__ == "__main__":
    unittest.main()
