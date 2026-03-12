---
last_updated: 2026-02-23
status: active
version: "0.1"
---

# AI Employee Dashboard

> **Tagline:** Your life and business on autopilot. Local-first, agent-driven, human-in-the-loop.

---

## Bank Balance

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| Current Balance    | `$0.00` *(placeholder — update via Finance Watcher)* |
| Last Updated       | —                                          |
| Pending Outgoing   | $0.00                                      |
| Flagged (>$500)    | 0 items                                    |

---

## Needs Action Queue

> Files in `/Needs_Action` awaiting Claude processing:

| File | Type | Received | Priority |
|------|------|----------|----------|
| *(empty)* | — | — | — |

**Count:** 0 pending *(2 files processed 2026-02-23)*

---

## Pending Approvals

> Items in `/Pending_Approval` requiring YOUR decision before Claude acts:

| Item | Action Required | Amount | Deadline |
|------|----------------|--------|----------|
| *(none)* | — | — | — |

**Count:** 0 pending approvals

---

## Active Projects

| Project Name | Due Date | Budget | Status  | Owner |
|--------------|----------|--------|---------|-------|
| *(none yet)* | —        | —      | —       | —     |

---

## Pending Messages

| Source    | From | Subject | Priority | Received |
|-----------|------|---------|----------|----------|
| *(empty)* | —    | —       | —        | —        |

---

## Recent Activity

| Timestamp | Action | File | Result |
|-----------|--------|------|--------|
| 2026-02-23 22:30 | file_drop_processed | content.md (empty .md, 0 bytes) | Archived to /Done — file was empty |
| 2026-02-23 22:30 | file_drop_processed | hackathon_brief.pdf (PDF, 513 KB, 29 pages) | Summarized & archived to /Done — Hackathon 0 brief: Building Autonomous FTEs |

---

## System Status

| Component             | Status            | Last Check          | Notes                        |
|-----------------------|-------------------|---------------------|------------------------------|
| File Watcher          | ✅ Running        | 2026-02-23 22:28    | Run `filesystem_watcher.py`  |
| Claude Reasoning      | ✅ Active         | 2026-02-23 22:30    | Processed 2 files            |
| Vault Read/Write      | ✅ Ready          | 2026-02-23 22:30    | Obsidian vault initialized   |
| Ralph Wiggum Hook     | ✅ Active         | 2026-02-23 22:30    | See `.claude/settings.json`  |

---

## Quick Commands

```bash
# Process all pending files
claude "Read Skills/SKILL_Process_File_Drop.md, then process all files in Needs_Action/. Read Company_Handbook.md first."

# Generate daily briefing
claude "Read Skills/SKILL_Daily_Briefing.md, then generate today's briefing. Scan Needs_Action/, Pending_Approval/, Done/, Plans/. Save to Briefings/."

# Create a plan for a task
claude "Read Skills/SKILL_Generate_Plan.md, then create a plan for: [describe task]. Save to Plans/."
```

---

*Dashboard maintained by AI Employee v0.1 | Update by running a briefing skill*
