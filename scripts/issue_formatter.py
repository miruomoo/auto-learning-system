"""
Build the GitHub issue body for today's LeetCode review session.

The issue body contains a numbered list of due problems plus instructions
for submitting results via comments.  The number assigned to each problem
is its **1-based position** in the due list, and that mapping is embedded
in the issue body as a hidden JSON block so the comment parser can
reconstruct it without re-running discovery.

Usage
-----
    python scripts/issue_formatter.py
    python scripts/issue_formatter.py --today 2026-08-04

Stdout: the full issue body (Markdown).
Exit codes: 0 success, 1 error.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from discovery import discover_problems  # noqa: E402
from scheduler import days_overdue, is_due, new_entry  # noqa: E402

_REPO_ROOT = Path(__file__).parent.parent
_REVIEWS_PATH = _REPO_ROOT / ".leetcode-review" / "reviews.json"

_DIFFICULTY_EMOJI = {"Hard": "🔴", "Medium": "🟡", "Easy": "🟢", "Unknown": "⚪"}


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


def _sync(reviews: dict, today: date) -> dict:
    discovered = discover_problems(_REPO_ROOT)
    for problem_id, meta in discovered.items():
        if problem_id not in reviews:
            entry = new_entry(today)
            entry["difficulty"] = meta["difficulty"]
            entry["topic"] = meta["topic"]
            reviews[problem_id] = entry
        else:
            existing = reviews[problem_id]
            if existing.get("topic") in (None, "Unknown"):
                existing["topic"] = meta["topic"]
            if existing.get("difficulty") in (None, "Unknown"):
                existing["difficulty"] = meta["difficulty"]
    return reviews


_DIFFICULTY_ORDER = {"Hard": 0, "Medium": 1, "Easy": 2, "Unknown": 3}

_CONFIG_PATH = _REPO_ROOT / ".leetcode-review" / "config.json"


def _load_config() -> dict:
    defaults = {"daily_show_limit": 3, "pause_until": None}
    if not _CONFIG_PATH.exists():
        return defaults
    try:
        with _CONFIG_PATH.open() as fh:
            data = json.load(fh)
        return {**defaults, **data}
    except (json.JSONDecodeError, OSError):
        return defaults


def _is_paused(config: dict, today: date) -> bool:
    """Return True when the automation is paused for *today*."""
    pause_until = config.get("pause_until")
    if not pause_until:
        return False
    try:
        return today <= date.fromisoformat(pause_until)
    except ValueError:
        return False


def _sort_key(item: tuple[str, dict], today: date):
    problem_id, entry = item
    diff_rank = _DIFFICULTY_ORDER.get(entry.get("difficulty", "Unknown"), 3)
    overdue = days_overdue(entry, today)
    ease = entry.get("ease_factor", 2.5)
    last = entry.get("last_review") or "0000-00-00"
    return (diff_rank, -overdue, ease, last)


def _display_name(problem_id: str) -> str:
    return problem_id.replace("-", " ").title()


def _due_label(entry: dict, today: date) -> str:
    overdue = days_overdue(entry, today)
    if overdue == 0:
        return "Today"
    return f"{overdue} day{'s' if overdue != 1 else ''} overdue"


def build_issue_body(today: date | None = None) -> tuple[str, list[tuple[str, dict]]]:
    """
    Build the Markdown body for the daily review issue.

    Returns (body_str, due_items) where due_items is the ordered list of
    (problem_id, entry) pairs shown in the issue.
    """
    if today is None:
        today = date.today()

    config = _load_config()
    if _is_paused(config, today):
        pause_until = config["pause_until"]
        body = (
            f"## 📚 Today's LeetCode Reviews — {today.isoformat()}\n\n"
            f"⏸️ Reviews are paused until **{pause_until}**. No problems will be shown until then."
        )
        return body, []

    reviews = _load_reviews()
    reviews = _sync(reviews, today)
    _save_reviews(reviews)

    due_items = [(pid, entry) for pid, entry in reviews.items() if is_due(entry, today)]
    due_items.sort(key=lambda x: _sort_key(x, today))

    max_daily: int = config["daily_show_limit"]
    shown_items = due_items[:max_daily]
    deferred_items = due_items[max_daily:]

    if not shown_items:
        body = (
            f"## 📚 Today's LeetCode Reviews — {today.isoformat()}\n\n"
            "✅ No reviews scheduled for today. Come back tomorrow!"
        )
        return body, []

    # Build numbered problem list
    problem_lines: list[str] = []
    # mapping: 1-based number -> problem_id (stored as JSON in the issue)
    problem_map: dict[str, str] = {}

    for idx, (problem_id, entry) in enumerate(shown_items, start=1):
        diff = entry.get("difficulty", "Unknown")
        topic = entry.get("topic", "Unknown")
        emoji = _DIFFICULTY_EMOJI.get(diff, "⚪")
        due_str = _due_label(entry, today)
        name = _display_name(problem_id)
        problem_map[str(idx)] = problem_id
        problem_lines.append(
            f"{idx}. {emoji} **{name}**\n"
            f"   - Difficulty: {diff}\n"
            f"   - Topic: {topic}\n"
            f"   - Due: {due_str}"
        )

    problems_section = "\n\n".join(problem_lines)

    # Hidden JSON block for the comment parser
    map_json = json.dumps(problem_map)

    # Summary line: how many shown vs total due
    total_due = len(due_items)
    shown_count = len(shown_items)
    if total_due > shown_count:
        summary_line = (
            f"Showing {shown_count} of {total_due} problems due today "
            f"(most overdue / hardest first). "
            f"The remaining {total_due - shown_count} will appear in tomorrow's issue."
        )
    else:
        summary_line = f"{shown_count} problem(s) due today."

    # Optional deferred section
    if deferred_items:
        deferred_lines = [
            f"- {_display_name(pid)} "
            f"({entry.get('difficulty', 'Unknown')}, "
            f"{_due_label(entry, today)})"
            for pid, entry in deferred_items
        ]
        deferred_section = (
            "\n\n---\n\n"
            "### ⏭️ Deferred to Tomorrow\n\n"
            "These problems are also due but will be shown in the next daily issue:\n\n"
            + "\n".join(deferred_lines)
        )
    else:
        deferred_section = ""

    body = f"""## 📚 Today's LeetCode Reviews — {today.isoformat()}

{summary_line}

---

### How to submit results

After completing each problem, comment on this issue using:

```
review <number> <result>
```

**Valid results:** `easy` · `medium` · `forgot` · `reset` · `remove`

**Example:**
```
review 1 easy
review 2 medium
review 3 forgot
review 4 reset
review 5 remove
```

---

### ⏸️ Need a break?

To pause the daily reviews, comment:

```
pause <days>
```

**Example:** `pause 7` freezes automation for 7 days (max 365). Reviews resume automatically when the pause expires.

---

### Today's Problems

{problems_section}{deferred_section}

---

<!-- problem-map: {map_json} -->"""

    return body, shown_items


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily review issue body")
    parser.add_argument("--today", help="Override today's date (YYYY-MM-DD)")
    args = parser.parse_args()

    today = date.fromisoformat(args.today) if args.today else None
    body, _ = build_issue_body(today)
    print(body)


if __name__ == "__main__":
    main()
