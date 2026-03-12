# Personal AI Employee — Bronze Tier

> **Tagline:** Your life and business on autopilot. Local-first, agent-driven, human-in-the-loop.

**Hackathon:** Personal AI Employee Hackathon 0 — Building Autonomous FTEs in 2026
**Tier:** 🥉 Bronze (Minimum Viable Deliverable)
**Stack:** Claude Code · Obsidian · Python 3.13+ · watchdog

---

## What This Builds

A local-first AI Employee that:

1. **Watches** your `Inbox/` folder for dropped files (filesystem watcher)
2. **Processes** each file — classifying it, creating a plan, applying Company Handbook rules
3. **Manages** an Obsidian vault as its memory and dashboard
4. **Persists** autonomously via the Ralph Wiggum Stop Hook until all tasks are done
5. **Implements** all AI logic as reusable Agent Skills (`SKILL_*.md` files)

---

## Project Structure

```
hackathon-0/
├── AI_Employee_Vault/               ← Obsidian vault (open this in Obsidian)
│   ├── Dashboard.md                 ← Real-time status dashboard
│   ├── Company_Handbook.md          ← Rules of Engagement for the AI
│   ├── Inbox/                       ← DROP FILES HERE to trigger watcher
│   ├── Needs_Action/                ← Watcher places metadata here
│   ├── Done/                        ← Completed tasks
│   ├── Plans/                       ← Claude-generated action plans
│   ├── Logs/                        ← Structured JSON audit logs
│   ├── Pending_Approval/            ← Items needing YOUR decision
│   ├── Approved/                    ← You move files here to approve
│   ├── Rejected/                    ← You move files here to reject
│   ├── Briefings/                   ← Daily briefing reports
│   └── Skills/
│       ├── SKILL_Process_File_Drop.md   ← Handles new file drops
│       ├── SKILL_Generate_Plan.md       ← Creates structured plans
│       └── SKILL_Daily_Briefing.md      ← Daily status briefing
├── .claude/
│   ├── settings.json                ← Ralph Wiggum Stop Hook config
│   └── hooks/
│       └── ralph_wiggum.py          ← Keeps Claude working until done
├── filesystem_watcher.py            ← Main watcher script
├── requirements.txt
└── README.md
```

---

## Setup Instructions

### Step 1 — Install Python dependencies

```bash
cd E:\hackathon-0
pip install -r requirements.txt
```

Verify:
```bash
python -c "import watchdog; print('watchdog OK')"
```

### Step 2 — Verify Claude Code is installed

```bash
claude --version
```

If not installed:
```bash
npm install -g @anthropic/claude-code
```

### Step 3 — Open the vault in Obsidian

1. Open Obsidian
2. Click **"Open folder as vault"**
3. Select: `E:\hackathon-0\AI_Employee_Vault`
4. You should see `Dashboard.md`, `Company_Handbook.md`, and the `Skills/` folder

### Step 4 — Start the File System Watcher

Open a terminal in `E:\hackathon-0` and run:

```bash
# Standard mode (watchdog-based, efficient)
python filesystem_watcher.py

# With polling fallback (no watchdog needed)
python filesystem_watcher.py --poll

# Auto-trigger Claude when a file is dropped
python filesystem_watcher.py --auto-trigger

# Custom vault path
python filesystem_watcher.py --vault "C:\path\to\AI_Employee_Vault"
```

You should see:
```
==============================
 AI Employee — File System Watcher
==============================
Vault        : E:\hackathon-0\AI_Employee_Vault
Watching     : E:\hackathon-0\AI_Employee_Vault\Inbox
Auto-trigger : OFF (manual)
✅ watchdog observer started on: E:\hackathon-0\AI_Employee_Vault\Inbox
   Drop files into Inbox/ to trigger processing.
   Press Ctrl+C to stop.
```

### Step 5 — Test: Drop a file into Inbox

In a second terminal or Windows Explorer, copy any file into `Inbox/`:

```bash
# From the hackathon-0 directory
cp "Personal AI Employee Hackathon 0_ Building Autonomous FTEs in 2026.pdf" AI_Employee_Vault/Inbox/test_doc.pdf
```

The watcher output should show:
```
↘  New file detected: test_doc.pdf
   ✔ Copied  → FILE_test_doc.pdf
   ✔ Metadata → FILE_test_doc.md
   ┌─ To process manually ───────────────────────────────────────┐
   │  claude "Read Skills/SKILL_Process_File_Drop.md.            │
   │          Process Needs_Action/FILE_test_doc.md"             │
   └─────────────────────────────────────────────────────────────┘
✅  Done: test_doc.pdf
```

Check that `Needs_Action/FILE_test_doc.md` now exists in the vault.

---

## Using Claude to Process Files

