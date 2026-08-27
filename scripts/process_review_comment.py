"""
Process a ``review <number> <result>`` comment posted on the daily review issue.

Usage (called by the GitHub Actions workflow)
---------------------------------------------
    python scripts/process_review_comment.py \
        --issue-number  <N>          \
        --comment-body  "<text>"     \
        --comment-id    <C>          \
        --repo          owner/repo

The script:
1. Fetches the issue body via the GitHub API to extract the problem-map.
2. Parses all ``review <n> <result>`` commands from the comment.
3. For each command, applies the SM-2 schedule update to reviews.json.
4. Posts a reply comment with the results (or error messages).

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

from scheduler import reset_entry, schedule  # noqa: E402

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

_VALID_RESULTS = {"easy", "medium", "forgot", "reset", "remove"}
_RESULT_LABEL = {"easy": "Easy", "medium": "Medium", "forgot": "Forgot", "reset": "Reset", "remove": "Remove"}

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


def fetch_issue_body(repo: str, issue_number: int) -> str:
    url = f"{_GH_API}/repos/{repo}/issues/{issue_number}"
    return _api_get(url)["body"] or ""


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
    defaults: dict = {"pause_until": None}
    if not _CONFIG_PATH.exists():
        return defaults
    try:
        with _CONFIG_PATH.open() as fh:
            data = json.load(fh)
        return {**defaults, **data}
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


def process_commands(
    commands: list[tuple[int, str]],
    problem_map: dict[str, str],
    reviews: dict,
    today: date,
) -> tuple[list[dict], list[str]]:
    """
    Apply each command to *reviews* (mutated in place).

    Returns:
        results  – list of result dicts for successful commands
        errors   – list of error message strings
    """
    results: list[dict] = []
    errors: list[str] = []

    for num, rating in commands:
        key = str(num)
        if key not in problem_map:
            errors.append(
                f"❌ **Unable to process review**\n\n"
                f"Problem #{num} does not exist in today's review list.\n\n"
                f"**Available problems:**\n{_available_list(problem_map)}"
            )
            continue

        problem_id = problem_map[key]
        if problem_id not in reviews:
            errors.append(
                f"❌ **Problem not found in reviews.json**\n\n"
                f"Problem #{num} (`{problem_id}`) is not tracked."
            )
            continue

        if rating == "Remove":
            del reviews[problem_id]
            results.append(
                {
                    "num": num,
                    "name": _display_name(problem_id),
                    "rating": rating,
                }
            )
            continue

        reviews[problem_id] = (
            reset_entry(reviews[problem_id], today)
            if rating == "Reset"
            else schedule(reviews[problem_id], rating, today)  # type: ignore[arg-type]
        )
        entry = reviews[problem_id]
        next_date = date.fromisoformat(entry["next_review"])

        results.append(
            {
                "num": num,
                "name": _display_name(problem_id),
                "rating": rating,
                "next_review": next_date,
                "interval": entry["interval"],
            }
        )

    return results, errors


def build_reply(results: list[dict], errors: list[str]) -> str:
    parts: list[str] = []

    if results:
        if len(results) == 1:
            r = results[0]
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
            for r in results:
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

    parts.extend(errors)
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--repo", required=True, help="owner/repo")
    args = parser.parse_args()

    today = date.today()

    # Read comment body from environment variable to avoid shell-quoting issues
    comment_body = os.environ.get("REVIEW_COMMENT_BODY", "")
    if not comment_body:
        print("REVIEW_COMMENT_BODY env var is empty. Skipping.")
        return

    # 1a. Check for a pause command — handled independently of review commands
    pause_days = parse_pause_command(comment_body)
    if pause_days is not None:
        pause_until = today + timedelta(days=pause_days)
        config = _load_config()
        config["pause_until"] = pause_until.isoformat()
        _save_config(config)
        reply = (
            f"⏸️ **Reviews paused**\n\n"
            f"Automation has been paused for **{pause_days} day{'s' if pause_days != 1 else ''}**.\n"
            f"Reviews will resume on **{pause_until.isoformat()}**."
        )
        try:
            post_comment(args.repo, args.issue_number, reply)
        except Exception as exc:
            print(f"Error posting comment: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    # 1b. Parse review commands from the comment
    commands = parse_commands(comment_body)
    if not commands:
        # No review commands found — ignore the comment silently
        print("No review commands found. Skipping.")
        return

    # 2. Fetch issue body to get problem map
    try:
        issue_body = fetch_issue_body(args.repo, args.issue_number)
    except Exception as exc:
        print(f"Error fetching issue: {exc}", file=sys.stderr)
        sys.exit(1)

    problem_map = extract_problem_map(issue_body)
    if not problem_map:
        print("Could not find problem map in issue body. Skipping.", file=sys.stderr)
        sys.exit(1)

    # 3. Load reviews, apply updates
    reviews = _load_reviews()
    results, errors = process_commands(commands, problem_map, reviews, today)

    # 4. Save updated reviews
    if results:
        _save_reviews(reviews)

    # 5. Post reply
    reply = build_reply(results, errors)
    if not reply:
        return

    try:
        post_comment(args.repo, args.issue_number, reply)
    except Exception as exc:
        print(f"Error posting comment: {exc}", file=sys.stderr)
        sys.exit(1)

    # 6. Signal whether all problems have been reviewed today
    reviewed_today = set()
    for problem_id in problem_map.values():
        entry = reviews.get(problem_id, {})
        last = entry.get("last_review")
        if last == today.isoformat():
            reviewed_today.add(problem_id)

    all_done = reviewed_today >= set(problem_map.values())

    # Write to GITHUB_OUTPUT so the workflow can act on it
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"all_reviewed={'true' if all_done else 'false'}\n")


if __name__ == "__main__":
    main()
