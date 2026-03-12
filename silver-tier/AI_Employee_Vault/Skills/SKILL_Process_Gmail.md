# SKILL: Process Gmail

## Description
Processes email action files dropped into `/Needs_Action/` by the Gmail Watcher.
Reads email content, classifies priority, drafts a reply if appropriate, and routes
to approval or auto-handles based on Company_Handbook rules.

## Trigger
Automatically called by Reasoning Loop when a file matching `EMAIL_*.md` exists
in `/Needs_Action/`. Also callable directly.

---

## Prompt Template

```
You are executing the Process Gmail skill.

INPUT: Read the file at /Needs_Action/{EMAIL_filename}.md

STEP 1 — PARSE EMAIL
Extract from the file frontmatter:
  - from: sender email and name
  - subject: email subject
  - received: timestamp
  - priority: as set by watcher (high/normal/low)
  - body: email content/snippet

STEP 2 — CLASSIFY
Determine:
  a. Is this sender a KNOWN contact? (Check if they appear in previous Done/ files)
  b. Urgency level: high / medium / low
  c. Action required: reply_needed / forward / archive / flag_for_human
  d. Category: invoice_request / general_inquiry / complaint / lead / spam

STEP 3 — DRAFT RESPONSE (if reply_needed)
Write a professional email reply following Company_Handbook.md tone guidelines:
  - Professional, concise, helpful
  - Reference specific details from their email
  - Include a clear next step or call-to-action
  - Sign as: "AI Assistant for Samina Ashraf"

STEP 4 — ROUTE
  If sender is KNOWN contact AND action is routine:
    → Create approval file at /Pending_Approval/EMAIL_REPLY_{task_id}.md
    → Contents: draft reply + original + instructions to approve
  If sender is UNKNOWN or action is sensitive:
    → Create approval file with HIGH_PRIORITY flag
    → Note: "New contact — human review required"
  If email is spam/irrelevant:
    → Log to /Logs/ and move to /Done/ with status: archived

STEP 5 — UPDATE DASHBOARD
Append to Dashboard.md ## Recent Activity:
  - [{timestamp}] Email from {sender}: {subject} — {action taken}
```

---

## Approval File Format

```markdown
---
type: email_reply_approval
task_id: {id}
original_from: {sender}
original_subject: {subject}
created: {timestamp}
expires: {timestamp + 24h}
status: pending
---

## Original Email
{snippet}

## Proposed Reply
{draft reply}

## To Approve
Move this file to /Approved/ folder.

## To Reject
Move this file to /Rejected/ folder.
```

---

## Example Usage

```bash
# Process a specific email file
claude --print "Execute SKILL_Process_Gmail for file EMAIL_abc123.md per /Skills/SKILL_Process_Gmail.md" \
  --cwd /path/to/AI_Employee_Vault

# Process all emails (via reasoning loop)
claude --print "Execute SKILL_Reasoning_Loop" --cwd /path/to/AI_Employee_Vault
```

---

## Notes
- Never send a reply directly — always route through approval workflow.
- For invoice requests, cross-reference /Accounting/Current_Month.md.
- Log all processed emails to /Logs/YYYY-MM-DD.json.
