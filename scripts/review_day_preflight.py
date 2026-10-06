"""Decide whether the daily review workflow should run on the configured local day."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

from scheduler import local_today  # noqa: E402

_REPO_ROOT = Path(__file__).parent.parent
_CONFIG_PATH = _REPO_ROOT / ".leetcode-review" / "config.json"


def _load_config(config_path: Path) -> dict:
    try:
        with config_path.open() as fh:
            config = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}
    return config if isinstance(config, dict) else {}


def load_weekend_enabled(config_path: Path = _CONFIG_PATH) -> bool:
    """Return True only when the repository explicitly enables weekend reviews."""
    return _load_config(config_path).get("weekend_enabled") is True


def load_timezone(config_path: Path = _CONFIG_PATH) -> object:
    """Return the configured IANA timezone name, or None to use UTC."""
    return _load_config(config_path).get("timezone")


def should_run(today: date, weekend_enabled: bool = False) -> bool:
    """Return whether reviews are enabled for *today*."""
    return today.weekday() < 5 or weekend_enabled is True


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether today's review should run")
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        help="Override today's date (defaults to the configured timezone, or UTC)",
    )
    parser.add_argument("--config", type=Path, default=_CONFIG_PATH)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    today = args.today or local_today(load_timezone(args.config))
    enabled = should_run(today, load_weekend_enabled(args.config))
    value = "true" if enabled else "false"

    if args.github_output:
        with args.github_output.open("a") as fh:
            fh.write(f"should_run={value}\n")
            fh.write(f"today={today.isoformat()}\n")

    print(f"Review workflow enabled for {today.isoformat()}: {value}")


if __name__ == "__main__":
    main()
