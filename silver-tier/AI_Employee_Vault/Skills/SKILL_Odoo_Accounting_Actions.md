# SKILL: Odoo Accounting Actions (Full Accounting System)

## Description
Full cross-domain integration between personal workflows (email, social media) and
business accounting via Odoo 19 Community (self-hosted). Interacts with the `odoo-mcp`
server using Odoo's JSON-RPC APIs.

**Cross-domain integration:**
- LinkedIn lead → auto-create customer + draft invoice
- Email invoice request → create Odoo draft invoice → human approval → send
- Weekly CEO briefing pulls live accounting data (P&L, AR aging, cash flow)
- Overdue invoice → automated follow-up email via email-mcp

ALL write actions (invoices, bills, payments, orders) REQUIRE human approval via HITL.
Read-only actions (reports, lists, health) run autonomously.

## Odoo Instance
- **URL:** http://localhost:8069
- **Database:** ai_employee_db
- **MCP Server:** odoo-mcp (http://localhost:3004)
- **API Protocol:** JSON-RPC 2.0 via `/web/dataset/call_kw`

## Trigger
- Files in `/Needs_Action/` with `type: odoo_action`
- Files with prefix `ODOO_*.md`, `WEEKLY_BRIEFING_*.md`
- Called by SKILL_Weekly_CEO_Briefing for accounting data
- Called by SKILL_Process_LinkedIn for new lead → customer creation
- Manual: "Execute SKILL_Odoo_Accounting_Actions"

---

## READ-ONLY Endpoints (autonomous, no approval needed)

### Health Check
```
GET http://localhost:3004/health
→ { success, server, odoo, db, server_version, port }
```

### Revenue Summary
```
GET http://localhost:3004/revenue?date_from=YYYY-MM-01&date_to=YYYY-MM-31
→ { total_revenue, total_collected, total_outstanding, invoice_count, currency, period }
```

### List Customer Invoices
```
GET http://localhost:3004/invoices?state=open&limit=50
  state: draft | posted | open (open = posted + unpaid)
→ { invoices: [{id, name, partner, amount_total, amount_due, due_date, state, payment_state}] }
```

### List Vendor Bills
```
GET http://localhost:3004/bills?state=posted&limit=50
→ { bills: [{id, name, vendor, amount_total, amount_due, due_date, state}], total }
```

### List Customers
```
GET http://localhost:3004/customers?limit=50&search=query
→ { customers: [{id, name, email, phone, city, country, total_invoiced}] }
```

### List Vendors
```
GET http://localhost:3004/vendors?limit=50
→ { vendors: [{id, name, email, phone, payable_balance}] }
```

### List Products & Services
```
GET http://localhost:3004/products?type=service&limit=100
  type: service | consu | product
→ { products: [{id, name, type, sale_price, cost, uom}] }
```

### Chart of Accounts
```
GET http://localhost:3004/accounts?type=asset_receivable&limit=200
→ { accounts: [{id, code, name, type, currency, reconcile}] }
```

### Taxes
```
GET http://localhost:3004/taxes
→ { taxes: [{name, amount, amount_type, type_tax_use}] }
```

### Currencies
```
GET http://localhost:3004/currencies
→ { currencies: [{name, symbol, rate}] }
```

### Payments List
```
GET http://localhost:3004/payments?date_from=YYYY-MM-01&date_to=YYYY-MM-31
→ { payments: [{id, partner, amount, date, type, journal}], total }
```

### Journal Entries
```
GET http://localhost:3004/journal-entries?date_from=YYYY-MM-01&date_to=YYYY-MM-31
→ { entries: [{id, name, date, journal, ref, amount}] }
```

### Analytic Accounts (Cost Centers)
```
GET http://localhost:3004/analytic-accounts
→ { accounts: [{id, name, code, partner, balance, debit, credit}] }
```

### Purchase Orders
```
GET http://localhost:3004/purchase-orders?state=purchase&limit=50
  state: draft | purchase | done | cancel
→ { orders: [{id, name, vendor, amount_total, date_order, state}] }
```

### Sales Orders
```
GET http://localhost:3004/sales-orders?state=sale&limit=50
  state: draft | sale | done | cancel
→ { orders: [{id, name, customer, amount_total, date_order, state, invoice_status}] }
```

### Expenses Summary
```
GET http://localhost:3004/expenses?date_from=YYYY-MM-01&date_to=YYYY-MM-31
→ { expenses: [{id, name, vendor, amount_total, invoice_date}], total }
```

---

## FINANCIAL REPORTS (all auto-approved, read-only)

### Profit & Loss Report
```
GET http://localhost:3004/report/profit-loss?date_from=YYYY-MM-01&date_to=YYYY-MM-31
→ { revenue, expenses, net_profit, profit_margin, invoice_count, bill_count, period }
```

### AR Aging (Accounts Receivable)
```
GET http://localhost:3004/report/ar-aging
→ {
    total_outstanding,
    buckets: {
      current:    { count, total, items: [{id, name, partner, amount_due, due_date, days_overdue}] },
      days_1_30:  { count, total, items: [...] },
      days_31_60: { ... },
      days_61_90: { ... },
      over_90:    { ... }
    }
  }
```

### AP Aging (Accounts Payable)
```
GET http://localhost:3004/report/ap-aging
→ { total_payable, buckets: { current, days_1_30, days_31_60, days_61_90, over_90 } }
```

### Trial Balance
```
GET http://localhost:3004/report/trial-balance?date_from=YYYY-MM-01&date_to=YYYY-MM-31
→ { lines: [{account, debit, credit, balance}], totals: {debit, credit, balanced} }
```

### Balance Sheet
```
GET http://localhost:3004/report/balance-sheet?date=YYYY-MM-DD
→ { summary: {total_assets, total_liabilities, total_equity, balanced}, detail }
```

### Cash Flow Statement
```
GET http://localhost:3004/report/cash-flow?date_from=YYYY-MM-01&date_to=YYYY-MM-31
→ { inflows, outflows, net_cash_flow, transaction_count, detail: {inflows:[...], outflows:[...]} }
```

---

## WRITE Endpoints (ALL require /Approved/ file)

### Create Customer Invoice (Draft)
```
POST http://localhost:3004/invoice
Body: {
  "params": {
    "partner_name": "Tech Solutions Ltd",
    "partner_email": "billing@techsolutions.example.com",
    "lines": [
      { "description": "AI Setup Phase 2", "quantity": 1, "price_unit": 2500.00 },
      { "description": "Monthly Retainer", "quantity": 3, "price_unit": 500.00 }
    ],
    "due_date": "YYYY-MM-DD",
    "ref": "PO-12345",
    "currency_code": "USD"
  }
}
→ { invoice_id, invoice_name, amount_total, state: "draft" }
NOTE: Use amount + description as shorthand for single-line invoices.
```

### Post Invoice (Draft → Confirmed)
```
POST http://localhost:3004/post-invoice
Body: { "params": { "invoice_id": 42 } }
→ { invoice_id, name, state: "posted", amount_total }
```

### Create Vendor Bill (Draft)
```
POST http://localhost:3004/bill
Body: {
  "params": {
    "vendor_name": "Anthropic",
    "lines": [{ "description": "Claude API March 2026", "quantity": 1, "price_unit": 49.00 }],
    "due_date": "YYYY-MM-DD"
  }
}
→ { bill_id, bill_name, amount_total, state: "draft" }
```

### Post Bill (Draft → Confirmed)
```
POST http://localhost:3004/post-bill
Body: { "params": { "bill_id": 15 } }
→ { bill_id, name, state: "posted", amount_total }
```

### Create Credit Note / Refund
```
POST http://localhost:3004/credit-note
Body: {
  "params": {
    "invoice_id": 42,
    "reason": "Service not delivered",
    "refund_method": "refund"   // refund | cancel | modify
  }
}
```

### Register Payment (ALWAYS requires approval)
```
POST http://localhost:3004/payment
Body: {
  "params": {
    "invoice_id": 42,
    "amount": 1500.00,
    "payment_date": "YYYY-MM-DD",
    "journal_id": 7   // optional — bank/cash journal
  }
}
ALWAYS requires explicit HITL approval. Never auto-execute.
```

### Create Customer
```
POST http://localhost:3004/customer
Body: {
  "params": {
    "name": "New Client Ltd",
    "email": "contact@newclient.example.com",
    "phone": "+1-555-0000",
    "city": "New York",
    "country_code": "US",
    "vat": "US123456789"
  }
}
→ { customer_id }
```

### Create Vendor
```
POST http://localhost:3004/vendor
Body: { "params": { "name": "...", "email": "...", "phone": "...", "city": "..." } }
→ { vendor_id }
```

### Create Product/Service
```
POST http://localhost:3004/product
Body: {
  "params": {
    "name": "New Service Package",
    "type": "service",
    "list_price": 750.00,
    "standard_price": 150.00,
    "description": "Monthly AI consulting package"
  }
}
→ { product_id }
```

### Create Manual Journal Entry
```
POST http://localhost:3004/journal-entry
Body: {
  "params": {
    "date": "YYYY-MM-DD",
    "ref": "Adjustment — depreciation",
    "lines": [
      { "account_id": 17, "debit": 500.00, "credit": 0.00, "name": "Depreciation expense" },
      { "account_id": 25, "debit": 0.00,   "credit": 500.00, "name": "Accumulated depreciation" }
    ]
  }
}
VALIDATION: debit total must equal credit total (balanced entry).
```

### Create Purchase Order
```
POST http://localhost:3004/purchase-order
Body: {
  "params": {
    "vendor_name": "Google Cloud",
    "lines": [
      { "name": "Compute Engine Q2", "quantity": 1, "price_unit": 200.00, "date_planned": "YYYY-MM-DD" }
    ]
  }
}
→ { po_id, state: "draft" }
```

### Create Sales Order / Quotation
```
POST http://localhost:3004/sales-order
Body: {
  "params": {
    "customer_name": "Tech Solutions Ltd",
    "lines": [
      { "name": "AI Phase 3", "quantity": 1, "price_unit": 5000.00 }
    ],
    "validity_date": "YYYY-MM-DD",
    "note": "Includes 3-month support"
  }
}
→ { so_id, state: "draft" }
```

---

## HITL Approval Workflow for Write Actions

### Step 1 — Create Approval File
Create `/Pending_Approval/ODOO_{ACTION}_{CLIENT}_{DATE}.md`:
```markdown
---
type: approval_request
action: odoo_create_invoice
mcp_server: odoo-mcp
mcp_endpoint: POST http://localhost:3004/invoice
params:
  partner_name: "Tech Solutions Ltd"
  partner_email: "billing@techsolutions.example.com"
  amount: 2500.00
  description: "AI Automation Phase 2"
  due_date: "2026-04-08"
created: "2026-03-08T10:00:00"
status: pending
---

## Invoice Details
- **Client:** Tech Solutions Ltd
- **Amount:** $2,500.00
- **Service:** AI Automation Phase 2
- **Due:** 2026-04-08

## To Approve — move this file to /Approved/
## To Reject  — move this file to /Rejected/
```

### Step 2 — Wait for Human
The orchestrator detects when the file moves to `/Approved/`.

### Step 3 — Execute via MCP
After approval, call the appropriate endpoint with `Authorization: Bearer {MCP_SECRET}`.
Log the result to `/Logs/YYYY-MM-DD.json` via SKILL_Audit_Logging.
Move the source file to `/Done/`.

---

## Cross-Domain Workflows

### LinkedIn Lead → Odoo Customer + Invoice
1. SKILL_Process_LinkedIn detects new lead message in /Needs_Action/
2. Call `POST /customer` to create customer in Odoo
3. Create approval file for draft invoice (`POST /invoice`)
4. After approval: confirm invoice, send payment link via email-mcp

### Email Invoice Request → Odoo Draft → Send
1. SKILL_Process_Gmail detects invoice request email
2. Extract: client name, amount, services, due date
3. Create approval file for `POST /invoice`
4. After approval: call `POST /post-invoice` to confirm
5. Send PDF link via email-mcp (or notify manually)

### Overdue Invoice → Email Follow-Up
1. odoo_watcher.py creates `ODOO_OVERDUE_INV_*.md` in /Needs_Action/
2. SKILL_Odoo_Accounting_Actions processes it
3. Creates approval for sending payment reminder email
4. After approval: send via email-mcp

### Weekly CEO Briefing Data Pull
1. Call `GET /report/profit-loss` for current month
2. Call `GET /report/ar-aging` for outstanding receivables
3. Call `GET /report/cash-flow` for the week
4. Call `GET /invoices?state=open` for unpaid invoices
5. Call `GET /expenses` for current month expenses
6. Write all data to `/Accounting/Current_Month.md`
7. Return structured data to SKILL_Weekly_CEO_Briefing
8. No approval needed — read-only

---

## CEO Briefing Accounting Summary Format
```markdown
# Accounting Summary — {MONTH YEAR}
Generated: {ISO_TIMESTAMP}

## Revenue (Month-to-Date)
- Total billed: ${total_revenue}
- Collected: ${total_collected}
- Outstanding: ${total_outstanding}
- Invoices issued: {invoice_count}
- Profit margin: {profit_margin}%

## Profit & Loss
| | Amount |
|---|---|
| Revenue | ${revenue} |
| Expenses | ${expenses} |
| **Net Profit** | **${net_profit}** |

## Accounts Receivable Aging
| Bucket | Count | Total |
|--------|-------|-------|
| Current | {n} | ${amount} |
| 1–30 days | {n} | ${amount} |
| 31–60 days | {n} | ${amount} |
| 61–90 days | {n} | ${amount} |
| Over 90 days | {n} | ${amount} |

## Cash Flow
- Inflows: ${inflows}
- Outflows: ${outflows}
- Net: ${net_cash_flow}

## Action Items
- [ ] Follow up on invoices overdue > 30 days
- [ ] Review subscriptions for optimization
- [ ] Post any draft invoices
```

---

## Error Handling
- Odoo down: Write `ODOO_UNAVAILABLE_{DATE}.md` to /Needs_Action/
- Auth failure: Alert human, do NOT retry automatically — reset UID cache
- Unbalanced journal entry: Return 400 error before calling Odoo
- Network timeout: Retry up to 3 times with exponential backoff (1s, 2s, 4s)
- Module not installed: Log error, suggest `python scripts/setup_odoo.py`
- JSON-RPC error: Log full error, create human-review file, invoke SKILL_Error_Recovery

## Security
- Bearer token (`MCP_SECRET`) required for all non-health endpoints
- Localhost only (127.0.0.1) — never exposed to the internet
- No credentials logged (only partner names, amounts, IDs)
- DRY_RUN=true for safe testing — no Odoo writes until explicitly disabled
