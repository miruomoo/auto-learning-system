"""
Daily review entrypoint.

Usage
-----
    python scripts/review.py [--rate <problem-id> <Easy|Medium|Forgot>]

When called without arguments (the normal GitHub Actions path) it:

1. Discovers all solved problems in the repository.
2. Loads (or creates) .leetcode-review/reviews.json.
3. Registers any newly discovered problems (first review scheduled for tomorrow).
4. Saves the updated reviews.json.
5. Prints a human-readable report of all problems due today, sorted by:
      Hard first → most overdue → lowest ease factor → oldest review date.

When called with --rate it applies a rating to a single problem and exits.

Exit codes
----------
0  – success (even when no reviews are due)
1  – unexpected error
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Allow running from repo root without installing a package
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from discovery import discover_problems  # noqa: E402
from scheduler import days_overdue, is_due, new_entry, schedule  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_REVIEWS_PATH = _REPO_ROOT / ".leetcode-review" / "reviews.json"
_CONFIG_PATH = _REPO_ROOT / ".leetcode-review" / "config.json"
_SOLUTION_EXTENSIONS = {".py", ".js", ".ts", ".java", ".cpp", ".cs", ".go", ".rs", ".kt", ".swift", ".sql"}

# ---------------------------------------------------------------------------
# JSON helpers
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


def _load_config() -> dict:
    """Load .leetcode-review/config.json, returning sensible defaults if missing."""
    defaults = {
        "system_start_date": None,
        "auto_forgot_after_days": 14,
        "daily_show_limit": 3,
    }
    if not _CONFIG_PATH.exists():
        return defaults
    try:
        with _CONFIG_PATH.open() as fh:
            data = json.load(fh)
        return {**defaults, **data}
    except (json.JSONDecodeError, OSError):
        return defaults


# ---------------------------------------------------------------------------
# Discovery + sync
# ---------------------------------------------------------------------------


def _problem_solution_files(repo_root: Path, meta: dict, problem_id: str) -> list[Path]:
    problem_dir = repo_root / meta["topic"] / problem_id
    if not problem_dir.is_dir():
        return []
    return sorted(
        path for path in problem_dir.iterdir() if path.is_file() and path.suffix in _SOLUTION_EXTENSIONS
    )


def _first_commit_date(repo_root: Path, solution_file: Path) -> date | None:
    result = subprocess.run(
        ["git", "log", "--follow", "--diff-filter=A", "--format=%aI", "--", str(solution_file)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None

    timestamps = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not timestamps:
        return None

    try:
        return datetime.fromisoformat(timestamps[-1]).date()
    except ValueError:
        return None


def _new_problem_base_date(repo_root: Path, problem_id: str, meta: dict, today: date) -> date:
    commit_dates = [
        commit_date
        for solution_file in _problem_solution_files(repo_root, meta, problem_id)
        if (commit_date := _first_commit_date(repo_root, solution_file)) is not None
    ]
    # Falls back to today when git history is unavailable (e.g. shallow clone).
    # In that case the problem will pass the system_start_date cutoff and be
    # registered — intentionally permissive so genuine new submissions aren't
    # silently dropped when history can't be read.
    return min(commit_dates, default=today)


def sync_new_problems(reviews: dict, repo_root: Path, today: date) -> tuple[dict, list[str]]:
    """
    Add any newly discovered problems to *reviews*.

    Problems whose first-commit date is before the configured system_start_date
    are skipped entirely so pre-existing solutions don't flood the queue.

    Returns (updated_reviews, list_of_new_problem_ids).
    """
    config = _load_config()
    system_start_date: date | None = None
    if config.get("system_start_date"):
        try:
            system_start_date = date.fromisoformat(config["system_start_date"])
        except ValueError:
            system_start_date = None

    discovered = discover_problems(repo_root)
    new_ids: list[str] = []

    for problem_id, meta in discovered.items():
        if problem_id not in reviews:
            base_date = _new_problem_base_date(repo_root, problem_id, meta, today)
            if system_start_date is not None and base_date < system_start_date:
                continue
            entry = new_entry(base_date)
            # Override defaults with discovered metadata, but do *not*
            # overwrite any user-set difficulty/topic already in reviews.json.
            entry["difficulty"] = meta["difficulty"]
            entry["topic"] = meta["topic"]
            reviews[problem_id] = entry
            new_ids.append(problem_id)
        else:
            # Keep topic/difficulty fresh if they were never explicitly set.
            existing = reviews[problem_id]
            if existing.get("topic") in (None, "Unknown"):
                existing["topic"] = meta["topic"]
            if existing.get("difficulty") in (None, "Unknown"):
                existing["difficulty"] = meta["difficulty"]

    return reviews, new_ids


# ---------------------------------------------------------------------------
# Sorting helpers
# ---------------------------------------------------------------------------

_DIFFICULTY_ORDER = {"Hard": 0, "Medium": 1, "Easy": 2, "Unknown": 3}


def _sort_key(item: tuple[str, dict], today: date):
    problem_id, entry = item
    diff_rank = _DIFFICULTY_ORDER.get(entry.get("difficulty", "Unknown"), 3)
    overdue = days_overdue(entry, today)
    ease = entry.get("ease_factor", 2.5)
    last = entry.get("last_review") or "0000-00-00"
    # Sort: diff ASC, overdue DESC (negate), ease ASC, last ASC
    return (diff_rank, -overdue, ease, last)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

_DIFFICULTY_EMOJI = {"Hard": "🔴", "Medium": "🟡", "Easy": "🟢"}


def _build_report(due_items: list[tuple[str, dict]], today: date) -> str:
    if not due_items:
        return "✅ No reviews scheduled for today."

    lines = [
        f"📚 **LeetCode Review — {today.isoformat()}**",
        f"   {len(due_items)} problem(s) due\n",
        f"{'Problem':<45} {'Topic':<30} {'Diff':<8} {'Overdue':>7}",
        "-" * 95,
    ]
    for problem_id, entry in due_items:
        diff = entry.get("difficulty", "Unknown")
        topic = entry.get("topic", "Unknown")
        overdue = days_overdue(entry, today)
        emoji = _DIFFICULTY_EMOJI.get(diff, "⚪")
        overdue_str = f"+{overdue}d" if overdue > 0 else "today"
        lines.append(f"{emoji} {problem_id:<43} {topic:<30} {diff:<8} {overdue_str:>7}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main workflows
# ---------------------------------------------------------------------------


def run_daily(today: date | None = None) -> None:
    if today is None:
        today = date.today()

    config = _load_config()
    auto_forgot_after_days: int = config.get("auto_forgot_after_days", 14)

    reviews = _load_reviews()
    reviews, new_ids = sync_new_problems(reviews, _REPO_ROOT, today)

    # Auto-forgot sweep: problems overdue beyond the threshold are penalised
    # automatically so the queue doesn't grow without bound.
    auto_forgot_ids: list[str] = []
    for problem_id, entry in reviews.items():
        if days_overdue(entry, today) > auto_forgot_after_days:
            reviews[problem_id] = schedule(entry, "Forgot", today)
            auto_forgot_ids.append(problem_id)

    _save_reviews(reviews)

    if new_ids:
        print(f"🆕 Registered {len(new_ids)} new problem(s): {', '.join(sorted(new_ids))}\n")
    if auto_forgot_ids:
        print(
            f"⚠️  Auto-marked {len(auto_forgot_ids)} problem(s) as Forgot "
            f"(overdue > {auto_forgot_after_days} days): {', '.join(sorted(auto_forgot_ids))}\n"
        )

    due_items = [(pid, entry) for pid, entry in reviews.items() if is_due(entry, today)]
    due_items.sort(key=lambda x: _sort_key(x, today))

    print(_build_report(due_items, today))


def run_rate(problem_id: str, rating: str, today: date | None = None) -> None:
    if today is None:
        today = date.today()

    reviews = _load_reviews()
    if problem_id not in reviews:
        print(f"❌ Unknown problem: {problem_id}", file=sys.stderr)
        sys.exit(1)

    reviews[problem_id] = schedule(reviews[problem_id], rating, today)  # type: ignore[arg-type]
    _save_reviews(reviews)

    entry = reviews[problem_id]
    print(
        f"✅ Rated '{problem_id}' as {rating}. "
        f"Next review: {entry['next_review']} (interval: {entry['interval']}d, "
        f"ease: {entry['ease_factor']})"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LeetCode spaced-repetition system")
    sub = parser.add_subparsers(dest="command")

    rate_cmd = sub.add_parser("rate", help="Record the result of a review")
    rate_cmd.add_argument("problem_id", help="Problem slug, e.g. two-integer-sum")
    rate_cmd.add_argument("rating", choices=["Easy", "Medium", "Forgot"])

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "rate":
        run_rate(args.problem_id, args.rating)
    else:
        run_daily()


if __name__ == "__main__":
    main()
