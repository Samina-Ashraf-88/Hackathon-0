# AI Employee Gold Tier — System Architecture

**Owner:** Samina Ashraf | apple379tree@gmail.com
**Version:** 2.0 (Gold Tier)
**Built:** 2026-03-01

---

## System Overview

The AI Employee Gold Tier is a fully autonomous, local-first AI agent system that manages
Samina Ashraf's personal and business affairs across email, LinkedIn, Facebook, Instagram,
Twitter/X, and Odoo accounting — with human-in-the-loop approval for all sensitive actions.

**Core Philosophy:**
- Local-first: all data stays on your machine
- Human-in-the-loop: AI proposes, human approves, AI executes
- Privacy-first: no credentials leave the local environment
- Graceful degradation: failures don't cascade into total system failure

---

## Full System Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════╗
║                    PERSONAL AI EMPLOYEE — GOLD TIER                      ║
║                  Local-First | Agent-Driven | Human-in-the-Loop          ║
╚══════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SOURCES                                 │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────────┤
│  Gmail   │LinkedIn  │Facebook  │Instagram │Twitter/X │  Odoo 19 (local) │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴────────┬─────────┘
     │          │          │          │          │               │
     ▼          ▼          ▼          ▼          ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      PERCEPTION LAYER (Watchers)                         │
│  ┌──────────┐ ┌────────────┐ ┌────────────┐ ┌─────────────┐ ┌────────┐ │
│  │  Gmail   │ │  LinkedIn  │ │  Facebook  │ │  Instagram  │ │Twitter │ │
│  │ Watcher  │ │  Watcher   │ │  Watcher   │ │  Watcher    │ │Watcher │ │
│  │(Python)  │ │(Playwright)│ │ (→MCP poll)│ │ (→MCP poll) │ │(→MCP)  │ │
│  │ 120s     │ │  300s      │ │   300s     │ │   300s      │ │  300s  │ │
│  └────┬─────┘ └─────┬──────┘ └─────┬──────┘ └──────┬──────┘ └───┬────┘ │
└───────┼─────────────┼──────────────┼────────────────┼────────────┼──────┘
        │             │              │                │            │
        └─────────────┴──────────────┴────────────────┴────────────┘
                                     │
                                     ▼ (creates .md files)
┌─────────────────────────────────────────────────────────────────────────┐
│                    OBSIDIAN VAULT (Local Markdown)                       │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  /Needs_Action/  │  /Plans/  │  /Pending_Approval/  │  /Approved/  ││
│  ├─────────────────────────────────────────────────────────────────────┤│
│  │  /Done/  │  /Rejected/  │  /Briefings/  │  /Accounting/  │  /Logs/ ││
│  ├─────────────────────────────────────────────────────────────────────┤│
│  │  Dashboard.md  │  Company_Handbook.md  │  Business_Goals.md        ││
│  ├─────────────────────────────────────────────────────────────────────┤│
│  │  CLAUDE.md  │  ARCHITECTURE.md  │  LESSONS.md                       ││
│  ├─────────────────────────────────────────────────────────────────────┤│
│  │  Skills/  →  14 SKILL_*.md files defining all AI behaviors          ││
│  └─────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼ (orchestrator triggers Claude)
┌─────────────────────────────────────────────────────────────────────────┐
│                    REASONING LAYER (Claude Code)                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  SKILL_Ralph_Wiggum_Autonomous_Loop (entry point)                │  │
│  │  ┌─────────────────────────────────────────────────────────────┐ │  │
│  │  │  Read → Classify → Load SKILL → Execute → Log → Move /Done/ │ │  │
│  │  └─────────────────────────────────────────────────────────────┘ │  │
│  │                                                                   │  │
│  │  Skills invoked:                                                  │  │
│  │  • SKILL_Process_Gmail          • SKILL_Process_Social_Post       │  │
│  │  • SKILL_Process_LinkedIn       • SKILL_Odoo_Accounting_Actions   │  │
│  │  • SKILL_Facebook_Instagram_    • SKILL_Weekly_CEO_Briefing        │  │
│  │    Twitter_Integration          • SKILL_Multi_MCP_Orchestration    │  │
│  │  • SKILL_Audit_Logging          • SKILL_Error_Recovery             │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────┬───────────────────────────────────┬──────────────────────────┘
           │                                   │
           ▼ (creates approval files)          ▼ (reads approved files)
