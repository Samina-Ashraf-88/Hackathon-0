---
type: linkedin_message
action: cross_domain_lead_to_invoice
platform: linkedin
from: "Ahmed Khalid"
from_title: "CEO, NexGen Ventures"
from_profile: "https://www.linkedin.com/in/ahmedkhalid-nexgen"
subject: "AI Automation Inquiry"
received: "2026-03-11T09:15:00"
priority: high
status: pending
classification: lead
cross_domain: true
skill: SKILL_Process_LinkedIn
---

# LinkedIn Lead — Cross-Domain Integration Demo

**From:** Ahmed Khalid — CEO, NexGen Ventures
**Message received:** March 11, 2026 at 9:15 AM

---

## Message

> Hi Samina,
>
> I came across your profile and I'm very interested in your AI automation services.
> We're a 25-person tech startup and we're spending way too much time on repetitive
> tasks — email triage, social media, invoicing. I'd love to understand what a
> Monthly AI Retainer would cost and what it includes. Can you send me a proposal?
>
> Best,
> Ahmed

---

## Cross-Domain Actions Required

This lead triggers a **full cross-domain workflow** (Personal ↔ Business):

### Step 1 — LinkedIn Response (Personal Domain)
Draft and queue a personalized LinkedIn reply via SKILL_Process_LinkedIn.

### Step 2 — Odoo Customer Creation (Business Domain)
Create customer in Odoo via odoo-mcp:
```
POST http://localhost:3004/customer
{
  "params": {
    "name": "NexGen Ventures",
    "email": "ahmed@nexgenventures.example.com",
    "phone": "+971-55-0000",
    "city": "Dubai",
    "country_code": "AE"
  }
}
```

### Step 3 — Draft Sales Proposal / Invoice (Business Domain)
Create a draft quotation/invoice in Odoo via odoo-mcp:
```
POST http://localhost:3004/sales-order
{
  "params": {
    "customer_name": "NexGen Ventures",
    "lines": [
      { "name": "Monthly AI Retainer — Starter", "quantity": 3, "price_unit": 500.00 },
      { "name": "AI Automation Setup", "quantity": 1, "price_unit": 1500.00 }
    ],
    "validity_date": "2026-04-11",
    "note": "Proposal for NexGen Ventures — AI automation for email, social, and invoicing."
  }
}
```

### Step 4 — Email Follow-Up (Personal Domain)
Draft a follow-up email with the proposal PDF link via email-mcp.

---

## Expected Claude Behavior

1. Read this file and identify it as a cross-domain LinkedIn lead
2. Execute SKILL_Process_LinkedIn → classify as high-value lead
3. Draft LinkedIn reply → write to /Pending_Approval/LINKEDIN_REPLY_Ahmed_Khalid_*.md
4. Call POST /customer on odoo-mcp → create NexGen Ventures in Odoo
5. Call POST /sales-order on odoo-mcp → create draft quotation
6. Write approval file → /Pending_Approval/ODOO_SALES_ORDER_NexGen_*.md
7. Draft follow-up email → /Pending_Approval/EMAIL_PROPOSAL_NexGen_*.md
8. Log all actions to /Logs/2026-03-11.json
9. Move THIS FILE to /Done/
10. Output: `<promise>TASK_COMPLETE</promise>`
