# SKILL: Cross-Domain Lead to Invoice (LinkedIn/Email → Odoo)

## Description
Full cross-domain integration workflow: a personal-domain event (LinkedIn lead or email
inquiry) triggers a chain of business-domain actions (Odoo customer creation, sales order,
draft invoice). This is the flagship Gold Tier cross-domain integration feature.

## Trigger
- File in `/Needs_Action/` where `classification: lead` AND `cross_domain: true`
- Prefix: `LINKEDIN_LEAD_*.md`, `EMAIL_LEAD_*.md`, `FACEBOOK_LEAD_*.md`
- Called from SKILL_Process_LinkedIn or SKILL_Process_Gmail when a lead is detected

---

## Step-by-Step Procedure

### Step 1 — Extract Lead Details
From the trigger file, extract:
```
lead_name        = from: field (contact name)
lead_company     = from_title: field (company name, if present)
lead_email       = (if present in message body or metadata)
lead_platform    = linkedin | email | facebook
lead_message     = the original message text
lead_interest    = what they asked about (service type, pricing, etc.)
```

### Step 2 — Check if Customer Exists in Odoo
```
GET http://localhost:3004/customers?search={lead_company or lead_name}&limit=5
```
- If customer found → use existing `customer_id`
- If not found → proceed to Step 3 to create

### Step 3 — Create Customer in Odoo (requires approval)
Create approval file `/Pending_Approval/ODOO_NEW_CUSTOMER_{name}_{date}.md`:
```markdown
---
type: approval_request
action: odoo_create_customer
mcp_endpoint: POST http://localhost:3004/customer
params:
  name: "{lead_company or lead_name}"
  email: "{lead_email}"
  phone: "{lead_phone if available}"
  city: "{lead_city if available}"
created: "{ISO_TIMESTAMP}"
status: pending
---

## New Customer: {name}
Source: {platform} lead from {lead_name}

## To Approve — move to /Approved/
## To Reject — move to /Rejected/
```

### Step 4 — Create Draft Sales Order / Quotation (requires approval)
Based on `lead_interest`, select the most relevant service(s) from Odoo products:
```
GET http://localhost:3004/products?type=service
```
Map lead interest keywords to products:
- "retainer" / "monthly" → Monthly AI Retainer ($500/month)
- "setup" / "automation" → AI Automation Setup ($1,500)
- "agent" / "claude" → Claude Agent Development ($2,000)
- "consulting" / "advice" → AI Consulting Hourly ($150/hr)
- "social media" → Social Media Management ($300/month)
- "strategy" / "linkedin" → LinkedIn Strategy Session ($200)

Create approval file `/Pending_Approval/ODOO_SALES_ORDER_{company}_{date}.md`:
```markdown
---
type: approval_request
action: odoo_create_sales_order
mcp_endpoint: POST http://localhost:3004/sales-order
params:
  customer_name: "{company}"
  lines:
    - name: "{selected_service}"
      quantity: {qty}
      price_unit: {price}
  validity_date: "{today + 30 days}"
  note: "Proposal for {company} — via {platform} lead from {lead_name}"
created: "{ISO_TIMESTAMP}"
status: pending
---

## Quotation for {company}
Total: ${amount}

Approve to create in Odoo. Email will follow with proposal link.
## To Approve — move to /Approved/
## To Reject — move to /Rejected/
```

### Step 5 — Draft Platform Reply (Personal Domain)
Create a warm, personalized reply to the lead:

**For LinkedIn leads** → `/Pending_Approval/LINKEDIN_REPLY_{name}_{date}.md`:
```
Subject: Re: {original_subject or "AI Automation Services"}

Hi {first_name},

Thank you for reaching out! I'd love to help {company} streamline your operations
with AI automation.

Based on what you described, I'd recommend our [selected package] — [brief description].

I've put together a quick proposal. Would you have 20 minutes this week for a call
to walk through the details?

Looking forward to connecting!
— Samina
```

**For email leads** → `/Pending_Approval/EMAIL_REPLY_{name}_{date}.md`

### Step 6 — Log the Cross-Domain Action
Write to `/Logs/{date}.json`:
```json
{
  "timestamp": "{ISO}",
  "action_type": "cross_domain_lead_capture",
  "actor": "claude_code",
  "component": "cross_domain_integration",
  "skill_invoked": "SKILL_Cross_Domain_Lead_To_Invoice",
  "target": "{lead_company}",
  "parameters": {
    "source_platform": "{platform}",
    "lead_name": "{name}",
    "services_proposed": ["{service1}"],
    "proposal_amount": {amount}
  },
  "approval_status": "pending",
  "result": "approval_files_created"
}
```

### Step 7 — Update Dashboard
Add to Dashboard.md Recent Activity:
```
- [{timestamp}] New lead captured: {name} from {company} ({platform}) — Proposal: ${amount}
```

### Step 8 — Complete
- Move trigger file from `/Needs_Action/` → `/Done/`
- Output: `<promise>TASK_COMPLETE</promise>` if no other items remain

---

## Cross-Domain Data Flow Diagram

```
PERSONAL DOMAIN                          BUSINESS DOMAIN
─────────────────                        ───────────────────────────
LinkedIn / Email                         Odoo Community (localhost:8069)
     │                                           │
     ▼                                           ▼
Watcher detects                         Customer record created
lead message                            (via POST /customer)
     │                                           │
     ▼                                           ▼
/Needs_Action/                          Sales Order / Quotation
LINKEDIN_LEAD_*.md                      (via POST /sales-order)
     │                                           │
     ▼                                           ▼
Claude reads file              ┌────────▶ /Pending_Approval/
(SKILL_Cross_Domain)           │         ODOO_SALES_ORDER_*.md
     │                         │                 │
     ▼                         │                 ▼
Draft platform reply           │         Human approves
(SKILL_Process_LinkedIn)       │                 │
     │                         │                 ▼
     ▼                         │         Orchestrator dispatches
/Pending_Approval/             │         → SKILL_Odoo_Accounting_Actions
LINKEDIN_REPLY_*.md            │         → MCP call executes
     │                         │                 │
     ▼                         │                 ▼
Human approves ────────────────┘         Invoice created in Odoo
     │                                           │
     ▼                                           ▼
Reply sent via                          Email follow-up with
LinkedIn MCP                            proposal link (email-mcp)
```

---

## MCP Calls Summary

| Call | Endpoint | Auth Required |
|------|----------|--------------|
| Check existing customer | GET /customers?search=... | Bearer token |
| Create customer | POST /customer | Bearer token + Approval file |
| Get products | GET /products?type=service | Bearer token |
| Create sales order | POST /sales-order | Bearer token + Approval file |
| Send reply email | POST http://localhost:3000/send-email | Bearer token + Approval file |

---

## Error Handling
- Odoo unavailable: Create customer/order files locally, retry when Odoo back online
- Lead already a customer: Skip Step 3, go directly to Step 4
- No matching product: Default to "AI Consulting (Hourly)" as catch-all
- Lead email missing: Skip email follow-up, note in approval file