### Process a single dropped file

```bash
cd E:\hackathon-0
claude "Read AI_Employee_Vault/Skills/SKILL_Process_File_Drop.md. Then process AI_Employee_Vault/Needs_Action/FILE_test_doc.md following the skill procedure. Read AI_Employee_Vault/Company_Handbook.md first. Create a plan in AI_Employee_Vault/Plans/ and update AI_Employee_Vault/Dashboard.md."
```

### Process ALL pending files (with Ralph Wiggum loop)

```bash
claude --print "Read AI_Employee_Vault/Skills/SKILL_Process_File_Drop.md and AI_Employee_Vault/Company_Handbook.md. Process every FILE_*.md in AI_Employee_Vault/Needs_Action/ one by one. For each file: create a plan in Plans/, move completed files to Done/. Update Dashboard.md when all done. Output <TASK_COMPLETE> only after ALL files are moved out of Needs_Action/."
```

The Ralph Wiggum Stop Hook (`.claude/settings.json`) will keep Claude re-running until `Needs_Action/` is empty or `<TASK_COMPLETE>` is output.

### Generate a daily briefing

```bash
claude "Read AI_Employee_Vault/Skills/SKILL_Daily_Briefing.md and AI_Employee_Vault/Company_Handbook.md. Generate today's briefing. Scan Needs_Action/, Pending_Approval/, Done/, Plans/. Save to AI_Employee_Vault/Briefings/. Update Dashboard.md."
```

### Create a plan for any task

```bash
claude "Read AI_Employee_Vault/Skills/SKILL_Generate_Plan.md. Create a plan for: [describe your task here]. Read Company_Handbook.md first. Save to AI_Employee_Vault/Plans/."
```

---

## Human-in-the-Loop Workflow

When Claude needs your approval (e.g., sending an email, any action over $500):

1. Claude creates a file in `AI_Employee_Vault/Pending_Approval/`
2. You review the file in Obsidian
3. **To APPROVE:** Move/drag the file to `AI_Employee_Vault/Approved/`
4. **To REJECT:** Move/drag the file to `AI_Employee_Vault/Rejected/`
5. Run Claude again to execute approved actions

---

## Ralph Wiggum Stop Hook

The hook is already configured in `.claude/settings.json`. It activates automatically when running Claude Code from this project directory.

**How it works:**
- After each Claude turn, the hook script checks `Needs_Action/` for pending files
- If files remain → blocks Claude's exit and re-injects the processing prompt
- If empty → allows Claude to exit cleanly
- Hard cap at 10 iterations to prevent infinite loops

**Test the hook manually:**
```bash
echo '{"ralph_iteration": 0}' | python .claude/hooks/ralph_wiggum.py
```

---

## Keeping the Watcher Running (Production)

### Option A: PM2 (recommended)

```bash
npm install -g pm2
pm2 start filesystem_watcher.py --interpreter python
pm2 save
pm2 startup    # follow the printed command to enable on boot
pm2 logs filesystem_watcher   # tail logs
```

### Option B: Windows Task Scheduler

```powershell
# Run as Administrator
$action = New-ScheduledTaskAction `
  -Execute "python" `
  -Argument "E:\hackathon-0\filesystem_watcher.py" `
  -WorkingDirectory "E:\hackathon-0"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "AI_Employee_Watcher" -Action $action -Trigger $trigger -Settings $settings
```

---

## Judging Checklist — Bronze Tier

| Requirement | Status | Location |
|-------------|--------|----------|
| Obsidian vault named `AI_Employee_Vault` | ✅ | `AI_Employee_Vault/` |
| `/Inbox`, `/Needs_Action`, `/Done` folders | ✅ | vault root |
| `Dashboard.md` with placeholder sections | ✅ | `AI_Employee_Vault/Dashboard.md` |
| `Company_Handbook.md` with rules | ✅ | `AI_Employee_Vault/Company_Handbook.md` |
| Working file system Watcher | ✅ | `filesystem_watcher.py` |
| Claude reads/writes to vault | ✅ | Via CLI commands above |
| AI functionality as Agent Skills | ✅ | `Skills/SKILL_*.md` (3 skills) |
| Ralph Wiggum loop | ✅ | `.claude/hooks/ralph_wiggum.py` |
| Logging & error handling | ✅ | `Logs/` + watcher logging |

---

## Security Notes

- **Never** put credentials, `.env` files, or API tokens inside the vault
- The `.gitignore` already excludes `.env`, credentials, and session files
- All actions touching external systems require human approval (see `Company_Handbook.md`)
- Audit logs are written to `Logs/YYYY-MM-DD.json` (append-only)

---

*AI Employee v0.1 — Bronze Tier | Hackathon 0 Submission*
