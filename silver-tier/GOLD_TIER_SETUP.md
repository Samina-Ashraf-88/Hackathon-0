# Gold Tier Setup Guide — Complete Step-by-Step

**Samina Ashraf's Personal AI Employee — Gold Tier**
**Project root:** `E:/hackathon-0/silver-tier/`

---

## Prerequisites Check

```bash
python --version      # Must be 3.13+
node --version        # Must be v24+
npm --version         # Comes with Node
docker --version      # Must have Docker Desktop running
claude --version      # Must have Claude Code installed
pm2 --version         # Install: npm install -g pm2
```

If pm2 missing: `npm install -g pm2`

---

## Step 1 — Configure Environment Variables

```bash
cd E:/hackathon-0/silver-tier

# Copy the template
copy .env.gold.example .env    # Windows
# cp .env.gold.example .env   # Mac/Linux

# Edit .env and fill in:
# - MCP_SECRET (generate: node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")
# - FACEBOOK_PASSWORD
# - INSTAGRAM_PASSWORD
# - TWITTER_PASSWORD
# - ODOO_PASSWORD (choose your own)
# - ODOO_ADMIN_PASSWORD (choose your own)
# - ODOO_DB_PASSWORD (choose your own)
# Leave DRY_RUN=true until everything is tested
```

---

## Step 2 — Install Python Dependencies

```bash
cd E:/hackathon-0/silver-tier
pip install -r requirements.txt
python -m playwright install chromium
```

---

## Step 3 — Install Node.js Dependencies (All MCP Servers)

```bash
cd E:/hackathon-0/silver-tier

# Install each MCP server
cd mcp-email-server && npm install && cd ..
cd mcp-facebook    && npm install && cd ..
cd mcp-instagram   && npm install && cd ..
cd mcp-twitter     && npm install && cd ..
cd mcp-odoo        && npm install && cd ..
```

---

## Step 4 — Start Odoo (Docker)

> **Odoo version:** `odoo:18` (Community, released Oct 2024). Upgrade to `odoo:19`
> when that Docker Hub image is published. Modules: `account`, `sale_management`,
> `purchase`, `analytic`, `contacts`, `currency_rate_live`.

```bash
cd E:/hackathon-0/silver-tier

# Create data directories
mkdir -p odoo-data/postgres odoo-data/odoo

# Start Odoo + PostgreSQL
docker compose -f docker-compose.odoo.yml up -d

# Wait ~60 seconds, then check
docker compose -f docker-compose.odoo.yml ps
# Both services should show "Up (healthy)"

# Odoo UI: http://localhost:8069
```

> **After first startup:** Edit `docker-compose.odoo.yml` and remove the `--init=...`
> line from the Odoo command to speed up subsequent restarts. The `--init` flag
> re-installs modules on every container start (slow but harmless if left in).
> Remove it once `python scripts/setup_odoo.py` has run successfully.

---

## Step 5 — Initialize Odoo Database & Sample Data

```bash
cd E:/hackathon-0/silver-tier

# Load .env first (Windows PowerShell):
# Get-Content .env | ForEach-Object { if ($_ -notmatch '^#' -and $_ -match '=') { $k,$v=$_.split('=',2); [System.Environment]::SetEnvironmentVariable($k,$v) } }

python scripts/setup_odoo.py
```

This creates:
- Database: `ai_employee_db`
- Company: Samina Ashraf AI Consulting
- 3 sample customers (Tech Solutions Ltd, DataDriven Co, StartupX)
- 3 sample invoices ($1,500 + $500 + $2,000)
- Verifies odoo-mcp connectivity

**Verify via browser:** http://localhost:8069 | Login: admin / [your ODOO_PASSWORD]

---

## Step 6 — Authenticate Gmail

```bash
cd E:/hackathon-0/silver-tier/watchers
python gmail_watcher.py --auth
# Opens browser → log in as apple379tree@gmail.com
# Token saved to ../token.json
```

---

## Step 7 — Authenticate Social Media Sessions (One-time)

Start the MCP servers temporarily for login:
```bash
# Terminal 1: Start facebook-mcp
cd E:/hackathon-0/silver-tier/mcp-facebook && node index.js

# Terminal 2: Login to Facebook
curl -X POST http://localhost:3001/login \
  -H "Authorization: Bearer YOUR_MCP_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"email":"apple379tree@gmail.com","password":"YOUR_FACEBOOK_PASSWORD"}'
# Should return: {"success":true,"message":"Session saved"}
```

```bash
# Terminal 1: Start instagram-mcp
cd E:/hackathon-0/silver-tier/mcp-instagram && node index.js

# Login to Instagram
curl -X POST http://localhost:3002/login \
  -H "Authorization: Bearer YOUR_MCP_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"username":"apple379tree","password":"YOUR_INSTAGRAM_PASSWORD"}'
```

