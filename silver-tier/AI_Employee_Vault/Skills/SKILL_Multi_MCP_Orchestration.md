# SKILL: Multi-MCP Orchestration

## Description
Coordinates actions across all MCP servers in the Gold Tier system. Acts as the routing
layer — determines which MCP server to call, handles server health checks, routes
approval file executions to the correct server, and aggregates results.

## MCP Server Registry
| Server | Port | Protocol | Purpose |
|--------|------|----------|---------|
| email-mcp | 3000 | HTTP | Gmail send/draft (existing Silver) |
| facebook-mcp | 3001 | HTTP | Facebook post/reply automation |
| instagram-mcp | 3002 | HTTP | Instagram post/reply automation |
| twitter-mcp | 3003 | HTTP | Twitter/X post/reply automation |
| odoo-mcp | 3004 | HTTP | Odoo 19 accounting JSON-RPC bridge |

## Trigger
- Called internally by all other skills before making any MCP call
- Called by orchestrator.py when a file appears in /Approved/
- Manual: "Execute SKILL_Multi_MCP_Orchestration to route {action}"

## Step-by-Step Procedure

### Step 1 — Health Check All Servers
Before processing any /Approved/ file, check all servers:
```
For each server in registry:
  GET http://localhost:{port}/health
  If 200 → mark healthy
  If timeout/error → mark unhealthy, log to /Logs/
```

### Step 2 — Route Approved Action
When a file appears in /Approved/:
1. Read file front matter: `action`, `mcp_server`, `params`
2. Validate: is mcp_server in registry? Is server healthy?
3. Build HTTP request:
```
POST http://localhost:{server_port}/{action_endpoint}
Content-Type: application/json
Authorization: Bearer {MCP_SECRET from .env}
Body: {params as JSON}
```
4. Execute request (via bash or direct HTTP call)
5. Parse response
6. Log result via SKILL_Audit_Logging
7. Move /Approved/{file} → /Done/

### Step 3 — Handle Multi-Server Actions
For cross-platform posts (one approval, multiple servers):
```
If approval file has "platforms": ["facebook", "instagram", "twitter"]:
  Execute sequentially:
    1. POST to facebook-mcp
    2. POST to instagram-mcp
    3. POST to twitter-mcp
  If any fail: log error, continue with remaining platforms
  Summarize results in /Logs/
```

### Step 4 — Action Routing Table
```
action: send_email          → email-mcp      → POST /send
action: draft_email         → email-mcp      → POST /draft
action: post_to_facebook    → facebook-mcp   → POST /post
action: reply_on_facebook   → facebook-mcp   → POST /reply
action: post_to_instagram   → instagram-mcp  → POST /post
action: reply_on_instagram  → instagram-mcp  → POST /reply
action: create_tweet        → twitter-mcp    → POST /post
action: reply_on_twitter    → twitter-mcp    → POST /reply
action: odoo_create_invoice → odoo-mcp       → POST /invoice
action: odoo_register_payment → odoo-mcp     → POST /payment (ALWAYS HITL)
action: odoo_get_revenue    → odoo-mcp       → GET /revenue (no approval needed)
```

### Step 5 — Error Escalation Matrix
```
1st failure → Retry with exponential backoff (1s, 2s, 4s)
2nd failure → Log error, create FAILED_{ACTION}_{timestamp}.md in /Needs_Action/
3rd failure → Alert human via email draft, invoke SKILL_Error_Recovery_Graceful_Degradation
Permanent failure → Move to /Rejected/ with error details, keep audit log
```

## MCP Request Format
All MCP servers in this system use a unified HTTP JSON API:

### Request
```json
POST http://localhost:{port}/{endpoint}
{
  "action": "action_name",
  "params": { ... action-specific params ... },
  "metadata": {
    "approval_file": "path/to/approved/file.md",
    "session_id": "...",
    "dry_run": false
  }
}
```

### Response
```json
{
  "success": true,
  "result": { ... },
  "error": null,
  "timestamp": "ISO8601"
}
```

## Orchestrator Integration
The Python orchestrator.py calls this skill when it detects files in /Approved/:
```python
# orchestrator.py calls Claude with this prompt:
prompt = (
  f"Execute SKILL_Multi_MCP_Orchestration. "
  f"Route the action in file: {approved_file_path}. "
  f"Check server health first. Execute and log the result."
)
```

## Example Usage

**Scenario:** User moves `SOCIAL_FB_lead_reply_20260107.md` to /Approved/

Claude:
1. Reads file: `action: reply_on_facebook`, `comment_id: 123`, `reply_text: "Hi! ..."`
2. Checks facebook-mcp health → healthy
3. POSTs to `http://localhost:3001/reply`
4. Gets `{ "success": true, "reply_id": "456" }`
5. Logs action via SKILL_Audit_Logging
6. Moves file to /Done/
7. Updates Dashboard.md Recent Activity
8. Outputs `<promise>TASK_COMPLETE</promise>`

## Security Rules
- Never log credentials or tokens in audit files
- MCP_SECRET is read from environment variable only
- All MCP calls are localhost-only (no external network except via the MCP server itself)
- Approval files are never deleted — always moved to /Done/ or /Rejected/ for audit trail
