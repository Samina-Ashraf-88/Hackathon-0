"""
watchers/odoo_watcher.py — Odoo Accounting Monitor

Polls the odoo-mcp server periodically and creates /Needs_Action/ files
when financial events require human attention:

  - Overdue invoices (AR aging > 30 days)
  - Bills due soon (AP aging ≤ 3 days)
  - Low cash flow warning (outflows > inflows for the period)
  - Large sales orders awaiting invoicing
  - Weekly P&L summary (triggered on Mondays for CEO Briefing)

Run with:
  python watchers/odoo_watcher.py

Or via PM2 (ecosystem.gold.config.js):
  pm2 start ecosystem.gold.config.js --only odoo-watcher
"""

import os
import sys
import json
import time
import datetime
import urllib.request
import urllib.error
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
ODOO_MCP_URL   = os.getenv("ODOO_MCP_URL", "http://localhost:3004")
MCP_SECRET     = os.getenv("MCP_SECRET", "dev-secret-change-me")
VAULT_PATH     = Path(os.getenv("VAULT_PATH", "E:/hackathon-0/silver-tier/AI_Employee_Vault"))
CHECK_INTERVAL = int(os.getenv("ODOO_CHECK_INTERVAL", "3600"))  # 1 hour default
DRY_RUN        = os.getenv("DRY_RUN", "true").lower() == "true"

NEEDS_ACTION   = VAULT_PATH / "Needs_Action"
LOGS_DIR       = VAULT_PATH / "Logs"
PROCESSED_LOG  = VAULT_PATH / ".odoo_watcher_state.json"

# Thresholds
OVERDUE_DAYS_THRESHOLD = 30   # Flag invoices overdue > 30 days
BILLS_DUE_SOON_DAYS    = 3    # Flag bills due within 3 days
CASH_FLOW_WARN_RATIO   = 0.8  # Warn if outflows > 80% of inflows


# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    print(f"[{ts}] [{level}] [odoo-watcher] {msg}")


def mcp_get(endpoint: str, params: dict = None) -> dict:
    url = f"{ODOO_MCP_URL}{endpoint}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {MCP_SECRET}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"HTTP {e.code} on {endpoint}: {e.reason}", "WARN")
        return {"success": False, "error": str(e)}
    except Exception as e:
        log(f"Error calling {endpoint}: {e}", "ERROR")
        return {"success": False, "error": str(e)}


def write_needs_action(filename: str, content: str) -> bool:
    if DRY_RUN:
        log(f"[DRY RUN] Would write /Needs_Action/{filename}")
        return True
    NEEDS_ACTION.mkdir(parents=True, exist_ok=True)
    filepath = NEEDS_ACTION / filename
    if filepath.exists():
        log(f"Skipping — already exists: {filename}")
        return False
    filepath.write_text(content, encoding="utf-8")
    log(f"Created: /Needs_Action/{filename}")
    return True


def load_state() -> dict:
    if PROCESSED_LOG.exists():
        try:
            return json.loads(PROCESSED_LOG.read_text())
        except Exception:
            pass
    return {"last_check": None, "alerted_invoice_ids": [], "alerted_bill_ids": []}


def save_state(state: dict) -> None:
    if DRY_RUN:
        return
    PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_LOG.write_text(json.dumps(state, indent=2), encoding="utf-8")


def today_str() -> str:
    return datetime.date.today().isoformat()


def this_month() -> tuple:
    t = datetime.date.today()
    first = t.replace(day=1).isoformat()
    last  = t.isoformat()
    return first, last


# ── Check functions ───────────────────────────────────────────────────────────

