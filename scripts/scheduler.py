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
from datetime import date, timedelta
from typing import Literal

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


def new_entry(today: date | None = None) -> dict:
    """Return the default metadata for a newly discovered problem."""
    if today is None:
        today = date.today()
    return {
        "difficulty": "Medium",
        "topic": "Unknown",
        "last_review": None,
        "next_review": (today + timedelta(days=1)).isoformat(),
        "interval": 1,
        "ease_factor": _INITIAL_EASE,
        "review_count": 0,
    }


def schedule(entry: dict, rating: Rating, today: date | None = None) -> dict:
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
        interval = max(1, round(interval * ease))
    elif rating == "Medium":
        ease = _clamp_ease(ease + _MEDIUM_EASE_DELTA)
        interval = max(1, round(interval * _MEDIUM_INTERVAL_FACTOR))
    else:  # Forgot
        ease = _clamp_ease(ease + _FORGOT_EASE_DELTA)
        interval = 1

    entry["ease_factor"] = round(ease, 4)
    entry["interval"] = interval
    entry["last_review"] = today.isoformat()
    entry["next_review"] = (today + timedelta(days=interval)).isoformat()
    entry["review_count"] = entry.get("review_count", 0) + 1
    return entry


def is_due(entry: dict, today: date | None = None) -> bool:
    """Return True when the problem is due for review on or before *today*."""
    if today is None:
        today = date.today()
    next_review = entry.get("next_review")
    if next_review is None:
        return True
    return date.fromisoformat(next_review) <= today


def days_overdue(entry: dict, today: date | None = None) -> int:
    """Return how many days overdue the problem is (0 if not overdue)."""
    if today is None:
        today = date.today()
    next_review = entry.get("next_review")
    if next_review is None:
        return 0
    delta = (today - date.fromisoformat(next_review)).days
    return max(0, delta)
