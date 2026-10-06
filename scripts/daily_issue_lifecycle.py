"""Close older daily-review issues once today's issue replaces them."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date

DAILY_ISSUE_PREFIX = "📚 Daily LeetCode Review — "
CLOSING_COMMENT = (
    "🤖 Closing this older daily review issue because today's run has no scheduled reviews."
)


def superseded_comment(current_issue: int) -> str:
    """Return the closing comment for an older issue replaced by *current_issue*."""
    return (
        f"🤖 Closing this older daily review issue because it was superseded by "
        f"#{current_issue}. You can still comment `review <number> <result>` here "
        f"to record reviews for the problems listed above."
    )


def issue_date_from_title(title: str) -> date | None:
    """Return the date in a daily review issue title, or None for other issues."""
    if not title.startswith(DAILY_ISSUE_PREFIX):
        return None
    try:
        return date.fromisoformat(title.removeprefix(DAILY_ISSUE_PREFIX)[:10])
    except ValueError:
        return None


def older_daily_issues(issues: list[dict], today: date) -> list[int]:
    """Return older matching open issue numbers in deterministic order."""
    matches = []
    for issue in issues:
        issue_date = issue_date_from_title(issue.get("title", ""))
        if issue_date is not None and issue_date < today:
            matches.append(int(issue["number"]))
    return sorted(matches)


def close_stale_daily_issues(
    repo: str,
    today: date,
    has_reviews: bool,
    paused: bool = False,
    current_issue: int | None = None,
) -> list[int]:
    """
    Close older open daily issues.

    On an empty day they are closed because nothing is scheduled.  On a day
    with reviews they are closed as superseded by *current_issue*.  Nothing is
    closed while reviews are paused.
    """
    if paused or (has_reviews and current_issue is None):
        return []
    comment = superseded_comment(current_issue) if has_reviews else CLOSING_COMMENT
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
    issue_numbers = [
        number
        for number in older_daily_issues(json.loads(result.stdout), today)
        if number != current_issue
    ]
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
                comment,
            ],
            check=True,
        )
    return issue_numbers


def _optional_issue_number(value: str) -> int | None:
    return int(value) if value.strip() else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--today", required=True, type=date.fromisoformat)
    parser.add_argument("--has-reviews", required=True, choices=["true", "false"])
    parser.add_argument("--paused", required=True, choices=["true", "false"])
    parser.add_argument(
        "--current-issue",
        type=_optional_issue_number,
        default=None,
        help="Number of today's daily issue; older issues are closed as superseded by it",
    )
    args = parser.parse_args()
    closed = close_stale_daily_issues(
        args.repo,
        args.today,
        has_reviews=args.has_reviews == "true",
        paused=args.paused == "true",
        current_issue=args.current_issue,
    )
    print(f"Closed {len(closed)} older daily review issue(s).")


if __name__ == "__main__":
    main()
