# Personal AI Employee — Silver Tier

> *Your life and business on autopilot. Local-first, agent-driven, human-in-the-loop.*

A fully local, privacy-first AI Employee powered by **Claude Code** and **Obsidian**.
Monitors Gmail & LinkedIn, drafts responses and posts, generates plans, and executes
approved actions — all through a vault-based approval workflow.

---

## Architecture Overview

```
External Sources                    AI Employee
──────────────                    ──────────────────────────────────────────
Gmail           →  gmail_watcher.py     ─┐
LinkedIn        →  linkedin_watcher.py   ├→ /Needs_Action/  →  Claude Code
File System     →  (Bronze tier)        ─┘        ↓                ↓
                                              Plans/*.md    /Pending_Approval/
                                                              ↓ (human reviews)
                                                         /Approved/
                                                              ↓
                                             MCP Server / linkedin_poster.py
                                                              ↓
                                                    Gmail Send / LinkedIn Post
```

**Components:**
| Component | File | Purpose |
|-----------|------|---------|
| Gmail Watcher | `watchers/gmail_watcher.py` | Polls Gmail every 2 min |
| LinkedIn Watcher | `watchers/linkedin_watcher.py` | Polls LinkedIn every 5 min |
| LinkedIn Poster | `watchers/linkedin_poster.py` | Posts approved content |
| Orchestrator | `watchers/orchestrator.py` | Master controller |
| MCP Email Server | `mcp-email-server/index.js` | Sends emails via Gmail API |
| Ralph Wiggum Hook | `hooks/stop_hook.py` | Keeps Claude looping until done |
| Skills (×6) | `AI_Employee_Vault/Skills/` | Claude agent behaviors |

---

## Quick Start

### Prerequisites
- Python 3.13+
- Node.js v24+ LTS
- Claude Code CLI (`npm install -g @anthropic/claude-code`)
- Obsidian v1.10.6+ (open `AI_Employee_Vault` as vault)

---

## Step-by-Step Setup

### Step 1 — Install Python Dependencies

```bash
cd E:/hackathon-0/silver-tier
pip install -r requirements.txt
playwright install chromium
```

### Step 2 — Install Node.js MCP Server Dependencies

```bash
cd E:/hackathon-0/silver-tier/mcp-email-server
npm install
cd ..
```

### Step 3 — Configure Environment Variables

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and set DRY_RUN=true for testing (keeps everything safe)
# Change to DRY_RUN=false only when ready for real sends
```

### Step 4 — Set Up Gmail OAuth Authentication

Your `credentials.json` is already in place (copied from the client_secret file).

```bash
# Run the auth flow — opens a browser window
python watchers/gmail_watcher.py --auth
```

1. Browser opens → Log in with `apple379tree@gmail.com`
2. Grant permissions to Gmail
3. `token.json` is saved automatically
4. Close the browser tab

**Verify it works:**
```bash
python watchers/gmail_watcher.py --once
# Should print: "Found X new email(s)"
```

### Step 5 — Set Up LinkedIn Session

```bash
# Opens a visible browser for manual login
python watchers/linkedin_watcher.py --login
```

1. Browser opens → Log in to LinkedIn as `samina-ashraf-8386453b3`
2. Complete login (including any 2FA)
3. Wait for the feed to load
4. Session is saved automatically to `.linkedin_session/`
5. Close when done

**Verify it works:**
```bash
python watchers/linkedin_watcher.py --once
# Should print: "Found X item(s)"
```

### Step 6 — Configure the Ralph Wiggum Stop Hook

The stop hook is registered in `.claude/settings.json`. For it to work globally,
also add it to your user-level Claude settings:

```bash
# On Windows, Claude Code settings are at:
# %APPDATA%\Claude\settings.json
# Merge in the hooks config from .claude/settings.json
```

Or use project-level settings by running Claude from this directory:
```bash
cd E:/hackathon-0/silver-tier
claude --cwd AI_Employee_Vault "Execute SKILL_Reasoning_Loop"
```

### Step 7 — Start the MCP Email Server

```bash
cd E:/hackathon-0/silver-tier/mcp-email-server
node index.js
```

You should see:
```
╔══════════════════════════════════════════╗
║   AI Employee — MCP Email Server v1.0   ║
║  Listening: http://127.0.0.1:3000        ║
║  Dry Run:   ENABLED (no real sends)      ║
╚══════════════════════════════════════════╝
✅ Gmail connected: apple379tree@gmail.com
```

**Test it:**
```bash
curl http://localhost:3000/health

# Test sending (dry run — won't actually send)
curl -X POST http://localhost:3000/send-email \
  -H "Content-Type: application/json" \
  -d '{"to":"test@example.com","subject":"Test","body":"Hello from AI Employee"}'