def check_overdue_invoices(state: dict) -> int:
    """Flag customer invoices overdue > OVERDUE_DAYS_THRESHOLD days."""
    log("Checking overdue AR invoices...")
    data = mcp_get("/report/ar-aging")
    if not data.get("success"):
        log(f"AR aging check failed: {data.get('error')}", "WARN")
        return 0

    alerted = set(state.get("alerted_invoice_ids", []))
    new_alerts = 0
    buckets = data.get("buckets", {})

    for bucket_key in ["days_31_60", "days_61_90", "over_90"]:
        bucket = buckets.get(bucket_key, {})
        for inv in bucket.get("items", []):
            inv_id = inv.get("id")
            if inv_id in alerted:
                continue
            days = inv.get("days_overdue", 0)
            partner = inv.get("partner", "Unknown")
            amount  = inv.get("amount_due", 0)
            due_date = inv.get("due_date", "unknown")
            filename = f"ODOO_OVERDUE_INV_{inv_id}_{today_str()}.md"
            content = f"""---
type: odoo_action
action: follow_up_overdue_invoice
invoice_id: {inv_id}
partner: "{partner}"
amount_due: {amount}
due_date: "{due_date}"
days_overdue: {days}
priority: {"high" if days > 60 else "medium"}
created: "{datetime.datetime.now().isoformat()}"
auto_approve: false
---

# Overdue Invoice Follow-Up Required

**Invoice:** {inv.get("name", f"INV-{inv_id}")}
**Client:** {partner}
**Amount Due:** ${amount:,.2f}
**Due Date:** {due_date}
**Days Overdue:** {days} days

## Recommended Actions
- [ ] Send payment reminder email to {partner}
- [ ] Check if payment is in progress
- [ ] Escalate if > 60 days: consider late fee or pause services

## To Act
- Move to `/Approved/` to trigger automated email reminder
- Or handle manually in Odoo: {os.getenv("ODOO_URL", "http://localhost:8069")}/odoo/accounting/customer-invoices
"""
            if write_needs_action(filename, content):
                alerted.add(inv_id)
                new_alerts += 1

    state["alerted_invoice_ids"] = list(alerted)
    log(f"Overdue invoices: {new_alerts} new alerts")
    return new_alerts


def check_bills_due_soon(state: dict) -> int:
    """Flag vendor bills due within BILLS_DUE_SOON_DAYS."""
    log("Checking upcoming payables...")
    data = mcp_get("/report/ap-aging")
    if not data.get("success"):
        log(f"AP aging check failed: {data.get('error')}", "WARN")
        return 0

    alerted = set(state.get("alerted_bill_ids", []))
    new_alerts = 0
    today = datetime.date.today()

    current_bills = data.get("buckets", {}).get("current", {}).get("items", [])
    for bill in current_bills:
        bill_id = bill.get("id")
        if bill_id in alerted:
            continue
        due_date_str = bill.get("due_date")
        if not due_date_str:
            continue
        try:
            due_date = datetime.date.fromisoformat(due_date_str)
            days_until = (due_date - today).days
            if days_until > BILLS_DUE_SOON_DAYS:
                continue
        except ValueError:
            continue

        vendor = bill.get("vendor", "Unknown")
        amount = bill.get("amount_due", 0)
        filename = f"ODOO_BILL_DUE_{bill_id}_{today_str()}.md"
        content = f"""---
type: odoo_action
action: review_upcoming_bill
bill_id: {bill_id}
vendor: "{vendor}"
amount_due: {amount}
due_date: "{due_date_str}"
days_until_due: {days_until}
created: "{datetime.datetime.now().isoformat()}"
auto_approve: false
---

# Vendor Bill Due Soon

**Bill:** {bill.get("name", f"BILL-{bill_id}")}
**Vendor:** {vendor}
**Amount:** ${amount:,.2f}
**Due:** {due_date_str} ({days_until} days)

## Action Required
- [ ] Verify funds available for payment
- [ ] Approve payment in Odoo or schedule via MCP /payment endpoint

## Odoo Link
{os.getenv("ODOO_URL", "http://localhost:8069")}/odoo/accounting/vendor-bills
"""
        if write_needs_action(filename, content):
            alerted.add(bill_id)
            new_alerts += 1

    state["alerted_bill_ids"] = list(alerted)
    log(f"Bills due soon: {new_alerts} new alerts")
    return new_alerts


