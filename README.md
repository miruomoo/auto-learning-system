# Auto Learning System

> Automated spaced-repetition review system for LeetCode solutions, powered by GitHub Actions.

---

## How it works

Solutions are stored in this repository organised by topic and problem ID. Two GitHub Actions workflows drive the review loop:

### 1. Daily LeetCode Review (`main.yml`)

Runs automatically at **5:00 AM UTC every day**. A preflight check picks the review day in the [configured timezone](#timezone) (UTC by default), enables Monday–Friday runs by default and enables Saturday/Sunday runs only when weekend reviews are configured. Manual `workflow_dispatch` runs follow the same policy.

1. **`scripts/review.py`** — consumes new submission commits and determines which problems are due, then updates `.leetcode-review/reviews.json`.
2. **`scripts/issue_formatter.py`** — reads the synchronized metadata and formats the day's review set into a GitHub Issue body.
3. A GitHub Issue titled `📚 Daily LeetCode Review — YYYY-MM-DD` is created (or updated if one already exists for today).
4. Updated review metadata is committed back to the repository.
5. On an unpaused day, older open issues with the same daily-review title prefix are closed with an automated comment: as superseded by today's issue when there are reviews, or because nothing is scheduled on an empty day. Today's issue and unrelated issues remain open. Closed daily issues still accept review comments.

### Submission tracking and migration

`system_start_date` applies to individual submission events, not entire problems. A problem with older imported files begins tracking when its first `submission-N` file is committed on or after the cutoff. Eligible commits are consumed chronologically and their commit identities are stored in `processed_submission_commits`, so same-day submissions remain distinct and workflow reruns are idempotent.

An automatically detected submission records completion by setting `last_review` to the UTC submission date and `next_review` to that date plus the current interval, applying the configured weekend policy. It does not change the interval, ease factor, or review count. Explicit `Easy`, `Medium`, and `Forgot` issue comments remain responsible for SM-2 interval and ease-factor changes, and each comment is applied at most once using its GitHub comment ID.

On the first run after upgrading, entries with established review progress keep their existing schedule, difficulty, and topic; currently eligible commits are marked as already processed instead of replayed. Untouched legacy entries are rebuilt only from eligible submissions, and imported entries with no eligible submission are excluded. If Git history cannot be read, that problem's metadata is left unchanged and the error is reported.

### 2. Process Review Comment (`process-review-comment.yml`)

Triggered when the repository owner posts a comment containing `review` or `pause` on a daily review issue, whether the issue is open or closed. Comments from other users are ignored.

1. **`scripts/process_review_comment.py`** — applies the `pause` command and the `review` commands in the comment (both can appear in the same comment), updates `.leetcode-review/config.json` and the spaced-repetition schedule in `.leetcode-review/reviews.json`, and posts one reply with the results. If the reply cannot be posted, the run only logs a warning, so the updates are still saved.
2. Updated review metadata is committed back to the repository.
3. If the issue is open and every required problem in it has been completed, the issue is closed.

A problem counts as completed for an issue once a `review` command for it has been processed from that issue (including `reset`), once it has been removed from the review pool, or when its last review is on or after the issue's date, so reviews that continue past midnight still count.

An `easy`, `medium`, or `forgot` rating is skipped, and reported in the reply, if the problem was already rated on or after the issue's date (for example, a deferred problem rated in both yesterday's and today's issue), so the interval does not grow twice. To rate it again anyway, comment `review <number> reset` first. Repeated commands for the same problem in one comment are also reported as skipped.

Both workflows share one `review-metadata` concurrency queue, so review metadata is updated by one run at a time, and they rebase and retry if a push is rejected.

---

## Repository structure

```
.leetcode-review/
  config.json               ← review automation settings
  reviews.json              ← spaced-repetition state for all problems

scripts/
  review.py                 ← selects problems due today & updates schedule
  issue_formatter.py        ← formats the daily review GitHub Issue body
  process_review_comment.py ← handles review feedback from issue comments
  review_day_preflight.py   ← picks the review day and applies the weekend policy
  daily_issue_lifecycle.py  ← closes older daily issues
  discovery.py              ← scans the repo for solution files
  scheduler.py              ← spaced-repetition scheduling logic

.github/workflows/
  main.yml                  ← daily review workflow (daily at 5 AM UTC)
  process-review-comment.yml← comment-triggered feedback workflow

<topic-folder>/
  <problem-id>/
    submission-0.<ext>      ← first submission
    submission-1.<ext>      ← second submission
    ...
```

## Weekend reviews

Weekend reviews are disabled by default. Add or update this setting in `.leetcode-review/config.json` to allow normal review issues and newly calculated due dates on Saturdays and Sundays:

```json
{
  "weekend_enabled": true
}
```

The workflow uses the current day in the [configured timezone](#timezone) (UTC by default). A missing, `false`, or invalid `weekend_enabled` value preserves weekday-only behavior.

Changing the setting does not rewrite existing review metadata. Enabling weekends affects only newly calculated dates, so dates already rolled to Monday stay on Monday. After disabling weekends, an existing Saturday or Sunday due date is treated as due on Monday without immediately changing the stored date.

**Example solution paths:**
```
Data Structures & Algorithms/two-integer-sum/submission-0.py
Data Structures & Algorithms/binary-search/submission-0.ts
Python For Beginners/python-hello-world/submission-0.py
```

## Timezone

"Today" means the current **UTC** day by default. To use your local day for the daily issue, the weekend policy, pauses, and review dates, add an IANA timezone name to `.leetcode-review/config.json`:

```json
{
  "timezone": "Europe/London"
}
```

A missing or empty value uses UTC. An unknown value prints a warning and falls back to UTC. Submission dates detected from commits remain UTC dates.

The daily workflow still starts at 05:00 UTC, so adjust the `cron` schedule in `.github/workflows/main.yml` to get the issue at a different local time. The run must start after your local midnight: in timezones more than 5 hours behind UTC (for example, US Central or Pacific time), the default schedule runs on the previous local day.

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

Once the daily issue is created, post a comment on it with one `review <number> <result>` line per problem. The **Process Review Comment** workflow will pick it up and reschedule the problems accordingly. You can also comment on an older or closed daily issue to review problems you deferred. A `pause <days>` line pauses the daily reviews and can be combined with review lines in the same comment.

**Valid results:** `easy` · `medium` · `forgot` · `reset` · `remove`

| Result   | Description                                                                              |
|----------|------------------------------------------------------------------------------------------|
| `easy`   | Solved quickly with no hints                                                             |
| `medium` | Solved with some extra thinking or hints                                                 |
| `forgot` | Could not solve or had to look at the solution                                           |
| `reset`  | Restart spaced-repetition from scratch (resets interval to 1 day)                       |
| `remove` | Remove from the review pool entirely (re-added automatically when re-discovered)         |
