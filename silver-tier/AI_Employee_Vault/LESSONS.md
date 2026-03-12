# AI Employee Gold Tier — Lessons Learned

**Author:** Samina Ashraf (with AI Employee assistance)
**Period:** January–March 2026
**Tier:** Gold

---

## L1 — The "Lazy Agent" Problem is Real

**What We Learned:**
Claude Code, like all LLMs, will stop when it thinks it's done — even when there are
still items in /Needs_Action/. Without the Ralph Wiggum Stop hook, the AI processes
one or two items and calls it done.

**Solution:**
The Stop hook pattern (hooks/stop_hook.py) intercepts every exit attempt and checks:
1. Did Claude output `<promise>TASK_COMPLETE</promise>`?
2. Is /Needs_Action/ actually empty?

If either check fails, the hook blocks exit and re-injects the task prompt with context
about remaining work. This turns a one-shot model into a true autonomous agent.

**Key insight:** Max 10 iterations is a safety valve. Most tasks complete in 1-3 iterations.
Hitting 10 usually means Claude is stuck — which itself is an alert signal.

---

## L2 — File-Based Communication is Surprisingly Robust

**What We Learned:**
Using the filesystem (Obsidian vault) as the message bus between all components
(watchers, Claude, orchestrator, MCP servers, human) is not a compromise — it's a
superpower:
- Every action is auditable (the file IS the log)
- Human review is natural (just open Obsidian)
- No message queue infrastructure needed
- Survives crashes: files persist
- Git-compatible: can version control the vault state

**What to watch out for:**
- File naming collisions (use timestamps: YYYYMMDD_HHMMSS)
- Race conditions if multiple watchers create files simultaneously (use atomic writes)
- Stale files: implement cleanup routines for /Plans/ > 7 days old

**Solution:**
- All file names include high-resolution timestamps
- BaseWatcher uses atomic `write_text()` which is safe for single-writer scenarios
- Weekly cleanup in CEO Briefing script

---

## L3 — Playwright Sessions Need Care

**What We Learned:**
Browser automation for Facebook, Instagram, and Twitter/X is fragile:
- Sessions expire (typically 2-4 weeks)
- 2FA breaks headless login automation
- Platform UI changes break selectors overnight
- Headless detection is increasingly aggressive

**Solutions:**
- Persistent browser context (launchPersistentContext) preserves cookies across restarts
- Sessions stored in `.sessions/` directory (committed to .gitignore)
- Login is a one-time manual step via POST /login endpoint
- Health check every 60s detects session expiry early
- When session expires: create AUTH_REQUIRED_*.md → alert human → re-login

**Future improvement:**
Use official APIs where available (e.g., Twitter API v2, Facebook Graph API)
instead of Playwright. Playwright is the fallback when APIs are too restrictive.

---

## L4 — Human-in-the-Loop Must Be Frictionless

**What We Learned:**
If approving an AI action requires opening a terminal or running a command, humans
don't do it. The approval mechanism must be dead simple.

**Our solution: file-move approval**
- AI creates a file in /Pending_Approval/ with full context
- Human opens Obsidian, reads the file, drags it to /Approved/ or /Rejected/
- Orchestrator detects the move and executes

This works because:
- Obsidian shows the approval request beautifully formatted
- Drag-and-drop in the Obsidian file explorer = approval
- No code, no commands, no friction
- The vault IS the dashboard

**Key rule:** Every approval file must include:
- What action will be taken (exact message/amount/content)
- Why it was triggered (what inbound message caused it)
- What happens if approved / rejected
- Expiry time (default 24 hours)

---

## L5 — DRY_RUN=true is Not Optional in Development

**What We Learned:**
During testing, the system WILL try to post embarrassing test content if DRY_RUN
is not set. Trust me.

**Implementation:**
Every script and MCP server reads `DRY_RUN` from environment:
```python
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
```

DRY_RUN=true means:
- Log EVERYTHING as normal
- Skip ALL external API calls
- Return mock success responses
- Still write files to vault (testing the file system logic)

**Lesson:** The logs should be identical in DRY_RUN and live mode — the only difference
is whether HTTP requests are made. This makes DRY_RUN genuinely useful for testing.

---

## L6 — Odoo's JSON-RPC API is Powerful but Quirky

**What We Learned:**
Odoo's external API (`/web/dataset/call_kw`) works well but has some quirks:
- Authentication gives you a UID that must be included in every call
- Model names follow Odoo's dot notation (e.g., `account.move`, not `invoice`)
- Domain filters use Polish notation lists (Odoo domain syntax)
- `create()` always returns a draft record — you must explicitly call `action_post()` to confirm
- Payment wizard API changed between versions

