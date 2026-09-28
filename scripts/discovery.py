"""
Automatic discovery of solution files in the repository.

Scans well-known topic folders and maps each problem folder to a
(problem_id, topic, difficulty) tuple.  No manual registration is needed.

Topic inference
---------------
The parent folder name is used as the topic (e.g. "Data Structures & Algorithms").

Difficulty lookup
-----------------
Difficulty comes from a vendored subset of NeetCode's public problem metadata.
Canonical slugs and LeetCode problem numbers are matched before local aliases.
Problems without an authoritative match are labelled ``"Unknown"``.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_DIFFICULTY_DATA_PATH = Path(__file__).with_name("neetcode_difficulties.json")
_VALID_DIFFICULTIES = {"Easy", "Medium", "Hard"}


@lru_cache(maxsize=1)
def _difficulty_data() -> tuple[dict, dict, dict]:
    with _DIFFICULTY_DATA_PATH.open() as fh:
        data = json.load(fh)
    problems = data["problems"]
    aliases = data["aliases"]
    by_number = {
        str(metadata["number"]): metadata
        for metadata in problems.values()
    }
    return problems, aliases, by_number


def infer_difficulty(problem_id: str) -> str:
    """Return NeetCode's difficulty for a number, canonical slug, or local alias."""
    slug = problem_id.lower().strip().strip("/")
    problems, aliases, by_number = _difficulty_data()

    number_match = re.match(r"^0*(\d+)(?:-|$)", slug)
    metadata = by_number.get(str(int(number_match.group(1)))) if number_match else None
    if metadata is None:
        metadata = problems.get(slug)
    if metadata is None:
        metadata = problems.get(aliases.get(slug, ""))

    difficulty = metadata.get("difficulty") if metadata else None
    return difficulty if difficulty in _VALID_DIFFICULTIES else "Unknown"


# ---------------------------------------------------------------------------
# Repository scanning
# ---------------------------------------------------------------------------

# Folder names that contain NeetCode solutions
_SOLUTION_ROOTS = [
    "Data Structures & Algorithms",
    "Python For Beginners",
    "Advanced Algorithms",
]

# A folder is treated as a problem folder when it contains at least one file
# matching this set of extensions.
_SOLUTION_EXTENSIONS = {".py", ".js", ".ts", ".java", ".cpp", ".cs", ".go", ".rs", ".kt", ".swift", ".sql"}


def _has_solution(folder: Path) -> bool:
    return any(f.suffix in _SOLUTION_EXTENSIONS for f in folder.iterdir() if f.is_file())


def discover_problems(repo_root: str | Path) -> dict[str, dict]:
    """
    Walk *repo_root* and return a mapping of ``problem_id -> {topic, difficulty}``.

    Only folders that contain at least one recognised solution file are included.
    """
    repo_root = Path(repo_root)
    problems: dict[str, dict] = {}

    for root_name in _SOLUTION_ROOTS:
        root_dir = repo_root / root_name
        if not root_dir.is_dir():
            continue
        topic = root_name
        for entry in sorted(root_dir.iterdir()):
            if not entry.is_dir():
                continue
            if not _has_solution(entry):
                continue
            problem_id = entry.name
            problems[problem_id] = {
                "topic": topic,
                "difficulty": infer_difficulty(problem_id),
            }

    return problems
