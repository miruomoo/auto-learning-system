"""Decide whether the daily review workflow should run on the current UTC day."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_CONFIG_PATH = _REPO_ROOT / ".leetcode-review" / "config.json"


def load_weekend_enabled(config_path: Path = _CONFIG_PATH) -> bool:
    """Return True only when the repository explicitly enables weekend reviews."""
    try:
        with config_path.open() as fh:
            config = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return False
    return isinstance(config, dict) and config.get("weekend_enabled") is True


def should_run(today: date, weekend_enabled: bool = False) -> bool:
    """Return whether reviews are enabled for *today*."""
    return today.weekday() < 5 or weekend_enabled is True


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether today's review should run")
    parser.add_argument("--today", type=date.fromisoformat, help="Override the UTC date")
    parser.add_argument("--config", type=Path, default=_CONFIG_PATH)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    today = args.today or datetime.now(timezone.utc).date()
    enabled = should_run(today, load_weekend_enabled(args.config))
    value = "true" if enabled else "false"

    if args.github_output:
        with args.github_output.open("a") as fh:
            fh.write(f"should_run={value}\n")

    print(f"Review workflow enabled for {today.isoformat()}: {value}")


if __name__ == "__main__":
    main()
