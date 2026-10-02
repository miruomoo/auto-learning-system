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
            "Close older daily issues on an empty day",
            "Commit updated review metadata",
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


if __name__ == "__main__":
    unittest.main()
