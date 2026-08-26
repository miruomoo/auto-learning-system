# Auto Learning System

> Automated spaced-repetition review system for LeetCode solutions, powered by GitHub Actions.

---

## How it works

Solutions are stored in this repository organised by topic and problem ID. Two GitHub Actions workflows drive the review loop:

### 1. Daily LeetCode Review (`main.yml`)

Runs automatically every day at **9:00 AM UTC** (or manually via `workflow_dispatch`).

1. **`scripts/review.py`** — scans your solutions and applies a spaced-repetition schedule to determine which problems are due for review today, then updates `.leetcode-review/reviews.json`.
2. **`scripts/issue_formatter.py`** — formats the day's review set into a GitHub Issue body.
3. A GitHub Issue titled `📚 Daily LeetCode Review — YYYY-MM-DD` is created (or updated if one already exists for today).
4. Updated review metadata is committed back to the repository.

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
  discovery.py              ← scans the repo for solution files
  scheduler.py              ← spaced-repetition scheduling logic

.github/workflows/
  main.yml                  ← daily review workflow (cron: 9 AM UTC)
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

**Valid results:** `easy` · `medium` · `forgot` · `reset`

| Result   | Description                                                           |
|----------|-----------------------------------------------------------------------|
| `easy`   | Solved quickly with no hints                                          |
| `medium` | Solved with some extra thinking or hints                              |
| `forgot` | Could not solve or had to look at the solution                        |
| `reset`  | Restart spaced-repetition from scratch (resets interval to 1 day)    |
