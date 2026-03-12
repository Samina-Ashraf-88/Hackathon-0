# SKILL: Audit Logging

## Description
Every action taken by the AI Employee — whether reading data, drafting content, sending
messages, or recovering from errors — MUST be logged. This skill provides the standard
logging interface used by all other skills. Logs are stored as JSON files in `/Logs/` and
retained for a minimum of 90 days.

## Trigger
- Called by all other skills after every significant action
- Called by orchestrator.py after every /Approved/ execution
- Manual: "Execute SKILL_Audit_Logging to write log entry: {...}"

## Log File Location
`/Logs/YYYY-MM-DD.json` — one file per day, array of JSON objects

## Standard Log Entry Schema
```json
{
  "timestamp": "2026-01-07T10:30:00Z",
  "log_id": "uuid-v4",
  "action_type": "email_send | social_post | odoo_create | approval_created | task_completed | error | system_event",
  "actor": "claude_code | watcher_name | orchestrator | system",
  "component": "email-mcp | facebook-mcp | instagram-mcp | twitter-mcp | odoo-mcp | vault | watchdog",
  "skill_invoked": "SKILL_name",
  "target": "email address | username | invoice_id | file_path",
  "parameters": { "key": "value" },
  "approval_status": "auto | pending | approved | rejected | not_required",
  "approved_by": "human | system_alert",
  "result": "success | failure | queued | skipped",
  "error_details": null,
  "dry_run": false,
  "source_file": "path/to/triggering/Needs_Action/file.md",
  "output_file": "path/to/resulting/Done_or_Pending/file.md"
}
```

## Step-by-Step Procedure

### Step 1 — Build Log Entry
From context of the action just taken, populate all fields:
```
- timestamp: current UTC ISO 8601
- log_id: generate using Python uuid.uuid4()
- action_type: classify the action
- actor: "claude_code" (default when Claude is executing)
- component: which MCP server or vault operation
- skill_invoked: name of the calling SKILL
- target: sanitized target (email domain only, not full address in sensitive contexts)
- parameters: relevant params WITHOUT secrets/tokens
- approval_status: was this approved by human or auto?
- result: success | failure | queued | skipped
- error_details: full error message if result=failure, else null
- dry_run: read from DRY_RUN env var
```

### Step 2 — Append to Daily Log File
```python
# Claude writes this to the log file via file tools
log_path = f"/Logs/{today_date}.json"
# Read existing entries or start fresh
# Append new entry
# Write back
```

### Step 3 — Log Rotation & Retention
Every Monday, check for log files older than 90 days:
```
Files older than 90 days → move to /Logs/Archive/YYYY-MM/
Files older than 1 year → create ARCHIVE_REVIEW_{YYYY}.md in /Needs_Action/ for human decision
```

### Step 4 — Write Summary to Dashboard
After logging, update Dashboard.md weekly metrics:
```
- Emails Processed: count of action_type=email_send this week
- Posts Published: count of action_type=social_post this week
- Tasks Completed: count of action_type=task_completed this week
- Approvals Granted: count of approval_status=approved this week
- Errors: count of result=failure this week
```

## Action Type Reference
| action_type | When to Use |
|-------------|-------------|
| `email_received` | Gmail watcher detected new email |
| `email_draft` | Claude drafted an email reply |
| `email_send` | Email MCP sent an email |
| `social_post` | Posted to Facebook/Instagram/Twitter |
| `social_reply` | Replied to a comment/DM |
| `social_lead_identified` | Flagged an inbound message as a lead |
| `odoo_read` | Read data from Odoo (revenue, invoices) |
| `odoo_create` | Created invoice/customer in Odoo |
| `odoo_payment` | Registered payment in Odoo |
| `approval_created` | Created a file in /Pending_Approval/ |
| `approval_granted` | Human moved file to /Approved/ |
| `approval_rejected` | Human moved file to /Rejected/ |
| `task_completed` | Moved task file from /Needs_Action/ to /Done/ |
| `ceo_briefing` | Generated Monday CEO Briefing |
| `error` | Any error/exception occurred |
| `error_recovery` | Error recovery action taken |
| `system_event` | Process started/stopped/restarted |
| `auth_failure` | OAuth token expired or session lost |

## Example Log Entry — Email Send
```json
{
  "timestamp": "2026-01-07T10:45:00Z",
  "log_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "action_type": "email_send",
  "actor": "claude_code",
  "component": "email-mcp",
  "skill_invoked": "SKILL_Send_Email_via_MCP",
  "target": "client_a@example.com",
  "parameters": { "subject": "January 2026 Invoice" },
  "approval_status": "approved",
  "approved_by": "human",
  "result": "success",
  "error_details": null,
  "dry_run": false,
  "source_file": "Needs_Action/EMAIL_123.md",
  "output_file": "Done/EMAIL_123.md"
}
```

## Example Log Entry — Error
```json
{
  "timestamp": "2026-01-07T11:00:00Z",
  "log_id": "a1b2c3d4-...",
  "action_type": "error",
  "actor": "claude_code",
  "component": "instagram-mcp",
  "skill_invoked": "SKILL_Process_Social_Post",
  "target": "apple379tree",
  "parameters": { "attempt": 3 },
  "approval_status": "not_required",
  "approved_by": null,
  "result": "failure",
  "error_details": "Connection refused at localhost:3002 after 3 retries",
  "dry_run": false,
  "source_file": "Needs_Action/INSTAGRAM_DM_001.md",
  "output_file": null
}
```

## Privacy Rules for Logs
- Never log: API keys, OAuth tokens, passwords, session cookies
- Truncate email body to first 100 chars in logs
- Log email domains, not full addresses when possible
- Never log banking credentials or Odoo admin password
- Log file access: which files were read/written, but not their full content
