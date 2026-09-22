"""Close older daily-review issues when today's review set is empty."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date

DAILY_ISSUE_PREFIX = "📚 Daily LeetCode Review — "
CLOSING_COMMENT = (
    "🤖 Closing this older daily review issue because today's run has no scheduled reviews."
)


def _issue_date(title: str) -> date | None:
    if not title.startswith(DAILY_ISSUE_PREFIX):
        return None
    try:
        return date.fromisoformat(title.removeprefix(DAILY_ISSUE_PREFIX))
    except ValueError:
        return None


def older_daily_issues(issues: list[dict], today: date) -> list[int]:
    """Return older matching open issue numbers in deterministic order."""
    matches = []
    for issue in issues:
        issue_date = _issue_date(issue.get("title", ""))
        if issue_date is not None and issue_date < today:
            matches.append(int(issue["number"]))
    return sorted(matches)


def close_stale_daily_issues(repo: str, today: date, has_reviews: bool) -> list[int]:
    """Close stale daily issues only when the current run has no reviews."""
    if has_reviews:
        return []

    result = subprocess.run(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "1000",
            "--json",
            "number,title",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    issue_numbers = older_daily_issues(json.loads(result.stdout), today)
    for issue_number in issue_numbers:
        subprocess.run(
            [
                "gh",
                "issue",
                "close",
                str(issue_number),
                "--repo",
                repo,
                "--comment",
                CLOSING_COMMENT,
            ],
            check=True,
        )
    return issue_numbers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--today", required=True, type=date.fromisoformat)
    parser.add_argument("--has-reviews", required=True, choices=["true", "false"])
    args = parser.parse_args()
    closed = close_stale_daily_issues(
        args.repo,
        args.today,
        has_reviews=args.has_reviews == "true",
    )
    print(f"Closed {len(closed)} older daily review issue(s).")


if __name__ == "__main__":
    main()
