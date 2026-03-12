---
skill_id: SKILL_Process_File_Drop
version: "1.0"
trigger: "New FILE_*.md detected in /Needs_Action"
category: file-processing
author: AI Employee System
last_updated: 2026-02-23
---

# SKILL: Process File Drop

## Description

This skill handles any new file that the File System Watcher places in `/Needs_Action`. It reads the file metadata, determines the content type, applies Company Handbook rules, creates a plan, and either completes the task or generates a human approval request.

---

## When to Use

- A `FILE_*.md` metadata file appears in `/Needs_Action/`
- User says: *"Process Needs_Action"* or *"Process the dropped file"*
- The Watcher script triggers Claude automatically
- Ralph Wiggum loop re-injects this prompt after an incomplete pass

---

## Inputs Required

| Input | Path | Purpose |
|-------|------|---------|
| Metadata file | `Needs_Action/FILE_*.md` | Describes the dropped file |
| Company rules | `Company_Handbook.md` | Rules to apply |
| Current state | `Dashboard.md` | Situational awareness |

---

## Step-by-Step Procedure

**Step 1 — Load context**
```
Read Company_Handbook.md (Section 3: Action Boundaries, Section 6: File Management).
Read Dashboard.md to understand current system state.
```

**Step 2 — Read the metadata file**
```
Read Needs_Action/FILE_{name}.md
Extract: original_name, file_type, size_bytes, received, status
```

**Step 3 — Classify the file**

| Extension | Category | Default Action |
|-----------|----------|----------------|
| `.pdf`, `.docx`, `.doc` | document | Summarize key points |
| `.csv`, `.xlsx` | spreadsheet | Parse headers; note row count |
| `.txt`, `.md` | text | Read and summarize |
| `.png`, `.jpg`, `.jpeg` | image | Describe; categorize |
| `.zip`, `.tar` | archive | List contents if possible; flag for review |
| unknown | unknown | Flag for human review; do not open |

**Step 4 — Check handbook rules**
```
Does this file require approval before action? (Section 3)
Does this file contain financial, legal, or medical content? (Section 5 Escalation)
```

**Step 5 — Create a plan**
```
Use SKILL_Generate_Plan.md to create:
  Plans/PLAN_{original_name}_{YYYYMMDD_HHMMSS}.md
```

**Step 6 — Execute or escalate**
- If **no approval needed**: Complete the plan steps, then move metadata to `/Done/`
- If **approval needed**: Create `/Pending_Approval/APPROVAL_{name}_{date}.md`, then STOP

**Step 7 — Update Dashboard and log**
```
Append to Dashboard.md → Recent Activity section
Write log entry to Logs/{YYYY-MM-DD}.json
```

---

## Prompt Template

Copy-paste this into Claude CLI or use it in your orchestrator:

```
You are an AI Employee operating under the rules in Company_Handbook.md.

A new file has been detected in the vault's Needs_Action folder.

Your task — follow these steps exactly:
1. Read Company_Handbook.md (focus on Sections 3, 5, 6, 7).
2. Read the metadata file at: Needs_Action/FILE_{FILENAME}.md
3. Classify the file type and determine required action.
4. Read Skills/SKILL_Generate_Plan.md and create a plan at: Plans/PLAN_{FILENAME}_{TIMESTAMP}.md
5. If the action requires human approval (per Handbook Section 3):
   - Create Pending_Approval/APPROVAL_{FILENAME}_{TIMESTAMP}.md
   - STOP. Do not take the action.
6. If no approval is needed:
   - Execute the plan steps.
   - Move the metadata file to: Done/FILE_{FILENAME}.md
7. Update Dashboard.md (Recent Activity section).
8. Write a log entry to Logs/{TODAY}.json in this format:
   {"timestamp":"...","action_type":"file_drop_processed","actor":"claude_code","file":"{FILENAME}","result":"..."}

Output: <TASK_COMPLETE> when all steps are done.
```

---

## CLI Usage Examples

```bash
# Process a specific file
claude "Read Skills/SKILL_Process_File_Drop.md. Then follow its procedure to process: Needs_Action/FILE_report.md. Read Company_Handbook.md first."

# Process ALL pending files in Needs_Action
claude "Read Skills/SKILL_Process_File_Drop.md and Company_Handbook.md. Process every FILE_*.md in Needs_Action/ one by one. Update Dashboard.md when done. Output <TASK_COMPLETE> when all files are processed."

# Process with Ralph Wiggum loop (keeps going until all files done)
claude --print "Read Skills/SKILL_Process_File_Drop.md and Company_Handbook.md. Process all FILE_*.md in Needs_Action/. Move each completed file to Done/. Output <TASK_COMPLETE> only after ALL files in Needs_Action/ are moved to Done/ or Pending_Approval/."
```

---

## Output Files Produced

| File | Location | Description |
|------|----------|-------------|
| `PLAN_{name}_{ts}.md` | `/Plans/` | Action plan with checkboxes |
| `APPROVAL_{name}_{ts}.md` | `/Pending_Approval/` | If approval required |
| `FILE_{name}.md` | `/Done/` | Completed metadata (moved from Needs_Action) |
| Updated `Dashboard.md` | vault root | Recent activity updated |
| `{date}.json` | `/Logs/` | Audit log entry appended |

---

## Completion Checklist

- [ ] Plan file exists in `/Plans/`
- [ ] File metadata moved to `/Done/` OR approval file in `/Pending_Approval/`
- [ ] `Dashboard.md` updated under "Recent Activity"
- [ ] Log entry written to `/Logs/{date}.json`
- [ ] Output `<TASK_COMPLETE>` (signals Ralph Wiggum loop to allow exit)

---

## Approval Request Template

When creating a file in `/Pending_Approval/`:

```markdown
---
type: approval_request
action: {describe the action}
file: {original filename}
reason: {why action is needed}
created: {ISO timestamp}
expires: {24 hours from created}
status: pending
---

## Action Details
- **What:** {description of action}
- **File:** {filename}
- **Reason:** {justification}

## To APPROVE
Move this file to: /Approved/

## To REJECT
Move this file to: /Rejected/
```

---

*Skill maintained by AI Employee System | Version 1.0*
