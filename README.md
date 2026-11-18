# Auto Learning System

> Automated spaced-repetition review system for LeetCode solutions, powered by GitHub Actions.

---

## Overview

I built this project to help me retain data structures and algorithms concepts after solving problems. Spaced repetition schedules harder problems sooner and familiar ones later, encouraging regular recall and long-term retention.

The system uses Python and GitHub Actions to track coding-problem submissions, schedule reviews, and deliver them as daily GitHub Issues.

**Highlights**
- Organizes solutions by topic and problem, with support for multiple languages.
- Detects new submissions and adds problems to a spaced-repetition schedule.
- Creates daily review issues and updates schedules from review feedback.
- Supports configurable timezones, optional weekend reviews, and pauses.

## Get started

Fork this repository to your GitHub account, then clone your fork:

```bash
git clone https://github.com/<your-username>/auto-learning-system.git
cd auto-learning-system
```

Add solutions under the topic and problem folders, then commit and push them to your fork. Enable GitHub Actions and Issues so the workflows can create review issues and update your schedule.

> **NeetCode integration:** Enable GitHub integration in [NeetCode](https://neetcode.io/) and connect it to your study repository to automatically sync submissions. This lets the review workflows discover new submissions without manually copying solution files.

## How it works

Solutions are organized by topic and problem ID. Two GitHub Actions workflows handle the review cycle:

1. **Daily review (`main.yml`)** runs at 5:00 AM UTC. It finds due problems, updates review metadata, and creates or updates a daily GitHub Issue. Runs are limited to weekdays by default; the timezone and weekend policy are configurable.
2. **Review feedback (`process-review-comment.yml`)** processes the repository owner's `review` and `pause` commands on daily review issues. Ratings update the spaced-repetition schedule, and completed issues are closed automatically.

Both workflows serialize metadata updates to prevent conflicting changes. New submission commits mark a problem as completed without changing its SM-2 rating; review feedback controls interval and ease-factor changes.

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

## Review commands

Comment on a daily review issue with one `review <number> <result>` line per problem. You can also review problems from older or closed daily issues. Use `pause <days>` to pause reviews; it can be combined with review commands in the same comment.

**Valid results:** `easy` · `medium` · `forgot` · `reset` · `remove`

| Result   | Description                                                                              |
|----------|------------------------------------------------------------------------------------------|
| `easy`   | Solved quickly with no hints                                                             |
| `medium` | Solved with some extra thinking or hints                                                 |
| `forgot` | Could not solve or had to look at the solution                                           |
| `reset`  | Restart spaced-repetition from scratch (resets interval to 1 day)                       |
| `remove` | Remove from the review pool entirely (re-added automatically when re-discovered)         |

Only the repository owner's commands are processed. Ratings already applied for a problem on or after that issue's date are skipped to avoid increasing the interval twice; use `review <number> reset` to rate it again.