```

### Step 8 — Open Vault in Obsidian

1. Open Obsidian
2. Open Vault → Navigate to `E:\hackathon-0\silver-tier\AI_Employee_Vault`
3. You'll see: Dashboard.md, Company_Handbook.md, Skills/, Needs_Action/, etc.

---

## Testing the System

### Test 1 — Simulate an Email Arriving

Test email files are pre-created in `/Needs_Action/`. Run the reasoning loop:

```bash
claude --print "Execute SKILL_Reasoning_Loop as defined in AI_Employee_Vault/Skills/SKILL_Reasoning_Loop.md. Vault: E:/hackathon-0/silver-tier/AI_Employee_Vault" --cwd "E:/hackathon-0/silver-tier/AI_Employee_Vault"
```

**Expected result:**
- `Plans/Plan_EMAIL_TEST_001.md` created
- `Pending_Approval/EMAIL_REPLY_*.md` created
- `Dashboard.md` updated with activity

### Test 2 — Approve an Email Reply

1. Open Obsidian → navigate to `Pending_Approval/`
2. Review the approval file
3. Move it to `Approved/` folder (drag in Obsidian or rename path)
4. Orchestrator detects it and calls MCP server

```bash
# Or manually trigger the send after approving:
python watchers/trigger_claude.py --skill SKILL_Send_Email_via_MCP \
  --context "Process the approved file in /Approved/"
```

### Test 3 — Generate a LinkedIn Sales Post

```bash
claude --print "Execute SKILL_Generate_Sales_Post as defined in AI_Employee_Vault/Skills/SKILL_Generate_Sales_Post.md. Use content pillar 1: AI Automation Tips. Vault: E:/hackathon-0/silver-tier/AI_Employee_Vault" --cwd "E:/hackathon-0/silver-tier/AI_Employee_Vault"
```

**Expected result:**
- `Pending_Approval/LINKEDIN_POST_*.md` created with draft post
- Review in Obsidian, move to `Approved/` to publish

### Test 4 — Publish an Approved LinkedIn Post (Dry Run)

```bash
# Set DRY_RUN=true in .env first
python watchers/linkedin_poster.py --scan-approved --vault "E:/hackathon-0/silver-tier/AI_Employee_Vault"
```

### Test 5 — Full Reasoning Loop

```bash
# Run with Ralph Wiggum loop (processes all items until Needs_Action is empty)
python watchers/trigger_claude.py --skill SKILL_Reasoning_Loop
```

### Test 6 — Process LinkedIn Lead

The test file `LINKEDIN_MESSAGE_TEST_001.md` simulates a sales lead:

```bash
python watchers/trigger_claude.py --skill SKILL_Process_LinkedIn \
  --context "Process LINKEDIN_MESSAGE_TEST_001.md — this is a high priority sales lead"
```

---

## Running Continuously

### Option A — Windows Task Scheduler (Recommended for Windows)

Import the XML task files:

```powershell
# Run as Administrator in PowerShell:
schtasks /create /xml "E:\hackathon-0\silver-tier\schedule\windows_task_orchestrator.xml" /tn "AIEmployee\Orchestrator"
schtasks /create /xml "E:\hackathon-0\silver-tier\schedule\windows_task_gmail_watcher.xml" /tn "AIEmployee\GmailWatcher"
schtasks /create /xml "E:\hackathon-0\silver-tier\schedule\windows_task_sales_post.xml" /tn "AIEmployee\SalesPost"
```

Or import via GUI: Task Scheduler → Action → Import Task → select each XML file.

### Option B — PM2 (Cross-platform, recommended for dev)

```bash
npm install -g pm2

# Start all watchers
pm2 start E:/hackathon-0/silver-tier/watchers/gmail_watcher.py --name gmail_watcher --interpreter python3
pm2 start E:/hackathon-0/silver-tier/watchers/linkedin_watcher.py --name linkedin_watcher --interpreter python3
pm2 start E:/hackathon-0/silver-tier/watchers/orchestrator.py --name orchestrator --interpreter python3
pm2 start E:/hackathon-0/silver-tier/mcp-email-server/index.js --name mcp_email

# Save and enable on reboot
pm2 save
pm2 startup

# Monitor
pm2 status
pm2 logs gmail_watcher
```

### Option C — Manual (for development/testing)

```bash
# Terminal 1: MCP Server
cd mcp-email-server && node index.js

# Terminal 2: Gmail Watcher
python watchers/gmail_watcher.py --vault AI_Employee_Vault

# Terminal 3: LinkedIn Watcher
python watchers/linkedin_watcher.py --vault AI_Employee_Vault

# Terminal 4: Orchestrator
python watchers/orchestrator.py --vault AI_Employee_Vault
```

---

## Human-in-the-Loop Workflow

```
1. Watcher detects event
         ↓
2. Creates file in /Needs_Action/
         ↓
3. Orchestrator triggers Claude
         ↓
4. Claude runs SKILL_Reasoning_Loop
         ↓
5. Creates Plan_*.md in /Plans/
         ↓
6. Sensitive actions → /Pending_Approval/
         ↓
