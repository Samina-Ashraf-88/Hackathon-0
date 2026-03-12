# SKILL: Reasoning Loop (Ralph Wiggum Pattern)

## Description
Scans the `/Needs_Action/` folder, reasons about each item, and creates
`Plan_{task_id}.md` files in `/Plans/`. Iterates using the Ralph Wiggum Stop hook
until all items are processed and moved to `/Done/`.

## Trigger
Called by the orchestrator when new `.md` files appear in `/Needs_Action/`.
Also callable manually: `claude --print "Execute SKILL_Reasoning_Loop"`

---

## Prompt Template

```
You are executing the Reasoning Loop skill.

STEP 1 — SCAN
Read all files in /Needs_Action/. List each file with its type (email, linkedin, file_drop).

STEP 2 — REASON (for each item)
For each file in /Needs_Action/:
  a. Read the full content.
  b. Identify: What is being requested? Who sent it? What action is needed?
  c. Cross-reference Company_Handbook.md for approval rules.
  d. Determine: Can this be auto-processed OR does it need human approval?

STEP 3 — PLAN
For each item, create a file at /Plans/Plan_{task_id}.md using this schema:
  ---
  task_id: {filename without extension}
  created: {ISO timestamp}
  source_type: {email|linkedin|file_drop}
  status: pending
  requires_approval: {true|false}
  ---
  ## Objective
  {one sentence goal}
  ## Steps
  - [ ] {step 1}
  - [ ] {step 2}
  - [ ] {step 3 — if sensitive, mark: REQUIRES APPROVAL}
  ## Notes
  {any relevant context}

STEP 4 — ROUTE
  - If requires_approval=true: copy item to /Pending_Approval/ and note in plan.
  - If requires_approval=false: mark steps as actionable and proceed to execute.

STEP 5 — EXECUTE SAFE ACTIONS
  Execute any steps that do NOT require approval (e.g., logging, drafting responses).
  For email sends: use SKILL_Send_Email_via_MCP.md.
  For LinkedIn posts: use SKILL_Generate_Sales_Post.md.

STEP 6 — COMPLETE
  After processing each item:
  - Update Dashboard.md "Recent Activity" with a one-line summary.
  - Move processed file: /Needs_Action/{file} → /Done/{file}
  - Update Plan status to "complete".

STEP 7 — CHECK COMPLETION
  If /Needs_Action/ is now empty: output <promise>TASK_COMPLETE</promise>
  If items remain: go back to STEP 1.
```

---

## Ralph Wiggum Stop Hook Integration
The `.claude/settings.json` Stop hook checks for `<promise>TASK_COMPLETE</promise>`.
- If NOT found → hook re-injects this skill prompt and Claude continues.
- If found → hook allows Claude to exit cleanly.
- Maximum iterations: 10 (safety limit).

---

## Example Usage

```bash
# Manual trigger
claude --print "Execute SKILL_Reasoning_Loop per /AI_Employee_Vault/Skills/SKILL_Reasoning_Loop.md" \
  --cwd /path/to/AI_Employee_Vault

# Triggered by orchestrator after watcher detects new file
python orchestrator.py --trigger reasoning_loop
```

---

## Expected Output
- `/Plans/Plan_{task_id}.md` created for each item
- `/Pending_Approval/` populated with items needing human review
- `/Done/` populated with completed items
- `Dashboard.md` updated with activity log
- Final output: `<promise>TASK_COMPLETE</promise>`
