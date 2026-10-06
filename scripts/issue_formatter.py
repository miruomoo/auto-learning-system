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
    python scripts/issue_formatter.py --body-file issue.md --github-output "$GITHUB_OUTPUT"

Stdout: the full issue body (Markdown).
Exit codes: 0 success, 1 error.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from scheduler import days_overdue, is_due, local_today  # noqa: E402

_REPO_ROOT = Path(__file__).parent.parent
_REVIEWS_PATH = _REPO_ROOT / ".leetcode-review" / "reviews.json"

_DIFFICULTY_EMOJI = {"Hard": "🔴", "Medium": "🟡", "Easy": "🟢", "Unknown": "⚪"}


def _load_reviews() -> dict:
    if _REVIEWS_PATH.exists():
        with _REVIEWS_PATH.open() as fh:
            return json.load(fh)
    return {}


_DIFFICULTY_ORDER = {"Hard": 0, "Medium": 1, "Easy": 2, "Unknown": 3}

_CONFIG_PATH = _REPO_ROOT / ".leetcode-review" / "config.json"


def _load_config() -> dict:
    defaults = {
        "daily_show_limit": 3,
        "pause_until": None,
        "weekend_enabled": False,
    }
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


def _is_paused(config: dict, today: date) -> bool:
    """Return True when the automation is paused for *today*."""
    pause_until = config.get("pause_until")
    if not pause_until:
        return False
    try:
        return today <= date.fromisoformat(pause_until)
    except ValueError:
        return False


def _sort_key(
    item: tuple[str, dict],
    today: date,
    weekend_enabled: bool = False,
):
    problem_id, entry = item
    diff_rank = _DIFFICULTY_ORDER.get(entry.get("difficulty", "Unknown"), 3)
    overdue = days_overdue(entry, today, weekend_enabled)
    ease = entry.get("ease_factor", 2.5)
    last = entry.get("last_review") or "0000-00-00"
    return (diff_rank, -overdue, ease, last)


def _display_name(problem_id: str) -> str:
    return problem_id.replace("-", " ").title()


def _due_label(
    entry: dict,
    today: date,
    weekend_enabled: bool = False,
) -> str:
    overdue = days_overdue(entry, today, weekend_enabled)
    if overdue == 0:
        return "Today"
    return f"{overdue} day{'s' if overdue != 1 else ''} overdue"


def build_issue_body(today: date | None = None) -> tuple[str, list[tuple[str, dict]]]:
    """
    Build the Markdown body for the daily review issue.

    Returns (body_str, shown_items) where shown_items is the ordered list of
    (problem_id, entry) pairs shown in the issue.
    """
    config = _load_config()
    if today is None:
        today = local_today(config.get("timezone"))

    weekend_enabled = config.get("weekend_enabled") is True
    if _is_paused(config, today):
        pause_until = config["pause_until"]
        body = (
            f"## 📚 Today's LeetCode Reviews — {today.isoformat()}\n\n"
            f"⏸️ Reviews are paused until **{pause_until}**. No problems will be shown until then."
        )
        return body, []

    reviews = _load_reviews()

    due_items = [
        (pid, entry)
        for pid, entry in reviews.items()
        if is_due(entry, today, weekend_enabled)
    ]
    due_items.sort(key=lambda x: _sort_key(x, today, weekend_enabled))

    max_daily = max(1, int(config["daily_show_limit"]))
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
    required_problem_map: dict[str, str] = {}

    for idx, (problem_id, entry) in enumerate(shown_items, start=1):
        diff = entry.get("difficulty", "Unknown")
        topic = entry.get("topic", "Unknown")
        emoji = _DIFFICULTY_EMOJI.get(diff, "⚪")
        due_str = _due_label(entry, today, weekend_enabled)
        name = _display_name(problem_id)
        problem_map[str(idx)] = problem_id
        required_problem_map[str(idx)] = problem_id
        problem_lines.append(
            f"{idx}. {emoji} **{name}**\n"
            f"   - Difficulty: {diff}\n"
            f"   - Topic: {topic}\n"
            f"   - Due: {due_str}"
        )

    problems_section = "\n\n".join(problem_lines)

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
        deferred_lines: list[str] = []
        first_deferred_number = len(shown_items) + 1
        for idx, (problem_id, entry) in enumerate(
            deferred_items, start=first_deferred_number
        ):
            diff = entry.get("difficulty", "Unknown")
            topic = entry.get("topic", "Unknown")
            emoji = _DIFFICULTY_EMOJI.get(diff, "⚪")
            due_str = _due_label(entry, today, weekend_enabled)
            name = _display_name(problem_id)
            problem_map[str(idx)] = problem_id
            deferred_lines.append(
                f"{idx}. {emoji} **{name}**\n"
                f"   - Difficulty: {diff}\n"
                f"   - Topic: {topic}\n"
                f"   - Due: {due_str}"
            )
        deferred_section = (
            "\n\n---\n\n"
            "### ⏭️ Deferred to Tomorrow\n\n"
            "These problems are also due and will appear in the next daily issue. "
            "They are optional, but you can review one now using its displayed number, "
            f"e.g. `review {first_deferred_number} easy`.\n\n"
            + "\n\n".join(deferred_lines)
        )
    else:
        deferred_section = ""

    # Hidden JSON blocks for command resolution and required completion tracking
    map_json = json.dumps(problem_map)
    required_map_json = json.dumps(required_problem_map)

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

<!-- problem-map: {map_json} -->
<!-- required-problem-map: {required_map_json} -->"""

    return body, shown_items


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily review issue body")
    parser.add_argument("--today", help="Override today's date (YYYY-MM-DD)")
    parser.add_argument("--body-file", type=Path, help="Write Markdown to this file instead of stdout")
    parser.add_argument("--github-output", type=Path, help="Write has_reviews to a GitHub Actions output file")
    args = parser.parse_args()

    config = _load_config()
    today = date.fromisoformat(args.today) if args.today else local_today(config.get("timezone"))
    body, shown_items = build_issue_body(today)
    if args.body_file:
        args.body_file.write_text(body + "\n")
    else:
        print(body)
    if args.github_output:
        paused = _is_paused(config, today)
        with args.github_output.open("a") as fh:
            fh.write(f"has_reviews={'true' if shown_items else 'false'}\n")
            fh.write(f"paused={'true' if paused else 'false'}\n")


if __name__ == "__main__":
    main()
