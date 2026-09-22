# Auto Learning System

> Automated spaced-repetition review system for LeetCode solutions, powered by GitHub Actions.

---

## How it works

Solutions are stored in this repository organised by topic and problem ID. Two GitHub Actions workflows drive the review loop:

### 1. Daily LeetCode Review (`main.yml`)

Runs automatically at **5:00 AM UTC on weekdays** (or manually via `workflow_dispatch`).

1. **`scripts/review.py`** — consumes new submission commits and determines which problems are due, then updates `.leetcode-review/reviews.json`.
2. **`scripts/issue_formatter.py`** — reads the synchronized metadata and formats the day's review set into a GitHub Issue body.
3. A GitHub Issue titled `📚 Daily LeetCode Review — YYYY-MM-DD` is created (or updated if one already exists for today).
4. If an unpaused day has no scheduled reviews, older open issues with the same daily-review title prefix are closed with an automated comment. Today's issue and unrelated issues remain open.
5. Updated review metadata is committed back to the repository.

### Submission tracking and migration

`system_start_date` applies to individual submission events, not entire problems. A problem with older imported files begins tracking when its first `submission-N` file is committed on or after the cutoff. Eligible commits are consumed chronologically and their commit identities are stored in `processed_submission_commits`, so same-day submissions remain distinct and workflow reruns are idempotent.

An automatically detected submission records completion by setting `last_review` to the UTC submission date and `next_review` to that date plus the current interval. It does not change the interval, ease factor, or review count. Explicit `Easy`, `Medium`, and `Forgot` issue comments remain responsible for SM-2 interval and ease-factor changes, and each comment is applied at most once using its GitHub comment ID.

On the first run after upgrading, entries with established review progress keep their existing schedule, difficulty, and topic; currently eligible commits are marked as already processed instead of replayed. Untouched legacy entries are rebuilt only from eligible submissions, and imported entries with no eligible submission are excluded. If Git history cannot be read, that problem's metadata is left unchanged and the error is reported.

### 2. Process Review Comment (`process-review-comment.yml`)

Triggered whenever a comment containing the word `review` is posted on an open issue.

1. **`scripts/process_review_comment.py`** — parses the comment to record your self-assessment (e.g. how well you recalled the solution) and updates the spaced-repetition schedule in `.leetcode-review/reviews.json`.
2. Updated review metadata is committed back to the repository.

---

## Repository structure

```
.leetcode-review/
  reviews.json              ← spaced-repetition state for all problems

scripts/
  review.py                 ← selects problems due today & updates schedule
  issue_formatter.py        ← formats the daily review GitHub Issue body
  process_review_comment.py ← handles review feedback from issue comments
  daily_issue_lifecycle.py  ← closes stale daily issues on empty days
  discovery.py              ← scans the repo for solution files
  scheduler.py              ← spaced-repetition scheduling logic

.github/workflows/
  main.yml                  ← daily review workflow (weekdays at 5 AM UTC)
  process-review-comment.yml← comment-triggered feedback workflow

<topic-folder>/
  <problem-id>/
    submission-0.<ext>      ← first submission
    submission-1.<ext>      ← second submission
    ...
```

**Example solution paths:**
```
Data Structures & Algorithms/two-integer-sum/submission-0.py
Data Structures & Algorithms/binary-search/submission-0.ts
Python For Beginners/python-hello-world/submission-0.py
```

---

## Supported languages

| Language   | Extension |
|------------|-----------|
| Python     | `.py`     |
| JavaScript | `.js`     |
| TypeScript | `.ts`     |
| Java       | `.java`   |
| C++        | `.cpp`    |
| C#         | `.cs`     |
| Go         | `.go`     |
| Rust       | `.rs`     |
| Kotlin     | `.kt`     |
| Swift      | `.swift`  |
| SQL        | `.sql`    |

---

## Interacting with the daily review

Once the daily issue is created, post a comment on it containing the word `review` along with your self-assessment. The **Process Review Comment** workflow will pick it up and reschedule the problem accordingly.

**Valid results:** `easy` · `medium` · `forgot` · `reset` · `remove`

| Result   | Description                                                                              |
|----------|------------------------------------------------------------------------------------------|
| `easy`   | Solved quickly with no hints                                                             |
| `medium` | Solved with some extra thinking or hints                                                 |
| `forgot` | Could not solve or had to look at the solution                                           |
| `reset`  | Restart spaced-repetition from scratch (resets interval to 1 day)                       |
| `remove` | Remove from the review pool entirely (re-added automatically when re-discovered)         |
