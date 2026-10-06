"""
Process a ``review <number> <result>`` comment posted on a daily review issue.

Usage (called by the GitHub Actions workflow)
---------------------------------------------
    python scripts/process_review_comment.py \
        --issue-number  <N>          \
        --comment-body  "<text>"     \
        --comment-id    <C>          \
        --repo          owner/repo

The script:
1. Parses the ``pause <days>`` and ``review <n> <result>`` commands in the comment.
2. Fetches the issue via the GitHub API to extract its date and problem-map.
3. Applies the pause and the review commands to config.json / reviews.json.
4. Writes ``all_reviewed`` to ``GITHUB_OUTPUT``.
5. Posts one reply comment with the results (a failed post is only a warning).

Environment variables
---------------------
GITHUB_TOKEN  – required for API calls.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib import request, error as urllib_error

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from daily_issue_lifecycle import issue_date_from_title  # noqa: E402
from scheduler import local_today, reset_entry, schedule  # noqa: E402

_REPO_ROOT = Path(__file__).parent.parent
_REVIEWS_PATH = _REPO_ROOT / ".leetcode-review" / "reviews.json"
_CONFIG_PATH = _REPO_ROOT / ".leetcode-review" / "config.json"

# Regex for one review command (case-insensitive, flexible whitespace)
_REVIEW_RE = re.compile(
    r"^\s*review\s+(\d+)\s+(easy|medium|forgot|reset|remove)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Regex for pause command: pause <days> (1–365)
_PAUSE_RE = re.compile(
    r"^\s*pause\s+(\d+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Regex to extract the problem-map JSON hidden in the issue body
_MAP_RE = re.compile(r"<!--\s*problem-map:\s*(\{.*?\})\s*-->", re.DOTALL)
_REQUIRED_MAP_RE = re.compile(
    r"<!--\s*required-problem-map:\s*(\{.*?\})\s*-->", re.DOTALL
)

_VALID_RESULTS = {"easy", "medium", "forgot", "reset", "remove"}
_RESULT_LABEL = {"easy": "Easy", "medium": "Medium", "forgot": "Forgot", "reset": "Reset", "remove": "Remove"}
_RATINGS = {"Easy", "Medium", "Forgot"}

# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

_GH_API = "https://api.github.com"


def _gh_headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    return headers


def _api_get(url: str) -> dict:
    req = request.Request(url, headers=_gh_headers())
    with request.urlopen(req) as resp:
        return json.loads(resp.read())


def _api_post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = request.Request(url, data=data, headers=_gh_headers(), method="POST")
    with request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_issue(repo: str, issue_number: int) -> dict:
    url = f"{_GH_API}/repos/{repo}/issues/{issue_number}"
    return _api_get(url)


def post_comment(repo: str, issue_number: int, body: str) -> None:
    url = f"{_GH_API}/repos/{repo}/issues/{issue_number}/comments"
    _api_post(url, {"body": body})


# ---------------------------------------------------------------------------
# reviews.json helpers
# ---------------------------------------------------------------------------


def _load_reviews() -> dict:
    if _REVIEWS_PATH.exists():
        with _REVIEWS_PATH.open() as fh:
            return json.load(fh)
    return {}


def _save_reviews(reviews: dict) -> None:
    _REVIEWS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _REVIEWS_PATH.open("w") as fh:
        json.dump(reviews, fh, indent=2, sort_keys=True)
        fh.write("\n")


# ---------------------------------------------------------------------------
# config.json helpers
# ---------------------------------------------------------------------------


def _load_config() -> dict:
    defaults: dict = {"pause_until": None, "weekend_enabled": False}
    if not _CONFIG_PATH.exists():
        return defaults
    try:
        with _CONFIG_PATH.open() as fh:
            data = json.load(fh)
        config = {**defaults, **data}
        config["weekend_enabled"] = data.get("weekend_enabled") is True
        return config
    except (json.JSONDecodeError, OSError):
        return defaults


def _save_config(config: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _CONFIG_PATH.open("w") as fh:
        json.dump(config, fh, indent=2, sort_keys=True)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_commands(comment_body: str) -> list[tuple[int, str]]:
    """
    Return a list of (problem_number, rating_str) tuples found in the comment.

    rating_str is title-cased ("Easy" / "Medium" / "Forgot").
    """
    commands = []
    for match in _REVIEW_RE.finditer(comment_body):
        num = int(match.group(1))
        rating = _RESULT_LABEL[match.group(2).lower()]
        commands.append((num, rating))
    return commands


def parse_pause_command(comment_body: str) -> int | None:
    """
    Return the number of days from a ``pause <days>`` command, or None if not present.

    If multiple pause commands appear, the first one wins.
    Days are clamped to [1, 365].
    """
    m = _PAUSE_RE.search(comment_body)
    if not m:
        return None
    days = int(m.group(1))
    return max(1, min(365, days))


def extract_problem_map(issue_body: str) -> dict[str, str]:
    """Extract the ``{num: problem_id}`` mapping embedded in the issue body."""
    m = _MAP_RE.search(issue_body)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


def extract_required_problem_map(
    issue_body: str, problem_map: dict[str, str]
) -> dict[str, str]:
    """Extract required problems, falling back to the full map for older issues."""
    m = _REQUIRED_MAP_RE.search(issue_body)
    if not m:
        return problem_map
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return problem_map


def problem_completed_for_issue(
    entry: dict | None, issue_date: date, issue_number: int | None = None
) -> bool:
    """
    Return whether a problem no longer needs a review for an issue.

    A problem is complete when it was removed from the review pool, when a
    comment on this issue rated or reset it (``completed_in_issues``), or when
    it was reviewed on or after the issue's date, e.g. from another issue.
    """
    if entry is None:
        return True
    completed_in = entry.get("completed_in_issues")
    if issue_number is not None and isinstance(completed_in, list) and issue_number in completed_in:
        return True
    last_review = entry.get("last_review")
    return isinstance(last_review, str) and last_review >= issue_date.isoformat()


def all_required_problems_reviewed(
    reviews: dict,
    required_problem_map: dict[str, str],
    issue_date: date,
    issue_number: int | None = None,
) -> bool:
    """Return whether every required problem of the issue dated *issue_date* is complete."""
    return all(
        problem_completed_for_issue(reviews.get(problem_id), issue_date, issue_number)
        for problem_id in required_problem_map.values()
    )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _display_name(problem_id: str) -> str:
    return problem_id.replace("-", " ").title()


def _format_date(d: date) -> str:
    return d.strftime("%B %-d, %Y")


def _available_list(problem_map: dict[str, str]) -> str:
    lines = []
    for k in sorted(problem_map, key=int):
        lines.append(f"{k}. {_display_name(problem_map[k])}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------


def _record_completion(
    entry: dict, issue_number: int | None, comment_marker: str | None
) -> None:
    if issue_number is not None:
        completed_in = entry.setdefault("completed_in_issues", [])
        if issue_number not in completed_in:
            completed_in.append(issue_number)
    if comment_marker is not None:
        entry.setdefault("processed_rating_comment_ids", []).append(comment_marker)


def process_commands(
    commands: list[tuple[int, str]],
    problem_map: dict[str, str],
    reviews: dict,
    today: date,
    comment_id: int | None = None,
    weekend_enabled: bool = False,
    issue_date: date | None = None,
    issue_number: int | None = None,
) -> tuple[list[dict], list[str]]:
    """
    Apply each command to *reviews* (mutated in place).

    *today* is the date a rating is recorded on; *issue_date* is the date of
    the issue the comment was posted on (defaults to *today*).  An Easy,
    Medium or Forgot rating is skipped when the problem was already rated on
    or after *issue_date*, so reviewing a problem in two issues does not run
    SM-2 twice.  Only the first command for a problem in a comment is applied.

    Returns:
        results  – list of result dicts; skipped commands carry a ``skipped`` reason
        errors   – list of error message strings
    """
    if issue_date is None:
        issue_date = today
    results: list[dict] = []
    errors: list[str] = []
    comment_marker = str(comment_id) if comment_id is not None else None
    handled_in_comment: set[str] = set()
    removed_in_comment: set[str] = set()

    for num, rating in commands:
        key = str(num)
        if key not in problem_map:
            errors.append(
                f"❌ **Unable to process review**\n\n"
                f"Problem #{num} does not exist in this issue's review list.\n\n"
                f"**Available problems:**\n{_available_list(problem_map)}"
            )
            continue

        problem_id = problem_map[key]
        result = {"num": num, "name": _display_name(problem_id), "rating": rating}
        if problem_id in removed_in_comment:
            results.append({**result, "skipped": "already removed earlier in this comment"})
            continue
        if problem_id in handled_in_comment:
            results.append({**result, "skipped": "already handled earlier in this comment"})
            continue

        if problem_id not in reviews:
            errors.append(
                f"❌ **Problem not found in reviews.json**\n\n"
                f"Problem #{num} (`{problem_id}`) is not tracked."
            )
            continue

        processed_comments = reviews[problem_id].get("processed_rating_comment_ids", [])
        if comment_marker is not None and comment_marker in processed_comments:
            continue

        if rating == "Remove":
            del reviews[problem_id]
            removed_in_comment.add(problem_id)
            results.append(result)
            continue

        handled_in_comment.add(problem_id)
        last_rated = reviews[problem_id].get("last_rated")
        if (
            rating in _RATINGS
            and isinstance(last_rated, str)
            and last_rated >= issue_date.isoformat()
        ):
            _record_completion(reviews[problem_id], issue_number, comment_marker)
            results.append(
                {
                    **result,
                    "skipped": (
                        f"already rated on {last_rated}, on or after this issue's date, "
                        f"so the schedule was not changed again. To re-rate it, "
                        f"comment `review {num} reset` first."
                    ),
                }
            )
            continue

        reviews[problem_id] = (
            reset_entry(reviews[problem_id], today, weekend_enabled)
            if rating == "Reset"
            else schedule(  # type: ignore[arg-type]
                reviews[problem_id], rating, today, weekend_enabled
            )
        )
        entry = reviews[problem_id]
        if rating in _RATINGS:
            entry["last_rated"] = today.isoformat()
        _record_completion(entry, issue_number, comment_marker)
        next_date = date.fromisoformat(entry["next_review"])

        results.append(
            {
                **result,
                "next_review": next_date,
                "interval": entry["interval"],
            }
        )

    return results, errors


def build_reply(
    results: list[dict], errors: list[str], pause_message: str | None = None
) -> str:
    parts: list[str] = []
    applied = [r for r in results if "skipped" not in r]
    skipped = [r for r in results if "skipped" in r]

    if applied:
        if len(applied) == 1:
            r = applied[0]
            if r["rating"] == "Remove":
                parts.append(
                    f"✅ **Review updated**\n\n"
                    f"**Problem:** {r['name']}\n"
                    f"**Result:** {r['rating']}\n"
                    f"The problem has been removed from the review pool. "
                    f"It will be re-added automatically the next time it is discovered."
                )
            else:
                parts.append(
                    f"✅ **Review updated**\n\n"
                    f"**Problem:** {r['name']}\n"
                    f"**Result:** {r['rating']}\n"
                    f"**Next review:** {_format_date(r['next_review'])}\n"
                    f"**New interval:** {r['interval']} day{'s' if r['interval'] != 1 else ''}"
                )
        else:
            lines = ["✅ **Reviews updated**\n"]
            for r in applied:
                if r["rating"] == "Remove":
                    lines.append(
                        f"{r['num']}. **{r['name']}**\n"
                        f"   - Result: {r['rating']}\n"
                        f"   - Removed from the review pool"
                    )
                else:
                    lines.append(
                        f"{r['num']}. **{r['name']}**\n"
                        f"   - Result: {r['rating']}\n"
                        f"   - Next review: {r['next_review'].strftime('%b %-d')}\n"
                        f"   - New interval: {r['interval']} day{'s' if r['interval'] != 1 else ''}"
                    )
            parts.append("\n".join(lines))

    if pause_message:
        parts.append(pause_message)

    if skipped:
        lines = ["⏭️ **Skipped**\n"]
        for r in skipped:
            lines.append(f"{r['num']}. **{r['name']}** ({r['rating']}): {r['skipped']}")
        parts.append("\n".join(lines))

    parts.extend(errors)
    return "\n\n---\n\n".join(parts)


def _pause_message(pause_days: int, pause_until: date) -> str:
    return (
        f"⏸️ **Reviews paused**\n\n"
        f"Automation has been paused for **{pause_days} day{'s' if pause_days != 1 else ''}**.\n"
        f"Reviews will resume on **{pause_until.isoformat()}**."
    )


def _write_all_reviewed(all_done: bool) -> None:
    """Tell the workflow whether the issue can be closed."""
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"all_reviewed={'true' if all_done else 'false'}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--comment-id", type=int, required=True)
    parser.add_argument("--repo", required=True, help="owner/repo")
    args = parser.parse_args()

    # Read comment body from environment variable to avoid shell-quoting issues
    comment_body = os.environ.get("REVIEW_COMMENT_BODY", "")
    pause_days = parse_pause_command(comment_body)
    commands = parse_commands(comment_body)
    if pause_days is None and not commands:
        print("No review or pause commands found. Skipping.")
        _write_all_reviewed(False)
        return

    config = _load_config()
    today = local_today(config.get("timezone"))

    # 1. Apply the pause first so it is kept even if the reviews cannot be processed
    pause_message = None
    if pause_days is not None:
        pause_until = today + timedelta(days=pause_days)
        config["pause_until"] = pause_until.isoformat()
        _save_config(config)
        pause_message = _pause_message(pause_days, pause_until)

    # 2. Apply review commands using this issue's date and problem map
    results: list[dict] = []
    errors: list[str] = []
    all_done = False
    fetch_failed = False
    if commands:
        try:
            issue = fetch_issue(args.repo, args.issue_number)
        except Exception as exc:
            print(f"Error fetching issue: {exc}", file=sys.stderr)
            fetch_failed = True
            errors.append(
                "❌ **Unable to process review**\n\n"
                "This issue could not be loaded, so no reviews were applied. "
                "Please post the review commands again."
            )
        else:
            issue_body = issue.get("body") or ""
            problem_map = extract_problem_map(issue_body)
            if not problem_map:
                print("Could not find problem map in issue body.", file=sys.stderr)
                errors.append(
                    "❌ **Unable to process review**\n\n"
                    "This issue has no problem list, so there is nothing to review here."
                )
            else:
                issue_date = issue_date_from_title(issue.get("title") or "") or today
                reviews = _load_reviews()
                results, errors = process_commands(
                    commands,
                    problem_map,
                    reviews,
                    today,
                    comment_id=args.comment_id,
                    weekend_enabled=config.get("weekend_enabled") is True,
                    issue_date=issue_date,
                    issue_number=args.issue_number,
                )
                if results:
                    _save_reviews(reviews)
                all_done = all_required_problems_reviewed(
                    reviews,
                    extract_required_problem_map(issue_body, problem_map),
                    issue_date,
                    args.issue_number,
                )

    # 3. Signal whether the issue can be closed before replying, so a failed
    #    reply cannot skip the close check
    _write_all_reviewed(all_done)

    # 4. Reply once.  The metadata is already saved, so a failed post is only a warning.
    reply = build_reply(results, errors, pause_message)
    if reply:
        try:
            post_comment(args.repo, args.issue_number, reply)
        except Exception as exc:
            detail = str(exc).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(f"::warning::Could not post the reply comment: {detail}")

    if fetch_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
