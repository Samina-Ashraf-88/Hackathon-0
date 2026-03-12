# SKILL: Ralph Wiggum Autonomous Loop

## Description
The Ralph Wiggum pattern is the AI Employee's persistence engine. Named after the
character who keeps showing up no matter what, this skill defines how Claude operates
in a continuous loop until ALL tasks in /Needs_Action/ are complete. The Stop hook
(hooks/stop_hook.py) intercepts Claude's exit and re-injects this prompt until done.

## How the Loop Works
```
┌─────────────────────────────────────┐
│  Orchestrator triggers Claude       │
│  with this skill as prompt          │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  Claude reads /Needs_Action/        │
│  Processes each file                │
│  Tries to exit                      │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  Stop Hook intercepts exit          │
│  Checks: promise present?           │
│  Checks: /Needs_Action/ empty?      │
└────────┬─────────────┬──────────────┘
         │ YES (done)  │ NO (not done)
         ▼             ▼
    Allow exit    Re-inject prompt
    ✅ Complete   (max 10 iterations)
```

## Trigger
- This skill is the PRIMARY entry point for the orchestrator
- Every time the orchestrator detects files in /Needs_Action/ and triggers Claude,
  it uses this skill as the framing prompt
- The Stop hook will continuously re-invoke this skill until complete

## Step-by-Step Procedure

### Iteration Start — Read and Plan
```
1. Read Dashboard.md for current system state
2. Read Company_Handbook.md for rules
3. List all files in /Needs_Action/ (sorted by creation time, oldest first)
4. For each file, determine required SKILL:
   - EMAIL_*.md         → SKILL_Process_Gmail
   - LINKEDIN_*.md      → SKILL_Process_LinkedIn
   - FACEBOOK_*.md      → SKILL_Facebook_Instagram_Twitter_Integration
   - INSTAGRAM_*.md     → SKILL_Facebook_Instagram_Twitter_Integration
   - TWITTER_*.md       → SKILL_Facebook_Instagram_Twitter_Integration
   - ODOO_*.md          → SKILL_Odoo_Accounting_Actions
   - WEEKLY_BRIEFING_*  → SKILL_Weekly_CEO_Briefing
   - SYSTEM_ERROR_*     → SKILL_Error_Recovery_Graceful_Degradation
   - POST_REQUEST_*     → SKILL_Process_Social_Post
   - MCP_DOWN_*         → SKILL_Error_Recovery_Graceful_Degradation
   - Other              → SKILL_Reasoning_Loop (default)
5. Create /Plans/PLAN_{session_id}_{date}.md with task list
```

### Iteration Body — Execute Skills
```
For each file in /Needs_Action/ (in order):
  1. Mark file as "in_progress" by reading it (Claude internally tracks state)
  2. Load and execute the matching SKILL
  3. Create approval file if needed → /Pending_Approval/
  4. Log action via SKILL_Audit_Logging
  5. Move file to /Done/ if processing complete
  6. Move to next file
```

### Iteration End — Completion Check
```
After processing all current /Needs_Action/ files:
  remaining = list files in /Needs_Action/
  pending_approvals = list files in /Pending_Approval/

  If remaining is empty AND (pending_approvals is empty OR only approval files remain):
    → Update Dashboard.md
    → Update /Plans/PLAN_{session_id}.md status to "COMPLETE"
    → Output: <promise>TASK_COMPLETE</promise>
    → Allow Claude to exit

  If remaining has new items (watchers added more while processing):
    → Continue loop (Stop hook will re-inject)

  If remaining has ONLY items blocked on human approval:
    → Note: "Waiting for human approval on {count} items"
    → Output: <promise>TASK_COMPLETE</promise>
    → Human-in-the-loop is a VALID completion state
```

### Human-in-the-Loop Pause
When ALL remaining work requires human approval:
```
This is a COMPLETE state. Output <promise>TASK_COMPLETE</promise>.

Rationale: The AI Employee has done everything it can autonomously.
The human must review /Pending_Approval/ files and move them to /Approved/.
The orchestrator will re-trigger Claude when new /Approved/ files appear.
```

## Safety Limits
```
max_iterations = 10 (configurable via RALPH_MAX_ITERATIONS env var)
iteration_timeout = 30 minutes per iteration
max_files_per_iteration = 20 (process in batches to prevent context overflow)
```

## Plan File Format
Created at `/Plans/PLAN_ralph_{session_id}_{date}.md`:
```markdown
---
created: {ISO_TIMESTAMP}
session_id: {session_id}
status: in_progress | complete | partial | blocked
iteration: {n} of max {max}
---

# Ralph Wiggum Execution Plan

## Task Queue (this iteration)
| File | Type | Status | SKILL |
|------|------|--------|-------|
| EMAIL_001.md | email | ✅ done | SKILL_Process_Gmail |
| FACEBOOK_002.md | social | ✅ done | SKILL_Facebook_Instagram_Twitter |
| ODOO_003.md | accounting | ⏳ pending_approval | SKILL_Odoo_Accounting_Actions |

## Pending Human Actions
- /Pending_Approval/ODOO_INVOICE_003.md — move to /Approved/ to create invoice

## Completion
- [ ] All files processed
- [ ] All immediate tasks done
- [ ] Output: <promise>TASK_COMPLETE</promise>
```

## Integration with Stop Hook
The `hooks/stop_hook.py` works in tandem with this skill:
1. Claude finishes an iteration
2. Hook reads the session transcript
3. Hook checks for `<promise>TASK_COMPLETE</promise>` AND empty /Needs_Action/
4. If not done: hook returns `{"action": "block", "new_message": "Continue processing..."}`
5. If done: hook returns `{"action": "continue"}`

## CLI Usage
```bash
# Trigger the Ralph loop manually
claude --print \
  "Execute SKILL_Ralph_Wiggum_Autonomous_Loop. \
   Vault: E:/hackathon-0/silver-tier/AI_Employee_Vault. \
   Process all items in /Needs_Action/." \
  --cwd "E:/hackathon-0/silver-tier/AI_Employee_Vault"
```

## Example Scenario — Full Loop
**Situation:** 3 files in /Needs_Action/:
1. `EMAIL_Invoice_request.md`
2. `FACEBOOK_DM_lead.md`
3. `WEEKLY_BRIEFING_20260202.md`

**Iteration 1:**
- Claude processes EMAIL → drafts reply → creates /Pending_Approval/EMAIL_reply.md
- Claude processes FACEBOOK_DM → classifies as lead → creates /Pending_Approval/SOCIAL_FB_reply.md
- Claude starts WEEKLY_BRIEFING → calls Odoo → generates briefing → writes to /Briefings/
- All 3 source files moved to /Done/
- /Needs_Action/ is now empty
- Outputs: `<promise>TASK_COMPLETE</promise>`

**Stop Hook:** Detects promise + empty /Needs_Action/ → allows exit
**Result:** Loop ran 1 iteration, all tasks complete
