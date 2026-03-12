# SKILL: Process LinkedIn

## Description
Processes LinkedIn notification/message files dropped by the LinkedIn Watcher.
Handles new messages, connection requests, post comments, and lead inquiries.
Routes to appropriate actions following Company_Handbook.md rules.

## Trigger
Called by Reasoning Loop when `LINKEDIN_*.md` files appear in `/Needs_Action/`.

---

## Prompt Template

```
You are executing the Process LinkedIn skill.

INPUT: Read the file at /Needs_Action/{LINKEDIN_filename}.md

STEP 1 — PARSE NOTIFICATION
Extract from frontmatter:
  - notification_type: message | connection_request | comment | mention | like
  - from_name: sender's name
  - from_profile: LinkedIn URL if available
  - content: message or notification text
  - received: timestamp

STEP 2 — CLASSIFY & PRIORITIZE
  a. Is this a sales lead? (keywords: "interested", "services", "price", "hire", "help")
  b. Is this a networking opportunity?
  c. Is this a comment needing a response?
  d. Priority: high (lead/complaint) | medium (networking) | low (like/generic)

STEP 3 — DETERMINE ACTION
  connection_request:
    → Draft acceptance message (if profile seems relevant to business)
    → Create approval file
  message (lead inquiry):
    → Draft professional response highlighting services from Business_Goals.md
    → Create HIGH_PRIORITY approval file
  message (general):
    → Draft brief professional response
    → Create approval file
  comment on our post:
    → Draft reply that adds value
    → Create approval file
  mention/like:
    → Log and archive (no action needed unless it's a lead signal)

STEP 4 — DRAFT RESPONSE
Write LinkedIn-appropriate response:
  - Max 3 short paragraphs
  - Professional and warm tone
  - Reference their specific message
  - Include relevant service offering if it's a lead
  - End with clear next step (e.g., "Happy to jump on a quick call this week")

STEP 5 — CREATE APPROVAL FILE
Path: /Pending_Approval/LINKEDIN_{type}_{task_id}.md

Contents:
  ---
  type: linkedin_action_approval
  action: {reply_message | accept_connection | reply_comment}
  recipient: {name}
  created: {timestamp}
  status: pending
  ---
  ## Context
  {original message/notification}
  ## Proposed Response
  {draft response}
  ## To Approve: Move to /Approved/
  ## To Reject: Move to /Rejected/

STEP 6 — UPDATE DASHBOARD
Append to Dashboard.md ## Recent Activity:
  - [{timestamp}] LinkedIn {type} from {name}: {action taken}
```

---

## Sales Lead Detection Keywords
Monitor for these signals:
- "interested in your services"
- "can you help with"
- "what do you charge"
- "looking for someone to"
- "automation", "AI", "consulting"
- "how much", "pricing", "rates"

When detected: mark as `priority: high` and flag in Dashboard.

---

## Example Usage

```bash
# Process LinkedIn notifications
claude --print "Execute SKILL_Process_LinkedIn for LINKEDIN_msg_001.md per Skills/SKILL_Process_LinkedIn.md" \
  --cwd /path/to/AI_Employee_Vault
```