**Key insight:**
Keep ALL Odoo write operations as DRAFT until explicit human approval.
The odoo-mcp server creates draft invoices — posting them requires a second approval.
This prevents accidental financial records.

---

## L7 — Audit Logs Are Your Most Valuable Asset

**What We Learned:**
When something goes wrong (and it will), the audit logs in `/Logs/YYYY-MM-DD.json`
are the only way to debug what happened. Design your logs first, then build features.

**What to always log:**
- Every file created in /Needs_Action/ (by watchers)
- Every SKILL invoked (by Claude)
- Every MCP call made (by orchestrator)
- Every approval granted/rejected (by human file-move detection)
- Every error, with full stack trace (capped at 500 chars)
- Every system restart (by watchdog)

**What NOT to log:**
- Passwords, tokens, API keys, session cookies
- Full email bodies (log subject and sender only)
- Full message content (log first 100 chars only)

---

## L8 — Process Management Changes Everything

**What We Learned:**
Python watchers started from a terminal die when you close the terminal.
PM2 solves this with three killer features:
1. Auto-restart on crash (with configurable backoff)
2. `pm2 startup` → processes survive reboot
3. `pm2 logs` → centralized log viewing

**Without PM2:** Your AI Employee dies when you sleep.
**With PM2:** Your AI Employee works while you sleep.

**One gotcha:** PM2 doesn't auto-load `.env` files. You must pass environment
variables explicitly in the PM2 ecosystem config (see ecosystem.gold.config.js).

---

## L9 — The Weekly CEO Briefing is the Killer Feature

**What We Learned:**
The Monday Morning CEO Briefing is what transforms this from a "cool technical demo"
into a genuine business tool. Before the briefing, you had to check 5 platforms manually.
After: one Obsidian file tells you everything that happened last week.

**Most valuable sections:**
1. Revenue vs. target (instant business health check)
2. Leads identified (pipeline visibility)
3. Proactive suggestions (the AI noticing what you miss)
4. Upcoming deadlines (never miss a client delivery)

**What surprised us:**
The subscription audit feature (flagging unused SaaS tools) consistently surfaces
$50-200/month in savings that you forgot about.

---

## L10 — Cross-Domain Integration Compounds Value

**What We Learned:**
Silver Tier (email + LinkedIn alone) was useful. Gold Tier added Facebook, Instagram,
Twitter, and Odoo. The value didn't increase linearly — it compounded.

Example: A lead appears as a Twitter mention → Claude identifies them → checks if
they're already an Odoo customer → drafts a personalized reply that references their
history → creates a follow-up task. This cross-domain intelligence is impossible
without integration at the AI reasoning layer.

**Architecture implication:** Don't silo the AI. Give Claude access to all context
(vault, all logs, Odoo data) when reasoning about any single task. Context = quality.

---

## What We'd Do Differently

1. **Start with official APIs** — Use Twitter API v2 and Facebook Graph API before
   resorting to Playwright. Automation bans are costly.

2. **Build the CEO Briefing first** — It's the feature that validates all other features.
   Start there to maintain motivation.

3. **Use structured IDs everywhere** — Every action in the vault needs a unique ID
   from day one, to enable cross-referencing between log files, vault files, and Odoo records.

4. **Rate limit aggressively** — Social platforms ban accounts that post too frequently.
   Build in rate limits (max X posts per hour) from day one.

5. **Test DRY_RUN=false on a throwaway account first** — Never test live posting on
   your real business account. Use a test account first.

---

## Known Limitations

1. **Playwright automation is fragile** — Platform UI changes break selectors.
   Plan for monthly maintenance.

2. **Instagram API restrictions** — Instagram heavily restricts automation.
   The Playwright approach may break with platform updates.

3. **Odoo version** — The docker-compose uses Odoo 17 (latest stable).
   Odoo 19 is referenced in the hackathon doc but may not be publicly available yet.
   The JSON-RPC API is backward compatible.

4. **Windows Task Scheduler** — The weekly audit scheduler requires manual setup
   or the `setup_gold.bat` script. PM2 cron tab is an alternative.

5. **No real-time push** — All watchers are polling-based (not webhooks).
   True real-time requires official API webhooks where available.

---

*Document maintained by AI Employee. Last update: auto-appended by SKILL_Weekly_CEO_Briefing*
