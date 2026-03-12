# SKILL: Weekly CEO Briefing

## Description
Runs every Sunday night (via cron/Task Scheduler). Autonomously audits the week's
activity across all domains (email, social media, Odoo accounting, tasks) and generates a
comprehensive Monday Morning CEO Briefing in `/Briefings/`. This is the flagship Gold Tier
proactive intelligence feature.

## Trigger
- Scheduled: Every Sunday at 22:00 (10 PM) via Task Scheduler / cron
- Manual: "Execute SKILL_Weekly_CEO_Briefing"
- File: `/Needs_Action/WEEKLY_BRIEFING_{YYYYMMDD}.md` (created by weekly_audit.py)

## Data Sources
1. `/Done/` — completed tasks this week
2. `/Logs/*.json` — action audit logs this week
3. `/Accounting/Current_Month.md` — Odoo revenue/expense data (via SKILL_Odoo_Accounting_Actions)
4. `Business_Goals.md` — targets and KPIs
5. `/Plans/` — plan files created this week
6. Social media summaries (from SKILL_Facebook_Instagram_Twitter_Integration)

## Step-by-Step Procedure

### Step 1 — Determine Report Period
```
period_start = last Monday (YYYY-MM-DD)
period_end   = this Sunday (YYYY-MM-DD)
briefing_date = next Monday (YYYY-MM-DD)
```

### Step 2 — Pull Odoo Accounting Data
Execute SKILL_Odoo_Accounting_Actions sub-routine:
```
- get_revenue_summary(date_from=period_start, date_to=period_end)
- list_invoices(state=open)
- get_expense_categories(date_from=month_start, date_to=period_end)
```
Store results in memory as `accounting_data`.

### Step 3 — Analyze Completed Tasks
```
Scan /Done/ for files created/moved this week (check file mtime or front matter dates)
Count by type: email, linkedin, facebook, instagram, twitter, odoo, approval
Identify bottlenecks: tasks that took > 48 hours from creation to /Done/
```

### Step 4 — Analyze Logs
```
Read all /Logs/YYYY-MM-DD.json files for this week
Count: emails_sent, posts_published, approvals_granted, approvals_rejected, errors
Identify most common error types
```

### Step 5 — Social Media Performance Summary
```
For each platform (Facebook, Instagram, Twitter):
  - Count posts published this week
  - Count messages/DMs received
  - Count leads identified
  - Estimate engagement (if data available in logs)
```

### Step 6 — Subscription Audit
Cross-reference `Business_Goals.md` subscription audit rules against expense data:
- Flag any software subscription with no recent usage log
- Flag any cost increase > 20%
- Flag duplicate tools

### Step 7 — Compare Against Business Goals
```
Read Business_Goals.md targets:
  - Revenue target vs actual
  - Lead count target vs actual
  - Response time target vs actual (from task age analysis)
  - Social engagement target vs actual
```
Calculate: on_track | at_risk | off_track for each metric

### Step 8 — Generate Proactive Suggestions
Based on data analysis, generate 3–5 actionable suggestions:
- Revenue gap: "We are $X below target. Suggested action: send follow-up to 3 leads."
- Overdue invoices: "Invoice #X has been unpaid for 30 days. Shall I send a reminder?"
- Subscription waste: "Tool Y shows no usage. Cancel? Save $X/month."
- Social opportunity: "Instagram engagement is up 40% when posts include AI tips. Post more."
- Upcoming deadlines: list any /Plans/ files with due dates in the next 14 days

### Step 9 — Write Briefing File
Create `/Briefings/{YYYYMMDD}_Monday_CEO_Briefing.md`:

```markdown
---
generated: {ISO_TIMESTAMP}
period: {period_start} to {period_end}
generated_by: AI Employee Gold Tier v2.0
---

# Monday Morning CEO Briefing
## Good morning, Samina! Here's your week in review.

## Executive Summary
{1–2 sentence narrative summary of the week}

## Revenue & Finance
| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Weekly Revenue | ${weekly_target} | ${actual} | {🟢/🟡/🔴} |
| MTD Revenue | ${monthly_goal} | ${mtd} | {🟢/🟡/🔴} |
| Unpaid Invoices | 0 | {count} (${total}) | {🟢/🔴} |

### Odoo Invoice Status
{list unpaid invoices with partner name, amount, days overdue}

## Tasks Completed This Week
{table of Done files: task, type, created, completed, duration}

## Bottlenecks
{table: task, expected_duration, actual_duration, delay_reason}

## Social Media This Week
| Platform | Posts | DMs Received | Leads | Engagement |
|----------|-------|--------------|-------|------------|
| Facebook | {n} | {n} | {n} | {est} |
| Instagram | {n} | {n} | {n} | {est} |
| Twitter/X | {n} | {n} | {n} | {est} |

## System Health
- Errors this week: {count}
- Most common error: {type}
- Processes restarted: {count}
- Approvals granted: {count} / Rejected: {count}

## Proactive Suggestions
{numbered list of 3–5 suggestions with [ACTION] tags}

## Upcoming Deadlines (Next 14 Days)
{list from /Plans/ with due dates}

## Subscription Audit
{list flagged subscriptions}

---
*Generated automatically by AI Employee Gold Tier. Review and dismiss by moving to /Done/.*
*Next briefing: {next_monday}*
```

### Step 10 — Create Approval Files for Suggested Actions
For each [ACTION] suggestion that requires Claude to do something:
1. Create `/Pending_Approval/CEO_ACTION_{description}_{date}.md`
2. List the specific MCP call or task that would be executed

### Step 11 — Update Dashboard
Update `Dashboard.md`:
- Add briefing link to Recent Activity
- Update Weekly Metrics section
- Update Status Overview

### Step 12 — Log and Complete
```
Write to /Logs/{date}.json: { "action": "ceo_briefing_generated", "file": "...", ... }
Move /Needs_Action/WEEKLY_BRIEFING_*.md → /Done/
Output: <promise>TASK_COMPLETE</promise>
```

## MCP Calls Summary
```
odoo-mcp: get_revenue_summary, list_invoices, get_expense_categories
(All read-only — no approval needed for the briefing generation itself)
```

## Example Output Location
`/Briefings/20260202_Monday_CEO_Briefing.md`

## Error Handling
- If Odoo unavailable: Generate briefing with "⚠️ Odoo data unavailable" placeholder
- If no log files for the week: Note "No action logs found for this period"
- Always generate the briefing even with partial data — never skip silently
