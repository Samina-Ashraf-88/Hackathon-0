# SKILL: Error Recovery & Graceful Degradation

## Description
Handles failures across all system components. When an MCP server, watcher, or external
API fails, this skill ensures the system degrades gracefully: queuing work locally, alerting
the human, and recovering when possible — without losing data or causing duplicate actions.

## Trigger
- Invoked by any other skill when an error occurs (2+ consecutive failures)
- Files in /Needs_Action/ with `type: system_error` or `type: mcp_failure`
- Watchdog.py creates these files automatically on process crashes
- Manual: "Execute SKILL_Error_Recovery_Graceful_Degradation"

## Error Classification Matrix

| Category | Examples | Recovery Strategy | Human Alert? |
|----------|----------|------------------|--------------|
| Transient | Network timeout, API rate limit | Exponential backoff (3 retries) | No |
| Authentication | Expired OAuth token, session expired | Alert human, pause operations | YES |
| Logic | Claude misinterprets task | Move to /Needs_Action/ with review flag | Yes (low priority) |
| Data | Corrupted .md file, missing field | Quarantine to /Rejected/, log details | No |
| MCP Server Down | Connection refused on port | Queue locally, restart attempt | Yes |
| System Crash | Orchestrator died, watcher stopped | Watchdog restarts, log incident | Yes |
| External Block | Platform blocked automation | Set manual_required flag | YES |
| Odoo Error | JSON-RPC fault, DB connection lost | Alert human, halt write actions | YES |

## Step-by-Step Procedure

### Step 1 — Parse Error Context
When invoked, read the triggering file or error message:
```
- error_type: transient | auth | logic | data | mcp_down | system | blocked | odoo
- component: email-mcp | facebook-mcp | instagram-mcp | twitter-mcp | odoo-mcp | watcher | orchestrator
- action_attempted: the specific action that failed
- failure_count: how many times this has failed
- original_file: the task file that triggered the failure
```

### Step 2 — Apply Recovery Strategy

#### Transient Error Recovery
```
1. Wait: 2^failure_count seconds (max 60s)
2. Retry original action
3. If failure_count >= 3 → escalate to human alert
4. Log each retry attempt to /Logs/
```

#### Authentication Failure
```
1. STOP all write operations for this platform
2. Create: /Needs_Action/AUTH_REQUIRED_{PLATFORM}_{DATE}.md
3. Draft email to apple379tree@gmail.com:
   Subject: "AI Employee: {PLATFORM} authentication needs renewal"
   Body: Step-by-step instructions to re-authenticate
4. Continue processing other unrelated tasks
5. Do NOT retry auth automatically
```

#### MCP Server Down
```
1. Queue outbound action to /Plans/QUEUED_ACTIONS.md
2. Attempt to restart: write restart request to watchdog state file
3. Check again after 5 minutes
4. If still down after 15 minutes → create human alert
5. Continue processing tasks that don't need this MCP server
```

#### Logic/Data Error
```
1. Move corrupted/problematic file to /Rejected/{original_name}_ERROR_{timestamp}.md
2. Append error details to the file's front matter
3. Log the quarantine action
4. Continue with remaining /Needs_Action/ files
```

#### External Platform Block
```
1. Mark platform as BLOCKED in Dashboard.md status
2. Create: /Needs_Action/MANUAL_POST_REQUIRED_{PLATFORM}_{DATE}.md with content ready
3. Do NOT attempt any more automated posts to that platform today
4. Log incident with error details
```

### Step 3 — Generate Human Alert (when needed)
Create approval file for email alert:
```markdown
---
type: approval_request
action: send_email
to: apple379tree@gmail.com
subject: "⚠️ AI Employee Alert: {error_type} on {component}"
priority: high
mcp_server: email-mcp
auto_approve: true   # system alerts are auto-approved
---

## Alert Details
- **Component:** {component}
- **Error:** {error_description}
- **Time:** {timestamp}
- **Action Required:** {specific_human_action_needed}
- **Queued Work:** {count} items waiting

## What AI Employee Did
{list of recovery actions taken}

## What You Need to Do
{step-by-step human action}
```
Note: `auto_approve: true` means the orchestrator sends this without waiting for human
file-move. This is the ONLY case where auto-approval is used.

### Step 4 — Update Dashboard Status
Update Dashboard.md:
```markdown
## System Health
| Component | Status | Last Error | Action Taken |
|-----------|--------|------------|--------------|
| facebook-mcp | ⚠️ Degraded | 2026-01-07 10:30 | Queued 2 posts |
| odoo-mcp | ✅ Healthy | — | — |
```

### Step 5 — Resume After Recovery
When the failed component comes back online (detected by watchdog or health check):
1. Read /Plans/QUEUED_ACTIONS.md
2. Process queued items in order (oldest first)
3. Update Dashboard.md status to ✅
4. Log recovery event

## Graceful Degradation Rules

### Gmail API Down
- Queue outgoing emails in `/Plans/EMAIL_QUEUE.md`
- Continue processing all non-email tasks
- Draft emails are saved locally, not lost

### Odoo Unavailable
- Never retry payment operations — always require fresh human approval
- Generate CEO Briefing with "⚠️ Odoo data unavailable" placeholder
- Continue with social/email tasks

### Social Platform Blocked
- Continue with other platforms
- Queue posts for manual posting
- Never bypass platform blocks with workarounds

### Claude Code Unavailable
- Watchers continue collecting → /Needs_Action/ queue grows
- Files are NOT processed until Claude is available
- No data loss (files persist on disk)

### Full System Down
- Watchdog.py restarts all processes
- On restart, Claude processes accumulated /Needs_Action/ queue
- Audit logs preserved

## Example Usage

**Scenario:** instagram-mcp returns 503 three times in a row.

Claude:
1. Classifies as MCP Server Down
2. Queues pending Instagram posts to `/Plans/QUEUED_ACTIONS.md`
3. Creates `/Needs_Action/MCP_DOWN_instagram_20260107.md`
4. Writes restart request to watchdog state
5. Updates Dashboard.md: `instagram-mcp | ⚠️ Down | 10:30 | 1 post queued`
6. Continues processing Facebook and Twitter tasks
7. Does NOT halt the entire AI Employee
8. Logs full incident to `/Logs/`
