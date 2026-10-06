"""
SM-2 inspired spaced-repetition scheduler.

This module is intentionally free of GitHub / filesystem dependencies so it
can be reused by a CLI, web interface, or tests without any side-effects.

Rating constants
----------------
EASY   – solved quickly, no hints needed
MEDIUM – solved eventually with extra thinking or 1-2 hints
FORGOT – could not solve or had to look at the solution
"""

from __future__ import annotations

import math
import sys
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

Rating = Literal["Easy", "Medium", "Forgot"]

# SM-2 tuning knobs
_MIN_EASE = 1.3
_INITIAL_EASE = 2.5
_EASY_EASE_DELTA = 0.15
_MEDIUM_EASE_DELTA = -0.05
_FORGOT_EASE_DELTA = -0.2
_MEDIUM_INTERVAL_FACTOR = 1.5


def _clamp_ease(ease: float) -> float:
    return max(_MIN_EASE, ease)


def _round_half_up(value: float) -> int:
    """Round halves up; Python's ``round()`` rounds halves to the nearest even number."""
    # Ease factors are stored with 4 decimals, so trimming float noise first keeps
    # exact halves such as 75 * 1.38 (103.49999999999999 as a float) at .5.
    return math.floor(round(value, 9) + 0.5)


def resolve_timezone(name: object) -> tzinfo:
    """Return the IANA timezone *name*, or UTC when it is unset or invalid."""
    if name is None or name == "":
        return timezone.utc
    if isinstance(name, str):
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            pass
    print(f"⚠️  Unknown timezone {name!r} in config.json; using UTC.", file=sys.stderr)
    return timezone.utc


def local_today(timezone_name: object = None, now: datetime | None = None) -> date:
    """Return the current date in the configured timezone (UTC by default)."""
    if now is None:
        now = datetime.now(timezone.utc)
    return now.astimezone(resolve_timezone(timezone_name)).date()


def next_weekday(value: date) -> date:
    """Roll Saturday/Sunday dates forward to Monday."""
    if value.weekday() == 5:
        return value + timedelta(days=2)
    if value.weekday() == 6:
        return value + timedelta(days=1)
    return value


def _apply_weekend_policy(value: date, weekend_enabled: bool = False) -> date:
    """Return *value* unchanged only when weekend reviews are explicitly enabled."""
    return value if weekend_enabled is True else next_weekday(value)


def review_date(start: date, interval: int, weekend_enabled: bool = False) -> date:
    """Return the calculated review date under the configured weekend policy."""
    return _apply_weekend_policy(start + timedelta(days=interval), weekend_enabled)


def new_entry(today: date | None = None, weekend_enabled: bool = False) -> dict:
    """Return the default metadata for a newly discovered problem."""
    if today is None:
        today = date.today()
    return {
        "difficulty": "Medium",
        "topic": "Unknown",
        "last_review": None,
        "next_review": review_date(today, 1, weekend_enabled).isoformat(),
        "interval": 1,
        "ease_factor": _INITIAL_EASE,
        "review_count": 0,
    }


def schedule(
    entry: dict,
    rating: Rating,
    today: date | None = None,
    weekend_enabled: bool = False,
) -> dict:
    """
    Apply an SM-2 update to *entry* given a review *rating*.

    Returns a **new** dict (the original is not mutated).
    """
    if today is None:
        today = date.today()

    entry = dict(entry)  # shallow copy – all values are scalars
    ease = entry.get("ease_factor", _INITIAL_EASE)
    interval = entry.get("interval", 1)

    if rating == "Easy":
        ease = _clamp_ease(ease + _EASY_EASE_DELTA)
        interval = max(1, _round_half_up(interval * ease))
    elif rating == "Medium":
        ease = _clamp_ease(ease + _MEDIUM_EASE_DELTA)
        interval = max(1, _round_half_up(interval * _MEDIUM_INTERVAL_FACTOR))
    else:  # Forgot
        ease = _clamp_ease(ease + _FORGOT_EASE_DELTA)
        interval = 1

    entry["ease_factor"] = round(ease, 4)
    entry["interval"] = interval
    entry["last_review"] = today.isoformat()
    entry["next_review"] = review_date(today, interval, weekend_enabled).isoformat()
    entry["review_count"] = entry.get("review_count", 0) + 1
    return entry


def reset_entry(
    entry: dict,
    today: date | None = None,
    weekend_enabled: bool = False,
) -> dict:
    """
    Reset *entry*'s spaced-repetition schedule back to its initial state.

    Returns a **new** dict (the original is not mutated).  The ``difficulty``
    and ``topic`` fields are preserved; all scheduling fields are reset to the
    same defaults used for a newly discovered problem.  Processing markers and
    the issues the problem was completed in are kept; ``last_rated`` is
    cleared so the next rating counts as the first one after the reset.
    """
    if today is None:
        today = date.today()
    reset = {
        "difficulty": entry.get("difficulty", "Medium"),
        "topic": entry.get("topic", "Unknown"),
        "last_review": None,
        "next_review": review_date(today, 1, weekend_enabled).isoformat(),
        "interval": 1,
        "ease_factor": _INITIAL_EASE,
        "review_count": 0,
    }
    for marker in (
        "processed_submission_commits",
        "processed_rating_comment_ids",
        "completed_in_issues",
    ):
        if marker in entry:
            reset[marker] = list(entry[marker])
    return reset


def is_due(
    entry: dict,
    today: date | None = None,
    weekend_enabled: bool = False,
) -> bool:
    """Return True when the problem is due for review on or before *today*."""
    if today is None:
        today = date.today()
    next_review = entry.get("next_review")
    if next_review is None:
        return True
    due_date = _apply_weekend_policy(date.fromisoformat(next_review), weekend_enabled)
    return due_date <= today


def days_overdue(
    entry: dict,
    today: date | None = None,
    weekend_enabled: bool = False,
) -> int:
    """Return how many days overdue the problem is (0 if not overdue)."""
    if today is None:
        today = date.today()
    next_review = entry.get("next_review")
    if next_review is None:
        return 0
    due_date = _apply_weekend_policy(date.fromisoformat(next_review), weekend_enabled)
    delta = (today - due_date).days
    return max(0, delta)