```bash
# Terminal 1: Start twitter-mcp
cd E:/hackathon-0/silver-tier/mcp-twitter && node index.js

# Login to Twitter/X
curl -X POST http://localhost:3003/login \
  -H "Authorization: Bearer YOUR_MCP_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"username":"SaminaAshr24675","password":"YOUR_TWITTER_PASSWORD"}'
```

**Note:** If 2FA is required, you'll need to temporarily run the MCP servers in headless=false
mode and complete 2FA manually. Sessions are then saved.

---

## Step 8 — Authenticate LinkedIn (Playwright session)

```bash
cd E:/hackathon-0/silver-tier/watchers
python linkedin_watcher.py --login
# Follow the browser prompts
```

---

## Step 9 — Start All Processes with PM2

```bash
cd E:/hackathon-0/silver-tier

# Start all 11 processes (5 MCP servers + 5 watchers + 1 watchdog)
pm2 start ecosystem.gold.config.js

# Check status
pm2 status

# View logs (all processes)
pm2 logs

# View specific process logs
pm2 logs facebook-mcp
pm2 logs gmail-watcher
pm2 logs watchdog

# Save process list (survives reboot)
pm2 save

# Register PM2 as Windows startup service
pm2 startup
# Follow the printed command
```

---

## Step 10 — Set Up Weekly CEO Briefing (Task Scheduler)

**Windows Task Scheduler:**
```bash
schtasks /create /tn "AI_Employee_Weekly_CEO_Briefing" ^
  /tr "python E:\hackathon-0\silver-tier\scripts\weekly_audit.py" ^
  /sc weekly /d SUN /st 22:00 /f /rl HIGHEST
```

**Or run it now to test:**
```bash
python scripts/weekly_audit.py --dry-run
# Check: AI_Employee_Vault/Needs_Action/WEEKLY_BRIEFING_*.md created
```

---

## Step 11 — Health Check All Systems

```bash
cd E:/hackathon-0/silver-tier

# Check all MCP servers
python -c "
import requests
servers = {
  'email-mcp':     'http://localhost:3000/health',
  'facebook-mcp':  'http://localhost:3001/health',
  'instagram-mcp': 'http://localhost:3002/health',
  'twitter-mcp':   'http://localhost:3003/health',
  'odoo-mcp':      'http://localhost:3004/health',
}
for name, url in servers.items():
    try:
        r = requests.get(url, timeout=3)
        status = '✅ OK' if r.status_code == 200 else f'⚠️ {r.status_code}'
    except Exception as e:
        status = f'❌ {e}'
    print(f'{name:20} {status}')
"

# Check Odoo
python scripts/setup_odoo.py --verify-only

# Check PM2
pm2 status
```

---

## Step 12 — Test the Full Workflow (DRY_RUN=true)

```bash
# 1. Create a test task manually
echo "---
type: facebook_message
platform: facebook
from: \"Test User\"
classification: lead
status: pending
---

## Test Facebook DM

Price inquiry from test user.
" > "AI_Employee_Vault/Needs_Action/FACEBOOK_MESSAGE_test_20260301.md"

# 2. Trigger Claude manually
claude --print \
  "Execute SKILL_Ralph_Wiggum_Autonomous_Loop. Vault: E:/hackathon-0/silver-tier/AI_Employee_Vault. Process all items in /Needs_Action/." \
  --cwd "E:/hackathon-0/silver-tier/AI_Employee_Vault"

# 3. Check results
ls AI_Employee_Vault/Pending_Approval/
ls AI_Employee_Vault/Done/
cat AI_Employee_Vault/Logs/$(date +%Y-%m-%d).json
```

---

## Step 13 — Test Weekly CEO Briefing

```bash
# Run briefing trigger (DRY_RUN=true mode)
python scripts/weekly_audit.py

# This creates /Needs_Action/WEEKLY_BRIEFING_*.md
# Then Claude processes it → creates /Briefings/YYYYMMDD_Monday_CEO_Briefing.md

# Check the briefing
ls AI_Employee_Vault/Briefings/
cat "AI_Employee_Vault/Briefings/$(ls AI_Employee_Vault/Briefings/ | tail -1)"
```

---

## Step 14 — Go Live (DRY_RUN=false)

When you're satisfied everything works:
```bash
# Edit .env
# Change: DRY_RUN=true → DRY_RUN=false

# Restart all PM2 processes to pick up new env
pm2 restart ecosystem.gold.config.js

# Monitor for first few hours
pm2 logs

# Check Dashboard.md in Obsidian
# Approve your first real action by moving a file from /Pending_Approval/ to /Approved/
```

---

## Troubleshooting

### MCP Server won't connect
```bash
# Check it's running
pm2 status
# Restart a specific server
pm2 restart facebook-mcp
# Check logs
pm2 logs facebook-mcp --lines 50
```

