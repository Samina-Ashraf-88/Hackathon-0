# SKILL: Approval Workflow (Human-in-the-Loop)

## Description
Manages the complete Human-in-the-Loop (HITL) approval lifecycle. Creates approval
request files, monitors for human decisions, and routes approved/rejected items to
the appropriate execution or archive path. This skill is the gatekeeper for all
sensitive actions.

## Trigger
Called by other skills when an action requires human approval (per Company_Handbook.md rules).
Also called by orchestrator to check for new decisions in /Approved/ or /Rejected/.

---

## Prompt Template

### Part A — Create Approval Request

```
You are executing Part A of the Approval Workflow skill: CREATE APPROVAL REQUEST.

INPUT:
  - action_type: {email_reply | linkedin_post | linkedin_dm | payment | file_delete}
  - action_data: {the proposed action details}
  - source_task_id: {originating task file}
  - urgency: {high | medium | low}
  - expires_in_hours: {24 | 48 | 72}

STEP 1 — GENERATE APPROVAL FILE
  Filename: /Pending_Approval/{ACTION_TYPE}_{task_id}_{YYYYMMDD_HHMM}.md

  Contents:
  ---
  type: approval_request
  action_type: {action_type}
  task_id: {task_id}
  created: {ISO timestamp}
  expires: {ISO timestamp + expires_in_hours}
  urgency: {urgency}
  status: pending
  ---
  ## What Needs Approval
  {clear 1-2 sentence description of what the AI wants to do}
  ## Details
  {full action details — recipient, content, etc.}
  ## Why This Action
  {brief reasoning — what triggered this need}
  ## Risk Level
  {Low / Medium / High} — {brief explanation}
  ## To APPROVE: Move this file to /Approved/
  ## To REJECT: Move this file to /Rejected/
  ## To EDIT: Modify the "Details" section, then move to /Approved/

STEP 2 — ALERT DASHBOARD
  Append to Dashboard.md ## Pending Approvals:
  - [{timestamp}] {urgency} — {action_type}: {brief description} → see /Pending_Approval/{filename}
```

### Part B — Process Decision

```
You are executing Part B of the Approval Workflow skill: PROCESS DECISION.

STEP 1 — SCAN FOR DECISIONS
  Check /Approved/ for any new files (recently moved from /Pending_Approval/).
  Check /Rejected/ for any new files.

STEP 2 — PROCESS APPROVED ITEMS
  For each file in /Approved/ with status: pending:
    a. Read action_type from frontmatter
    b. Route to appropriate execution skill:
       - email_reply → execute SKILL_Send_Email_via_MCP.md
       - linkedin_post → execute linkedin_poster.py
       - linkedin_dm → execute linkedin_poster.py with --type dm
    c. Update file status: approved, processed_at: {timestamp}

STEP 3 — PROCESS REJECTED ITEMS
  For each file in /Rejected/ with status: pending:
    a. Log the rejection to /Logs/YYYY-MM-DD.json
    b. Move source task file back to /Needs_Action/ with note: "REJECTED — needs revision"
       OR move to /Done/ with status: rejected_final
    c. Update Dashboard.md

STEP 4 — CHECK EXPIRED ITEMS
  For items in /Pending_Approval/ past their expires timestamp:
    a. Mark status: expired
    b. Log to /Logs/
    c. Alert in Dashboard.md: "EXPIRED APPROVAL: {filename} — action not taken"
    d. Move to /Done/ with status: expired

STEP 5 — UPDATE DASHBOARD
  Remove processed items from Dashboard.md ## Pending Approvals section.
  Add to ## Recent Activity.
```

---

## Approval File States

| State | Location | Next Action |
|-------|----------|-------------|
| pending | /Pending_Approval/ | Waiting for human |
| approved | /Approved/ | Execute action |
| rejected | /Rejected/ | Log and archive |
| expired | /Done/ | Log and alert |
| processed | /Done/ | Complete |

---

## Example Usage

```bash
# Create approval request for an email reply
claude --print "Execute SKILL_Approval_Workflow Part A for email_reply action. Task ID: EMAIL_abc123. Draft reply content: [content]. Urgency: medium." \
  --cwd /path/to/AI_Employee_Vault

# Process any pending decisions (run after moving files to /Approved/)
claude --print "Execute SKILL_Approval_Workflow Part B — process all decisions in /Approved/ and /Rejected/" \
  --cwd /path/to/AI_Employee_Vault
```

---

## Integration with Other Skills
- `SKILL_Process_Gmail.md` → calls Part A for all email replies
- `SKILL_Process_LinkedIn.md` → calls Part A for all LinkedIn actions
- `SKILL_Generate_Sales_Post.md` → calls Part A for all posts
- `SKILL_Send_Email_via_MCP.md` → called by Part B after approval
- `SKILL_Reasoning_Loop.md` → calls Part B at end of each loop iteration
