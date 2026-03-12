# SKILL: Send Email via MCP

## Description
Sends an approved email by calling the local MCP email server at localhost:3000.
Only executes when a corresponding file exists in `/Approved/`. Logs result to
`/Logs/` and moves the approval file to `/Done/`.

## Trigger
Called ONLY when a file with `type: email_reply_approval` or `type: email_send`
exists in `/Approved/`. Never called speculatively.

---

## Prompt Template

```
You are executing the Send Email via MCP skill.

PRECONDITION CHECK:
  1. Verify the file exists in /Approved/ (NOT /Pending_Approval/).
  2. Confirm the file has status: pending (not already sent).
  3. Confirm MCP server is running at localhost:3000.

INPUT: Read /Approved/{EMAIL_REPLY_filename}.md

STEP 1 — EXTRACT SEND PARAMETERS
From the approved file, extract:
  - to: recipient email address
  - subject: email subject line
  - body: the approved reply text
  - reply_to_message_id: (if available, for threading)

STEP 2 — VALIDATE
  - Confirm "to" is a valid email format
  - Confirm "subject" is not empty
  - Confirm "body" is not empty
  - If any field is missing: STOP, create error log, do NOT send

STEP 3 — CALL MCP SERVER
Make HTTP POST to localhost:3000/send-email with JSON body:
  {
    "to": "{recipient}",
    "subject": "{subject}",
    "body": "{body}",
    "from": "apple379tree@gmail.com"
  }

STEP 4 — HANDLE RESPONSE
  Success (HTTP 200):
    → Log action to /Logs/YYYY-MM-DD.json with status: success
    → Update the approval file: status: sent, sent_at: {timestamp}
    → Move file: /Approved/{file} → /Done/{file}
    → Update Dashboard.md Recent Activity
  Failure:
    → Log error with full details to /Logs/YYYY-MM-DD.json
    → Move file back to /Pending_Approval/ with error note
    → Alert: "EMAIL SEND FAILED — manual action required"

STEP 5 — LOG ENTRY FORMAT
  {
    "timestamp": "{ISO timestamp}",
    "action_type": "email_send",
    "actor": "claude_code",
    "to": "{recipient}",
    "subject": "{subject}",
    "approval_file": "{filename}",
    "result": "success|failure",
    "error": "{error message if any}"
  }
```

---

## MCP Server API Reference

**Base URL:** `http://localhost:3000`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/send-email` | POST | Send an email via Gmail |
| `/health` | GET | Check server status |
| `/draft-email` | POST | Save draft without sending |

**POST /send-email payload:**
```json
{
  "to": "recipient@example.com",
  "subject": "Subject line",
  "body": "Email body text",
  "from": "apple379tree@gmail.com",
  "cc": "",
  "replyToId": ""
}
```

---

## Safety Rules
1. NEVER call this skill without a file in `/Approved/`.
2. NEVER send to more than 5 recipients in one call.
3. NEVER send if server returns non-200 status — do NOT retry automatically.
4. All sends must be logged — no silent failures.

---

## Example Usage

```bash
# After moving approval file to /Approved/:
claude --print "Execute SKILL_Send_Email_via_MCP for EMAIL_REPLY_abc123.md per /Skills/SKILL_Send_Email_via_MCP.md" \
  --cwd /path/to/AI_Employee_Vault

# Check MCP server health first
curl http://localhost:3000/health
```