def check_cash_flow(state: dict) -> int:
    """Warn if monthly cash outflows exceed threshold relative to inflows."""
    log("Checking cash flow...")
    date_from, date_to = this_month()
    data = mcp_get("/report/cash-flow", {"date_from": date_from, "date_to": date_to})
    if not data.get("success"):
        log(f"Cash flow check failed: {data.get('error')}", "WARN")
        return 0

    inflows  = data.get("inflows", 0)
    outflows = data.get("outflows", 0)
    net      = data.get("net_cash_flow", 0)

    if inflows == 0 or outflows == 0:
        return 0  # No data yet

    ratio = outflows / inflows if inflows > 0 else 999
    if ratio <= CASH_FLOW_WARN_RATIO:
        return 0  # Healthy

    last_warn = state.get("last_cashflow_warn")
    if last_warn == today_str():
        return 0  # Already warned today

    filename = f"ODOO_CASHFLOW_WARN_{today_str()}.md"
    content = f"""---
type: odoo_action
action: review_cash_flow
period_from: "{date_from}"
period_to: "{date_to}"
inflows: {inflows}
outflows: {outflows}
net_cash_flow: {net}
outflow_ratio: {ratio:.1%}
created: "{datetime.datetime.now().isoformat()}"
auto_approve: false
---

# Cash Flow Warning — {datetime.date.today().strftime("%B %Y")}

**Period:** {date_from} to {date_to}
**Inflows:** ${inflows:,.2f}
**Outflows:** ${outflows:,.2f}
**Net Cash Flow:** ${net:,.2f}
**Outflow Ratio:** {ratio:.1%} of inflows

## ⚠️ Alert
Outflows are at {ratio:.1%} of inflows this period — above the {CASH_FLOW_WARN_RATIO:.0%} threshold.

## Recommended Actions
- [ ] Review upcoming expenses and defer non-critical ones
- [ ] Follow up on outstanding invoices to accelerate receivables
- [ ] Check P&L report for cost reduction opportunities
"""
    wrote = write_needs_action(filename, content)
    if wrote:
        state["last_cashflow_warn"] = today_str()
    return 1 if wrote else 0


def check_weekly_briefing(state: dict) -> int:
    """Trigger weekly CEO briefing on Mondays."""
    today = datetime.date.today()
    if today.weekday() != 0:  # 0 = Monday
        return 0

    last_briefing = state.get("last_weekly_briefing")
    if last_briefing == today_str():
        return 0

    log("Monday detected — creating weekly CEO briefing request...")

    # Pull accounting summary for the briefing
    date_from = (today - datetime.timedelta(days=7)).isoformat()
    date_to   = today.isoformat()

    revenue_data = mcp_get("/revenue", {"date_from": date_from, "date_to": date_to})
    pl_data      = mcp_get("/report/profit-loss", {"date_from": date_from, "date_to": date_to})
    ar_data      = mcp_get("/report/ar-aging")

    total_rev    = revenue_data.get("total_revenue", 0) if revenue_data.get("success") else "N/A"
    net_profit   = pl_data.get("net_profit", 0) if pl_data.get("success") else "N/A"
    ar_total     = ar_data.get("total_outstanding", 0) if ar_data.get("success") else "N/A"

    filename = f"WEEKLY_BRIEFING_{today_str()}.md"
    content = f"""---
type: weekly_briefing
period_from: "{date_from}"
period_to: "{date_to}"
created: "{datetime.datetime.now().isoformat()}"
auto_approve: false
---

# Weekly CEO Briefing Request — {today.strftime("%B %d, %Y")}

Auto-generated by odoo-watcher on Monday morning.
Execute `SKILL_Weekly_CEO_Briefing` to generate the full report.

## Accounting Snapshot (Last 7 Days)
- **Revenue:** ${total_rev:,.2f} (if numeric)
- **Net Profit:** ${net_profit:,.2f} (if numeric)
- **Outstanding AR:** ${ar_total:,.2f} (if numeric)

## Tasks for the Briefing
- [ ] Pull full P&L for the week
- [ ] List all open invoices and overdue AR
- [ ] Summarize vendor bills paid and upcoming
- [ ] Social media performance summary
- [ ] Key actions for the coming week

Execute SKILL_Weekly_CEO_Briefing to complete this briefing.
"""
    wrote = write_needs_action(filename, content)
    if wrote:
        state["last_weekly_briefing"] = today_str()
    return 1 if wrote else 0