┌──────────────────────────┐    ┌──────────────────────────────────────────┐
│   HUMAN-IN-THE-LOOP      │    │       ACTION LAYER (MCP Servers)         │
│  ┌────────────────────┐  │    │  ┌──────────┐  ┌───────────────────────┐ │
│  │ /Pending_Approval/ │  │    │  │email-mcp │  │   facebook-mcp        │ │
│  │                    │  │    │  │ :3000    │  │   :3001 (Playwright)  │ │
│  │ Review → Approve   │──┼───▶│  ├──────────┤  ├───────────────────────┤ │
│  │         Reject     │  │    │  │odoo-mcp  │  │   instagram-mcp       │ │
│  └────────────────────┘  │    │  │ :3004    │  │   :3002 (Playwright)  │ │
└──────────────────────────┘    │  │(JSON-RPC)│  ├───────────────────────┤ │
                                │  └──────────┘  │   twitter-mcp         │ │
                                │                │   :3003 (Playwright)  │ │
                                │                └───────────────────────┘ │
                                └────────────────────────┬─────────────────┘
                                                         │
                                                         ▼
                                             ┌───────────────────────┐
                                             │    EXTERNAL ACTIONS   │
                                             │  • Send Email         │
                                             │  • Post to Facebook   │
                                             │  • Post to Instagram  │
                                             │  • Tweet on Twitter   │
                                             │  • Create Odoo Invoice│
                                             │  • Register Payment   │
                                             └───────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                                   │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  orchestrator.py — watches /Needs_Action/ and /Approved/           │ │
│  │  Triggers Claude CLI with appropriate skills                        │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  watchdog.py — monitors all processes, auto-restarts on failure    │ │
│  │  Creates SYSTEM_ERROR_*.md alerts in /Needs_Action/                │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  PM2 ecosystem.gold.config.js — manages all 11 processes           │ │
│  │  Auto-restart, log rotation, startup persistence                   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    SCHEDULING LAYER                                      │
│  weekly_audit.py → every Sunday 22:00 via Task Scheduler                │
│    Creates WEEKLY_BRIEFING_*.md → triggers SKILL_Weekly_CEO_Briefing    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    PERSISTENCE (Ralph Wiggum Loop)                       │
│  Stop hook: hooks/stop_hook.py                                           │
│  Triggers on every Claude exit attempt:                                  │
│    1. Check for <promise>TASK_COMPLETE</promise> in transcript           │
│    2. Check if /Needs_Action/ is empty                                   │
│    3. If not done → re-inject prompt (max 10 iterations)                │
│    4. If done → allow exit                                               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### Watchers (Perception Layer)
| Watcher | File | Interval | Triggers |
|---------|------|----------|---------|
| Gmail | `gmail_watcher.py` | 120s | Google API unread+important |
| LinkedIn | `linkedin_watcher.py` | 300s | Playwright scraper |
| Facebook | `facebook_watcher.py` | 300s | facebook-mcp poll |
| Instagram | `instagram_watcher.py` | 300s | instagram-mcp poll |
| Twitter | `twitter_watcher.py` | 300s | twitter-mcp poll |

### MCP Servers (Action Layer)
| Server | Port | Technology | Endpoints |
|--------|------|-----------|-----------|
| email-mcp | 3000 | Node.js + Gmail API | /send, /draft, /health |
| facebook-mcp | 3001 | Node.js + Playwright | /post, /reply, /messages, /login |
| instagram-mcp | 3002 | Node.js + Playwright | /post, /reply, /messages, /login |
| twitter-mcp | 3003 | Node.js + Playwright | /post, /reply, /retweet, /login |
| odoo-mcp | 3004 | Node.js + JSON-RPC | /revenue, /invoices, /invoice, /payment |

