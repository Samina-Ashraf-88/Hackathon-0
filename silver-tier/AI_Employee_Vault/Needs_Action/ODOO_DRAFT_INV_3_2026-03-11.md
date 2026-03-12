---
type: odoo_action
action: review_draft_invoice
invoice_id: 3
partner: "StartupX"
amount_total: 2000
invoice_name: "False"
created: "2026-03-11T12:47:22.832443"
auto_approve: false
---

# Draft Invoice Needs Attention

**Invoice:** False
**Client:** StartupX
**Amount:** $2,000.00
**Status:** DRAFT (not yet sent)

## Action Required
- [ ] Review the invoice in Odoo
- [ ] Post (confirm) it to send to client: use POST /post-invoice with invoice_id=3
- [ ] Or cancel if no longer needed

## Odoo Link
http://localhost:8069/odoo/accounting/customer-invoices
