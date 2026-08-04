"""
Automatic discovery of solution files in the repository.

Scans well-known topic folders and maps each problem folder to a
(problem_id, topic, difficulty) tuple.  No manual registration is needed.

Topic inference
---------------
The parent folder name is used as the topic (e.g. "Data Structures & Algorithms").

Difficulty inference
--------------------
A lightweight keyword lookup against the problem ID is used to give a best-effort
difficulty label.  The label can be overridden by storing an explicit
``"difficulty"`` key in reviews.json.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Keyword-based difficulty heuristics
# ---------------------------------------------------------------------------

_HARD_KEYWORDS = {
    "maximum-path-sum",
    "serialize-and-deserialize",
    "sliding-window-maximum",
    "minimum-window",
    "alien-dictionary",
    "trapping-rain-water",
    "median-of-two-sorted-arrays",
    "word-ladder",
    "word-search",
    "search-for-word-ii",
    "swim-in-rising-water",
    "cheapest-flight-path",
    "minimum-cost-to-connect-points",
    "min-cost-to-connect-points",
    "distinct-subsequences",
    "edit-distance",
    "interleaving-string",
    "regular-expression-matching",
    "largest-rectangle-in-histogram",
    "count-paths",
    "n-queens",
    "palindrome-partitioning-ii",
    "burst-balloons",
    "buy-and-sell-crypto-with-cooldown",
    "binary-tree-from-preorder-and-inorder-traversal",
}

_EASY_KEYWORDS = {
    "two-integer-sum",
    "binary-search",
    "valid-palindrome",
    "valid-anagram",
    "counting-bits",
    "climbing-stairs",
    "same-binary-tree",
    "balanced-binary-tree",
    "binary-tree-diameter",
    "count-good-nodes-in-binary-tree",
    "invert-binary-tree",
    "maximum-depth-of-binary-tree",
    "buy-and-sell-crypto",
    "single-number",
    "reverse-bits",
    "number-of-1-bits",
    "missing-number",
    "python-hello-world",
}


def infer_difficulty(problem_id: str) -> str:
    """Best-effort difficulty from the problem slug."""
    slug = problem_id.lower()
    if slug in _HARD_KEYWORDS:
        return "Hard"
    if slug in _EASY_KEYWORDS:
        return "Easy"
    return "Medium"


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