def check_unposted_invoices(state: dict) -> int:
    """Alert on invoices sitting in draft for too long (> 2 days)."""
    log("Checking for stale draft invoices...")
    data = mcp_get("/invoices", {"state": "draft", "limit": "20"})
    if not data.get("success"):
        return 0

    new_alerts = 0
    alerted = set(state.get("alerted_draft_invoice_ids", []))
    two_days_ago = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()

    for inv in data.get("invoices", []):
        inv_id = inv.get("id")
        if inv_id in alerted:
            continue
        inv_date = inv.get("invoice_date") or ""
        if inv_date and inv_date > two_days_ago:
            continue  # Recent — give it time

        partner = inv.get("partner", "Unknown")
        amount  = inv.get("amount_total", 0)
        filename = f"ODOO_DRAFT_INV_{inv_id}_{today_str()}.md"
        content = f"""---
type: odoo_action
action: review_draft_invoice
invoice_id: {inv_id}
partner: "{partner}"
amount_total: {amount}
invoice_name: "{inv.get("name", "")}"
created: "{datetime.datetime.now().isoformat()}"
auto_approve: false
---

# Draft Invoice Needs Attention

**Invoice:** {inv.get("name", f"Draft-{inv_id}")}
**Client:** {partner}
**Amount:** ${amount:,.2f}
**Status:** DRAFT (not yet sent)

## Action Required
- [ ] Review the invoice in Odoo
- [ ] Post (confirm) it to send to client: use POST /post-invoice with invoice_id={inv_id}
- [ ] Or cancel if no longer needed

## Odoo Link
{os.getenv("ODOO_URL", "http://localhost:8069")}/odoo/accounting/customer-invoices
"""
        if write_needs_action(filename, content):
            alerted.add(inv_id)
            new_alerts += 1

    state["alerted_draft_invoice_ids"] = list(alerted)
    return new_alerts


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_checks() -> None:
    log(f"Running Odoo accounting checks (dry_run={DRY_RUN})...")
    state = load_state()

    total_alerts = 0
    total_alerts += check_overdue_invoices(state)
    total_alerts += check_bills_due_soon(state)
    total_alerts += check_cash_flow(state)
    total_alerts += check_weekly_briefing(state)
    total_alerts += check_unposted_invoices(state)

    state["last_check"] = datetime.datetime.now().isoformat()
    save_state(state)

    log(f"Checks complete — {total_alerts} new action items created")


def main():
    log(f"Odoo Watcher started | MCP: {ODOO_MCP_URL} | interval: {CHECK_INTERVAL}s | vault: {VAULT_PATH}")
    if DRY_RUN:
        log("DRY RUN MODE — no files will be written")

    # Run once immediately, then loop
    while True:
        try:
            # Check if MCP is up
            health = mcp_get("/health")
            if not health.get("success"):
                log(f"odoo-mcp not healthy: {health.get('error', 'unknown')} — skipping checks", "WARN")
            else:
                run_checks()
        except Exception as e:
            log(f"Check cycle error: {e}", "ERROR")

        log(f"Sleeping {CHECK_INTERVAL}s until next check...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
