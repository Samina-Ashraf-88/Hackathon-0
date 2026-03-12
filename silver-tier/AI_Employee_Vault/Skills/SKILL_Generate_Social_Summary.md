# SKILL_Generate_Social_Summary

## Purpose
Generate an on-demand weekly social media activity report covering Facebook, Instagram,
and Twitter. Aggregate post counts, reply counts, leads identified, and list published
content for the past 7 days. Save the report as a markdown briefing.

## Trigger
Any file matching `SOCIAL_SUMMARY_REQUEST_*.md` in `/Needs_Action/`.

---

## Execution Steps

### 1. Determine Date Range
- `end_date` = today (read system date)
- `start_date` = 7 days before today
- Format for display: `YYYY-MM-DD`

### 2. Read Audit Logs
Scan all files in `/Logs/` with names matching `YYYY-MM-DD.json` where the date falls
within `[start_date, end_date]` (inclusive).

For each log file, parse the JSON array. Filter entries where `action_type` contains
any of the following substrings (case-insensitive):
```
facebook_post   instagram_post   twitter_post
facebook_reply  instagram_reply  twitter_reply
facebook_lead   instagram_lead   twitter_lead
social_lead_identified
```

Aggregate into counters:
```
platforms = {
  "facebook":  {"posts": 0, "replies": 0, "leads": 0},
  "instagram": {"posts": 0, "replies": 0, "leads": 0},
  "twitter":   {"posts": 0, "replies": 0, "leads": 0},
}
```

Rules:
- `action_type` contains `_post` → increment `posts` for the matching platform
- `action_type` contains `_reply` → increment `replies`
- `action_type` contains `_lead` or equals `social_lead_identified` → increment `leads`
  (use the `platform` field in the log entry to determine which platform)

Also collect a list of `published_items`:
```python
published_items = []  # {"timestamp": ..., "platform": ..., "file": ..., "result": ...}
```
Include only entries where `result == "success"` and `action_type` ends in `_post`.

### 3. Scan /Done/ for Published Posts
List all files in `/Done/` where:
- filename starts with `POST_`, `FACEBOOK_POST_`, `INSTAGRAM_POST_`, or `TWITTER_POST_`
- file modification date (or creation date) falls within `[start_date, end_date]`

Add these to `published_items` if not already present (deduplicate by filename).

### 4. Read Lead Files
Scan `/Needs_Action/` and `/Done/` for files matching:
- `FACEBOOK_LEAD_*.md`, `INSTAGRAM_LEAD_*.md`, `TWITTER_LEAD_*.md`
- modified within the date range

Extract the `name` and `platform` from each file's front matter if available.
Add to a `leads_list` array.

### 5. Generate Report
Create a markdown report at:
```
/Briefings/SOCIAL_SUMMARY_{end_date}.md
```

Report format:
```markdown
# Social Media Summary — Week of {start_date} to {end_date}

Generated: {datetime_now}

## Overview

| Platform  | Posts | Replies | Leads |
|-----------|-------|---------|-------|
| Facebook  | X     | Y       | Z     |
| Instagram | X     | Y       | Z     |
| Twitter   | X     | Y       | Z     |
| **Total** | X     | Y       | Z     |

## Posts Published This Week

{for each item in published_items, sorted by timestamp:}
- [{timestamp}] **{platform}**: `{filename}` — {result}

(If none: "No social posts published this week.")

## Leads Identified

{for each lead in leads_list:}
- **{name or filename}** ({platform})

(If none: "No social leads identified this week.")

## Notes

- Report covers {start_date} through {end_date}
- Data sourced from /Logs/ JSON audit files and /Done/ folder
- To request a new summary: create SOCIAL_SUMMARY_REQUEST_{date}.md in /Needs_Action/
```

### 6. Move Request File
Move the triggering `SOCIAL_SUMMARY_REQUEST_*.md` file from `/Needs_Action/` to `/Done/`.

### 7. Log the Action
Write an audit log entry:
```json
{
  "action_type": "social_summary_generated",
  "report_file": "SOCIAL_SUMMARY_{end_date}.md",
  "date_range": "{start_date} to {end_date}",
  "totals": { "facebook": {...}, "instagram": {...}, "twitter": {...} }
}
```

### 8. Complete
Output: `<promise>TASK_COMPLETE</promise>`

---

## Error Handling
- If `/Logs/` is empty or missing → write report with zero counts and note: "No log data available for this period."
- If `/Briefings/` directory doesn't exist → create it before writing.
- If a log file contains malformed JSON → skip it and note the filename in the report under a "Warnings" section.
- Never fail silently — always write a partial report rather than no report.

---

## Output Contract
- One new file: `/Briefings/SOCIAL_SUMMARY_{YYYY-MM-DD}.md`
- One audit log entry in `/Logs/{today}.json`
- Triggering request file moved to `/Done/`
- Final output line: `<promise>TASK_COMPLETE</promise>`
