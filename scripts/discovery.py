"""
Automatic discovery of solution files in the repository.

Scans well-known topic folders and maps each problem folder to a
(problem_id, topic, difficulty) tuple.  No manual registration is needed.

Topic inference
---------------
The parent folder name is used as the topic (e.g. "Data Structures & Algorithms").

Difficulty
----------
The problem ID (NeetCode slug) is looked up in tables of NeetCode difficulties.
Known slugs always use the NeetCode label; unknown slugs default to Medium and
can be overridden by editing their ``"difficulty"`` key in reviews.json.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# NeetCode difficulties, keyed by NeetCode problem slug
# ---------------------------------------------------------------------------

_EASY = {
    "balanced-binary-tree",
    "binary-search",
    "binary-tree-diameter",
    "buy-and-sell-crypto",
    "climbing-stairs",
    "counting-bits",
    "depth-of-binary-tree",
    "duplicate-integer",
    "invert-a-binary-tree",
    "is-anagram",
    "is-palindrome",
    "kth-largest-integer-in-a-stream",
    "last-stone-weight",
    "linked-list-cycle-detection",
    "meeting-schedule",
    "merge-two-sorted-linked-lists",
    "min-cost-climbing-stairs",
    "missing-number",
    "non-cyclical-number",
    "number-of-one-bits",
    "plus-one",
    "python-hello-world",
    "reverse-a-linked-list",
    "reverse-bits",
    "same-binary-tree",
    "single-number",
    "subtree-of-a-binary-tree",
    "two-integer-sum",
    "validate-parentheses",
}

_MEDIUM = {
    "add-two-numbers",
    "anagram-groups",
    "binary-tree-from-preorder-and-inorder-traversal",
    "binary-tree-right-side-view",
    "buy-and-sell-crypto-with-cooldown",
    "car-fleet",
    "cheapest-flight-path",
    "clone-graph",
    "coin-change",
    "coin-change-ii",
    "combination-target-sum",
    "combination-target-sum-ii",
    "combinations-of-a-phone-number",
    "copy-linked-list-with-random-pointer",
    "count-connected-components",
    "count-good-nodes-in-binary-tree",
    "count-number-of-islands",
    "count-paths",
    "count-squares",
    "course-schedule",
    "course-schedule-ii",
    "daily-temperatures",
    "decode-ways",
    "design-twitter-feed",
    "design-word-search-data-structure",
    "eating-bananas",
    "edit-distance",
    "evaluate-reverse-polish-notation",
    "find-duplicate-integer",
    "find-minimum-in-rotated-sorted-array",
    "find-target-in-rotated-sorted-array",
    "gas-station",
    "generate-parentheses",
    "hand-of-straights",
    "house-robber",
    "house-robber-ii",
    "implement-prefix-tree",
    "insert-into-a-binary-search-tree",
    "insert-new-interval",
    "interleaving-string",
    "islands-and-treasure",
    "jump-game",
    "jump-game-ii",
    "k-closest-points-to-origin",
    "kth-largest-element-in-an-array",
    "kth-smallest-integer-in-bst",
    "level-order-traversal-of-binary-tree",
    "longest-common-subsequence",
    "longest-consecutive-sequence",
    "longest-increasing-subsequence",
    "longest-palindromic-substring",
    "longest-repeating-substring-with-replacement",
    "longest-substring-without-duplicates",
    "lowest-common-ancestor-in-binary-search-tree",
    "lru-cache",
    "max-area-of-island",
    "max-water-container",
    "maximum-product-subarray",
    "maximum-subarray",
    "meeting-schedule-ii",
    "merge-intervals",
    "merge-triplets-to-form-target",
    "min-cost-to-connect-points",
    "minimum-stack",
    "multiply-strings",
    "network-delay-time",
    "non-overlapping-intervals",
    "pacific-atlantic-water-flow",
    "palindrome-partitioning",
    "palindromic-substrings",
    "partition-equal-subset-sum",
    "partition-labels",
    "permutation-string",
    "permutations",
    "pow-x-n",
    "products-of-array-discluding-self",
    "redundant-connection",
    "remove-node-from-end-of-linked-list",
    "reorder-linked-list",
    "reverse-integer",
    "rotate-matrix",
    "rotting-fruit",
    "search-2d-matrix",
    "search-for-word",
    "set-zeroes-in-matrix",
    "spiral-matrix",
    "string-encode-and-decode",
    "subsets",
    "subsets-ii",
    "sum-of-two-integers",
    "surrounded-regions",
    "target-sum",
    "task-scheduling",
    "three-integer-sum",
    "time-based-key-value-store",
    "top-k-elements-in-list",
    "two-integer-sum-ii",
    "valid-binary-search-tree",
    "valid-parenthesis-string",
    "valid-sudoku",
    "valid-tree",
    "word-break",
}

_HARD = {
    "binary-tree-maximum-path-sum",
    "burst-balloons",
    "count-subsequences",
    "find-median-in-a-data-stream",
    "foreign-dictionary",
    "largest-rectangle-in-histogram",
    "longest-increasing-path-in-matrix",
    "median-of-two-sorted-arrays",
    "merge-k-sorted-linked-lists",
    "minimum-interval-including-query",
    "minimum-window-with-characters",
    "n-queens",
    "reconstruct-flight-path",
    "regular-expression-matching",
    "reverse-nodes-in-k-group",
    "search-for-word-ii",
    "serialize-and-deserialize-binary-tree",
    "sliding-window-maximum",
    "swim-in-rising-water",
    "trapping-rain-water",
    "word-ladder",
}


def neetcode_difficulty(problem_id: str) -> str | None:
    """Return the NeetCode difficulty of a known problem slug, or None."""
    slug = problem_id.lower()
    if slug in _EASY:
        return "Easy"
    if slug in _MEDIUM:
        return "Medium"
    if slug in _HARD:
        return "Hard"
    return None


def infer_difficulty(problem_id: str) -> str:
    """Return the NeetCode difficulty, defaulting to Medium for unknown slugs."""
    return neetcode_difficulty(problem_id) or "Medium"


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