7. YOU review and move to /Approved/ or /Rejected/
         ↓
8. Orchestrator detects /Approved/ file
         ↓
9. Executes action (send email / post LinkedIn)
         ↓
10. Logs result, moves to /Done/
```

**To approve:** Move file from `/Pending_Approval/` to `/Approved/`
**To reject:** Move file from `/Pending_Approval/` to `/Rejected/`
**To edit:** Open file, modify the "Details" section, then move to `/Approved/`

---

## Available Claude CLI Commands

```bash
# Run the full reasoning loop
claude "Execute SKILL_Reasoning_Loop per AI_Employee_Vault/Skills/SKILL_Reasoning_Loop.md"

# Process Gmail items
claude "Execute SKILL_Process_Gmail for EMAIL_TEST_001.md"

# Process LinkedIn items
claude "Execute SKILL_Process_LinkedIn for LINKEDIN_MESSAGE_TEST_001.md"

# Generate LinkedIn sales post
claude "Execute SKILL_Generate_Sales_Post — use content pillar 3: Industry Trends"

# Send an approved email
claude "Execute SKILL_Send_Email_via_MCP — process all files in /Approved/"

# Run approval workflow check
claude "Execute SKILL_Approval_Workflow Part B — process all decisions"
```

---

## Directory Structure

```
silver-tier/
├── AI_Employee_Vault/              ← Obsidian vault (open this in Obsidian)
│   ├── CLAUDE.md                   ← Claude Code configuration & rules
│   ├── Dashboard.md                ← Real-time status overview
│   ├── Company_Handbook.md         ← Rules of engagement
│   ├── Business_Goals.md           ← Goals, metrics, services
│   ├── Needs_Action/               ← Inbox: new items for Claude to process
│   ├── Plans/                      ← Claude-generated Plan_*.md files
│   ├── Pending_Approval/           ← Items waiting for human review
│   ├── Approved/                   ← Human-approved items (ready to execute)
│   ├── Rejected/                   ← Rejected items
│   ├── Done/                       ← Completed items archive
│   ├── Logs/                       ← JSON action logs (90-day retention)
│   ├── Briefings/                  ← Monday CEO briefings
│   ├── Inbox/                      ← Raw inbox (Bronze tier)
│   ├── Accounting/                 ← Financial tracking
│   └── Skills/                     ← Agent skill definitions
│       ├── SKILL_Reasoning_Loop.md
│       ├── SKILL_Process_Gmail.md
│       ├── SKILL_Process_LinkedIn.md
│       ├── SKILL_Generate_Sales_Post.md
│       ├── SKILL_Send_Email_via_MCP.md
│       └── SKILL_Approval_Workflow.md
├── watchers/
│   ├── base_watcher.py             ← Abstract base class
│   ├── gmail_watcher.py            ← Gmail monitoring
│   ├── linkedin_watcher.py         ← LinkedIn monitoring
│   ├── linkedin_poster.py          ← LinkedIn posting
│   ├── orchestrator.py             ← Master controller
│   └── trigger_claude.py           ← Manual Claude trigger helper
├── mcp-email-server/
│   ├── package.json
│   └── index.js                    ← MCP HTTP server (localhost:3000)
├── hooks/
│   └── stop_hook.py                ← Ralph Wiggum loop hook
├── schedule/
│   ├── cron_jobs.txt               ← Unix cron schedule
│   ├── windows_task_orchestrator.xml
│   ├── windows_task_gmail_watcher.xml
│   └── windows_task_sales_post.xml
├── .claude/
│   └── settings.json               ← Claude Code hook registration
├── credentials.json                ← Google OAuth client (DO NOT COMMIT)
├── .env.example                    ← Environment variable template
├── .env                            ← Your actual env vars (DO NOT COMMIT)
├── .gitignore
└── requirements.txt
```

---

## Security Notes

- `credentials.json` and `token.json` are gitignored — never commit them
- `.linkedin_session/` browser data is gitignored — stays local
- MCP server only accepts localhost connections
- All actions are in DRY_RUN mode by default — set `DRY_RUN=false` only when ready
- Payments always require human approval regardless of amount
- Audit logs stored in `/Logs/YYYY-MM-DD.json` for 90 days

---

## Troubleshooting

**Gmail auth fails:**
```bash
# Delete token and re-auth
rm token.json
python watchers/gmail_watcher.py --auth
```

**LinkedIn session expired:**
```bash
rm -rf .linkedin_session
python watchers/linkedin_watcher.py --login
```

**MCP server can't connect:**
```bash
# Check if server is running
curl http://localhost:3000/health
# Restart it
cd mcp-email-server && node index.js
```

**Claude CLI not found:**
```bash
npm install -g @anthropic/claude-code
claude --version
```

**Stop hook not triggering:**
```bash
# Verify hook registration
cat .claude/settings.json
# Test manually
echo '{"transcript_path":"","session_id":"test"}' | python hooks/stop_hook.py
```