### Agent Skills (14 total)
| Skill | Tier | Purpose |
|-------|------|---------|
| SKILL_Reasoning_Loop | Silver | Default task processing |
| SKILL_Process_Gmail | Silver | Email handling |
| SKILL_Process_LinkedIn | Silver | LinkedIn handling |
| SKILL_Generate_Sales_Post | Silver | LinkedIn content |
| SKILL_Send_Email_via_MCP | Silver | Email sending |
| SKILL_Approval_Workflow | Silver | HITL workflow |
| SKILL_Ralph_Wiggum_Autonomous_Loop | Gold | Main loop entry point |
| SKILL_Process_Social_Post | Gold | Unified social media |
| SKILL_Facebook_Instagram_Twitter_Integration | Gold | Social media integration |
| SKILL_Odoo_Accounting_Actions | Gold | Accounting operations |
| SKILL_Weekly_CEO_Briefing | Gold | Monday briefing |
| SKILL_Multi_MCP_Orchestration | Gold | MCP routing |
| SKILL_Error_Recovery_Graceful_Degradation | Gold | Error handling |
| SKILL_Audit_Logging | Gold | Structured logging |

---

## Data Flow: Inbound Message → Response

```
1. Watcher detects new message (e.g., Instagram DM)
2. Watcher creates INSTAGRAM_DM_sender_timestamp.md in /Needs_Action/
3. Watcher calls trigger_claude() via base_watcher.py
4. Orchestrator detects file change, triggers Claude CLI
5. Claude reads CLAUDE.md → loads SKILL_Ralph_Wiggum_Autonomous_Loop
6. Ralph loop reads /Needs_Action/, routes to SKILL_Facebook_Instagram_Twitter_Integration
7. Skill reads the DM, classifies (lead/support/spam)
8. If lead: Claude drafts reply, creates SOCIAL_INSTAGRAM_sender.md in /Pending_Approval/
9. Claude logs via SKILL_Audit_Logging
10. Claude moves original file to /Done/
11. Claude outputs <promise>TASK_COMPLETE</promise>
12. Stop hook detects promise → allows exit

[Human: sees /Pending_Approval/ in Dashboard.md]
13. Samina reviews the draft reply in Obsidian
14. Moves file from /Pending_Approval/ → /Approved/
15. Orchestrator detects /Approved/ file change
16. Triggers Claude with SKILL_Multi_MCP_Orchestration
17. Claude calls instagram-mcp POST /reply
18. Reply sent on Instagram
19. Claude logs the send, moves file to /Done/
20. Dashboard.md updated
```

---

## Security Architecture

### Credential Storage
- All credentials in `.env` (not committed to git)
- Browser sessions in `.sessions/` (not committed to git)
- Odoo credentials in `.env` only
- MCP_SECRET as Bearer token for all inter-service auth

### Permission Boundaries
| Action | Auto-Approve | Requires HITL |
|--------|-------------|----------------|
| Email draft | ✅ | — |
| Email send | — | ✅ Always |
| Social media post | — | ✅ Always |
| Social media reply | — | ✅ Always |
| Odoo read | ✅ | — |
| Odoo invoice (draft) | — | ✅ Always |
| Odoo payment | — | ✅ Always |
| System alert email | ✅ (auto_approve flag) | — |
| File operations (vault) | ✅ | — |

---

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| AI Brain | Claude Code (Sonnet 4.6) | Latest |
| Knowledge Base | Obsidian | v1.10.6+ |
| Watcher Scripts | Python | 3.13+ |
| MCP Servers | Node.js | v24+ LTS |
| Social Automation | Playwright | v1.40+ |
| Accounting | Odoo Community | 17/19 |
| Database | PostgreSQL | 16 |
| Containerization | Docker + Docker Compose | Latest |
| Process Management | PM2 | Latest |
| Version Control | Git | Latest |

---

*Architecture documented as part of AI Employee Gold Tier build — March 2026*