### Social media session expired
```bash
# 1. Stop the MCP server
pm2 stop facebook-mcp
# 2. Start temporarily with headless=false (edit index.js: headless: false)
cd mcp-facebook && node index.js
# 3. POST /login to re-authenticate
curl -X POST http://localhost:3001/login -H "Authorization: Bearer YOUR_SECRET" \
  -H "Content-Type: application/json" -d '{"email":"...","password":"..."}'
# 4. Restart via PM2
cd .. && pm2 start ecosystem.gold.config.js --only facebook-mcp
```

### Odoo not connecting
```bash
docker compose -f docker-compose.odoo.yml ps
docker compose -f docker-compose.odoo.yml logs odoo --tail 50
# If stuck: docker compose -f docker-compose.odoo.yml restart odoo
```

### Claude not finding Claude CLI
```bash
# Verify installation
claude --version
# If not found:
npm install -g @anthropic/claude-code
```

### Ralph Wiggum loop not stopping
```bash
# Check iteration counter
cat .ralph_iterations.json
# Reset if stuck
rm .ralph_iterations.json
# Or increase max iterations in .env:
RALPH_MAX_ITERATIONS=15
```

---

## Running the Ralph Wiggum Loop Manually

```bash
cd E:/hackathon-0/silver-tier

claude --print \
  "Execute SKILL_Ralph_Wiggum_Autonomous_Loop as defined in AI_Employee_Vault/Skills/SKILL_Ralph_Wiggum_Autonomous_Loop.md. Process all items in AI_Employee_Vault/Needs_Action/. Vault path: E:/hackathon-0/silver-tier/AI_Employee_Vault. Output <promise>TASK_COMPLETE</promise> when complete." \
  --cwd "E:/hackathon-0/silver-tier/AI_Employee_Vault"
```

---

## File Structure Summary

```
E:/hackathon-0/silver-tier/
├── .env                              ← Your secrets (never commit)
├── .env.gold.example                 ← Template
├── .claude/settings.json             ← Stop hook registration
├── .pids/                            ← Process PID files
├── .sessions/                        ← Browser session storage
│   ├── facebook/
│   ├── instagram/
│   ├── twitter/
│   └── linkedin/
├── AI_Employee_Vault/                ← Obsidian vault (the brain)
│   ├── CLAUDE.md                     ← AI rules
│   ├── Dashboard.md                  ← Live status
│   ├── Business_Goals.md             ← KPIs
│   ├── ARCHITECTURE.md               ← System docs
│   ├── LESSONS.md                    ← Lessons learned
│   ├── Skills/                       ← 14 SKILL_*.md files
│   ├── Needs_Action/                 ← Watcher input queue
│   ├── Pending_Approval/             ← Awaiting human review
│   ├── Approved/                     ← Human approved → Claude executes
│   ├── Rejected/                     ← Human rejected
│   ├── Done/                         ← Completed tasks
│   ├── Plans/                        ← Claude plan files
│   ├── Briefings/                    ← Weekly CEO briefings
│   ├── Accounting/                   ← Odoo data snapshots
│   └── Logs/                         ← JSON audit logs
├── watchers/                         ← Python watcher scripts
│   ├── base_watcher.py
│   ├── gmail_watcher.py              ← Silver (reused)
│   ├── linkedin_watcher.py           ← Silver (reused)
│   ├── facebook_watcher.py           ← Gold NEW
│   ├── instagram_watcher.py          ← Gold NEW
│   ├── twitter_watcher.py            ← Gold NEW
│   ├── orchestrator.py               ← Silver (reused)
│   ├── retry_handler.py              ← Gold EXPANDED
│   ├── watchdog.py                   ← Gold NEW
│   └── audit_logger.py               ← Gold NEW
├── mcp-email-server/                 ← Silver MCP (reused)
├── mcp-facebook/                     ← Gold NEW
├── mcp-instagram/                    ← Gold NEW
├── mcp-twitter/                      ← Gold NEW
├── mcp-odoo/                         ← Gold NEW
├── hooks/stop_hook.py                ← Ralph Wiggum (Silver, reused)
├── scripts/
│   ├── setup_odoo.py                 ← Gold NEW
│   ├── setup_gold.bat                ← Gold NEW (Windows setup)
│   └── weekly_audit.py               ← Gold NEW
├── docker-compose.odoo.yml           ← Gold NEW
├── odoo-config/odoo.conf             ← Gold NEW
├── ecosystem.gold.config.js          ← Gold NEW (PM2 config)
├── requirements.txt                  ← Updated for Gold
└── GOLD_TIER_SETUP.md                ← This file
```

---

*Setup guide — AI Employee Gold Tier | Samina Ashraf AI Consulting | March 2026*
