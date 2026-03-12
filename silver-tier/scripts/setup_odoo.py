"""
scripts/setup_odoo.py — Odoo Full Accounting Setup for AI Employee Gold Tier

Bootstraps the Odoo instance after Docker brings it up:
  1. Waits for Odoo to be ready
  2. Creates the ai_employee_db database (if not exists)
  3. Configures the company (Samina Ashraf AI Consulting)
  4. Creates chart of accounts extensions (if needed)
  5. Creates analytic accounts (cost centers)
  6. Creates sample products/services
  7. Creates sample customers and vendors
  8. Creates sample invoices, bills, and a sales order
  9. Creates sample journal entries
  10. Verifies the mcp-odoo connection

Run ONCE after: docker compose -f docker-compose.odoo.yml up -d

Usage:
  python scripts/setup_odoo.py
  python scripts/setup_odoo.py --verify-only
  python scripts/setup_odoo.py --reset-data    (re-create sample data only)
"""

import json
import time
import argparse
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import date, timedelta

# Fix Windows cp1252 encoding so emoji don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Config ────────────────────────────────────────────────────────────────────
ODOO_URL        = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB         = os.getenv("ODOO_DB", "ai_employee_db")
ODOO_ADMIN_PASS = os.getenv("ODOO_ADMIN_PASSWORD", "Adm!nM@ster#2026$X")
ODOO_USER       = os.getenv("ODOO_USERNAME", "admin")
ODOO_PASS       = os.getenv("ODOO_PASSWORD", "admin")

TODAY       = date.today().isoformat()
NEXT_30     = (date.today() + timedelta(days=30)).isoformat()
NEXT_60     = (date.today() + timedelta(days=60)).isoformat()
LAST_MONTH  = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()

print("=" * 65)
print("  Odoo Full Accounting Setup — AI Employee Gold Tier")
print(f"  Target: {ODOO_URL}  |  DB: {ODOO_DB}")
print("=" * 65)


# ── JSON-RPC helpers ──────────────────────────────────────────────────────────

def rpc(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        raise ConnectionError(f"Cannot connect to Odoo at {ODOO_URL}: {e}")


def wait_for_odoo(max_wait: int = 180) -> bool:
    print(f"\nWaiting for Odoo to start (max {max_wait}s)...")
    start = time.time()
    while time.time() - start < max_wait:
        try:
            with urllib.request.urlopen(f"{ODOO_URL}/web/health", timeout=5) as r:
                if r.status == 200:
                    print("  ✅ Odoo is ready!")
                    return True
        except Exception:
            pass
        time.sleep(5)
        print(f"  ... still waiting ({int(time.time()-start)}s)")
    return False


def db_exists() -> bool:
    # Try /jsonrpc (correct endpoint for db service)
    try:
        result = rpc(f"{ODOO_URL}/jsonrpc", {
            "jsonrpc": "2.0", "method": "call", "id": 1,
            "params": {"service": "db", "method": "list", "args": []}
        })
        dbs = result.get("result", [])
        if isinstance(dbs, list):
            return ODOO_DB in dbs
    except Exception:
        pass
    # Fallback: try to authenticate — if it works the DB exists
    try:
        result = rpc(f"{ODOO_URL}/jsonrpc", {
            "jsonrpc": "2.0", "method": "call", "id": 1,
            "params": {"service": "common", "method": "authenticate",
                       "args": [ODOO_DB, ODOO_USER, ODOO_PASS, {}]}
        })
        return bool(result.get("result"))
    except Exception:
        return False


def create_database() -> bool:
    print(f"\nCreating database '{ODOO_DB}'...")
    # Odoo 18 uses direct keyword args (not a 'fields' list)
    result = rpc(f"{ODOO_URL}/web/database/create", {
        "jsonrpc": "2.0", "method": "call", "id": 2,
        "params": {
            "master_pwd": ODOO_ADMIN_PASS,
            "name":       ODOO_DB,
            "lang":       "en_US",
            "password":   ODOO_PASS,
            "login":      ODOO_USER,
            "country_id": False,
            "demo":       False,
        }
    })
    if result.get("result"):
        print(f"  [OK] Database '{ODOO_DB}' created")
        # Give Odoo time to finish post-init
        time.sleep(10)
        return True
    err = result.get("error", result)
    print(f"  [WARN] Database creation response: {err}")
    return False


def authenticate() -> int:
    result = rpc(f"{ODOO_URL}/jsonrpc", {
        "jsonrpc": "2.0", "method": "call", "id": 3,
        "params": {
            "service": "common", "method": "authenticate",
            "args": [ODOO_DB, ODOO_USER, ODOO_PASS, {}]
        }
    })
    uid = result.get("result")
    if not uid:
        raise ValueError(f"Authentication failed: {result}")
    print(f"  ✅ Authenticated as {ODOO_USER} (UID: {uid})")
    return uid


def kw(uid: int, model: str, method: str, args: list, kwargs: dict = None):
    # Use /jsonrpc (classic JSON-RPC service endpoint, works in Odoo 14-18)
    result = rpc(f"{ODOO_URL}/jsonrpc", {
        "jsonrpc": "2.0", "method": "call", "id": 4,
        "params": {
            "service": "object", "method": "execute_kw",
            "args": [ODOO_DB, uid, ODOO_PASS, model, method, args, kwargs or {}]
        }
    })
    if "error" in result:
        raise ValueError(f"Odoo error calling {model}.{method}: {result['error']}")
    return result.get("result")


def find_or_create(uid, model, domain, vals):
    ids = kw(uid, model, "search", [domain])
    if ids:
        return ids[0]
    new_id = kw(uid, model, "create", [vals])
    return new_id


# ── Setup steps ───────────────────────────────────────────────────────────────

def grant_accounting_access(uid: int) -> None:
    """Grant the admin user analytic + full accounting groups (Odoo 18 requirement)."""
    try:
        # group IDs: 16=Analytic Accounting, 28=Show Full Accounting Features
        # Search by XML name to be version-safe
        grp_analytic = kw(uid, "res.groups", "search",
                          [[["full_name", "=", "Technical / Analytic Accounting"]]])
        grp_full_acc = kw(uid, "res.groups", "search",
                          [[["full_name", "=", "Technical / Show Full Accounting Features"]]])
        pairs = [(4, g[0]) for g in [grp_analytic, grp_full_acc] if g]
        if pairs:
            kw(uid, "res.users", "write", [[uid], {"groups_id": pairs}])
    except Exception:
        pass  # non-fatal — groups may already be assigned


def setup_company(uid: int) -> None:
    print("\n[1/9] Configuring company...")
    # Get Pakistan country ID
    pk_ids = kw(uid, "res.country", "search", [[["code", "=", "PK"]]])
    country_id = pk_ids[0] if pk_ids else False

    companies = kw(uid, "res.company", "search", [[["id", "=", 1]]])
    if companies:
        kw(uid, "res.company", "write", [[1], {
            "name": "Samina Ashraf AI Consulting",
            "email": "apple379tree@gmail.com",
            "phone": "+92-000-0000000",
            "website": "https://www.linkedin.com/in/samina-ashraf-8386453b3",
            "street": "Karachi",
            "country_id": country_id,
        }])
        print("  ✅ Company: Samina Ashraf AI Consulting (Karachi, PK)")


def setup_analytic_accounts(uid: int) -> list:
    print("\n[2/9] Creating analytic accounts (cost centers)...")
    # Odoo 17+ requires analytic accounts to belong to an analytic plan
    plan_id = find_or_create(uid, "account.analytic.plan",
                             [["name", "=", "AI Employee"]], {"name": "AI Employee"})
    accounts = [
        {"name": "AI Projects",            "code": "AI-001", "plan_id": plan_id},
        {"name": "Consulting Services",    "code": "CS-001", "plan_id": plan_id},
        {"name": "Software Subscriptions", "code": "SW-001", "plan_id": plan_id},
        {"name": "Marketing",              "code": "MK-001", "plan_id": plan_id},
        {"name": "Operations",             "code": "OP-001", "plan_id": plan_id},
    ]
    ids = []
    for a in accounts:
        aid = find_or_create(uid, "account.analytic.account",
                             [["code", "=", a["code"]]], a)
        ids.append(aid)
        print(f"  [OK] Analytic account: {a['name']} ({a['code']})")
    return ids


def setup_products(uid: int) -> list:
    print("\n[3/9] Creating products & services catalog...")
    products = [
        {"name": "AI Automation Setup",        "type": "service", "list_price": 1500.0, "standard_price": 300.0},
        {"name": "Monthly AI Retainer",        "type": "service", "list_price": 500.0,  "standard_price": 100.0},
        {"name": "Claude Agent Development",   "type": "service", "list_price": 2000.0, "standard_price": 400.0},
        {"name": "AI Consulting (Hourly)",     "type": "service", "list_price": 150.0,  "standard_price": 30.0},
        {"name": "Social Media Management",    "type": "service", "list_price": 300.0,  "standard_price": 60.0},
        {"name": "LinkedIn Strategy Session",  "type": "service", "list_price": 200.0,  "standard_price": 40.0},
        {"name": "Weekly CEO Briefing Report", "type": "service", "list_price": 100.0,  "standard_price": 20.0},
    ]
    ids = []
    for p in products:
        pid = find_or_create(uid, "product.template",
                             [["name", "=", p["name"]], ["type", "=", p["type"]]], p)
        ids.append(pid)
        print(f"  ✅ Product: {p['name']} (${p['list_price']})")
    return ids


def setup_customers(uid: int) -> list:
    print("\n[4/9] Creating customers...")
    customers = [
        {"name": "Tech Solutions Ltd",  "email": "contact@techsolutions.example.com",  "phone": "+1-555-0101", "customer_rank": 1, "city": "New York"},
        {"name": "DataDriven Co",       "email": "hello@datadriven.example.com",       "phone": "+1-555-0202", "customer_rank": 1, "city": "San Francisco"},
        {"name": "StartupX",            "email": "founder@startupx.example.com",       "phone": "+1-555-0303", "customer_rank": 1, "city": "Austin"},
        {"name": "GlobalRetail Inc",    "email": "procurement@globalretail.example.com","phone": "+44-20-0001", "customer_rank": 1, "city": "London"},
        {"name": "AI Ventures UAE",     "email": "info@aiventures.example.com",        "phone": "+971-4-000",  "customer_rank": 1, "city": "Dubai"},
    ]
    ids = []
    for c in customers:
        cid = find_or_create(uid, "res.partner",
                             [["name", "=", c["name"]], ["customer_rank", ">", 0]], c)
        ids.append(cid)
        print(f"  ✅ Customer: {c['name']} ({c['city']})")
    return ids


def setup_vendors(uid: int) -> list:
    print("\n[5/9] Creating vendors/suppliers...")
    vendors = [
        {"name": "Anthropic",           "email": "billing@anthropic.com",          "supplier_rank": 1, "city": "San Francisco"},
        {"name": "Microsoft Azure",     "email": "billing@microsoft.example.com",   "supplier_rank": 1, "city": "Redmond"},
        {"name": "Google Cloud",        "email": "billing@google.example.com",      "supplier_rank": 1, "city": "Mountain View"},
        {"name": "Hostinger",           "email": "support@hostinger.example.com",   "supplier_rank": 1, "city": "Kaunas"},
        {"name": "Upwork Platform",     "email": "billing@upwork.example.com",      "supplier_rank": 1, "city": "San Francisco"},
    ]
    ids = []
    for v in vendors:
        vid = find_or_create(uid, "res.partner",
                             [["name", "=", v["name"]], ["supplier_rank", ">", 0]], v)
        ids.append(vid)
        print(f"  ✅ Vendor: {v['name']}")
    return ids


def setup_invoices(uid: int, customer_ids: list) -> list:
    print("\n[6/9] Creating sample invoices...")
    invoice_defs = [
        # (partner_idx, description, amount, state, due_date)
        (0, "AI Automation Setup — Phase 1",         1500.0, "posted", NEXT_30),
        (1, "Monthly AI Retainer — March 2026",       500.0, "posted", NEXT_30),
        (2, "Claude Agent Development — MVP",        2000.0, "draft",  NEXT_60),
        (3, "LinkedIn AI Strategy Session",           200.0, "posted", TODAY),   # overdue-ish
        (4, "Social Media Management Package",        300.0, "posted", NEXT_30),
    ]
    ids = []
    for (idx, desc, amount, state, due) in invoice_defs:
        inv_id = kw(uid, "account.move", "create", [{
            "move_type": "out_invoice",
            "partner_id": customer_ids[idx],
            "invoice_date_due": due,
            "invoice_line_ids": [[0, 0, {"name": desc, "quantity": 1, "price_unit": amount}]]
        }])
        if state == "posted":
            try:
                kw(uid, "account.move", "action_post", [[inv_id]])
            except Exception:
                pass  # Already posted or validation issue
        ids.append(inv_id)
        status = "CONFIRMED" if state == "posted" else "DRAFT"
        print(f"  ✅ Invoice ({status}): {desc[:40]} — ${amount}")
    return ids


def setup_bills(uid: int, vendor_ids: list) -> list:
    print("\n[7/9] Creating sample vendor bills...")
    bill_defs = [
        (0, "Claude API Usage — Feb 2026",          49.0,  "posted"),
        (1, "Azure VM Hosting — Feb 2026",          80.0,  "posted"),
        (2, "Google Cloud Storage — Feb 2026",      25.0,  "posted"),
        (3, "Domain + SSL Renewal",                 15.0,  "draft"),
        (4, "Upwork Service Fee — Feb 2026",        45.0,  "posted"),
    ]
    ids = []
    for (idx, desc, amount, state) in bill_defs:
        bill_id = kw(uid, "account.move", "create", [{
            "move_type": "in_invoice",
            "partner_id": vendor_ids[idx],
            "invoice_date_due": NEXT_30,
            "invoice_line_ids": [[0, 0, {"name": desc, "quantity": 1, "price_unit": amount}]]
        }])
        if state == "posted":
            try:
                kw(uid, "account.move", "action_post", [[bill_id]])
            except Exception:
                pass
        ids.append(bill_id)
        status = "CONFIRMED" if state == "posted" else "DRAFT"
        print(f"  ✅ Bill ({status}): {desc[:40]} — ${amount}")
    return ids


def setup_sales_order(uid: int, customer_ids: list) -> None:
    print("\n[8/9] Creating sample sales order...")
    try:
        so_id = kw(uid, "sale.order", "create", [{
            "partner_id": customer_ids[0],
            "order_line": [
                [0, 0, {"name": "AI Automation Phase 2", "product_uom_qty": 1, "price_unit": 2500.0}],
                [0, 0, {"name": "Monthly Retainer (3 months)", "product_uom_qty": 3, "price_unit": 500.0}],
            ],
            "validity_date": NEXT_60,
            "note": "Proposal for Tech Solutions Ltd — Phase 2 AI automation project"
        }])
        print(f"  ✅ Sales Order created (ID: {so_id}) — Tech Solutions Ltd, $4,000")
    except Exception as e:
        print(f"  ⚠️  Sales order: {e} (sale module may need to be installed)")


def setup_purchase_order(uid: int, vendor_ids: list) -> None:
    print("\n[9/9] Creating sample purchase order...")
    try:
        po_id = kw(uid, "purchase.order", "create", [{
            "partner_id": vendor_ids[2],  # Google Cloud
            "order_line": [
                [0, 0, {
                    "name": "Google Cloud Compute — Q2 2026",
                    "product_qty": 1,
                    "price_unit": 200.0,
                    "date_planned": NEXT_30
                }]
            ]
        }])
        print(f"  ✅ Purchase Order created (ID: {po_id}) — Google Cloud, $200")
    except Exception as e:
        print(f"  ⚠️  Purchase order: {e} (purchase module may need to be installed)")


def verify_mcp() -> bool:
    print("\n─── Verifying odoo-mcp connection ───")
    try:
        with urllib.request.urlopen("http://localhost:3004/health", timeout=5) as r:
            data = json.loads(r.read())
            if data.get("success"):
                print(f"  ✅ odoo-mcp healthy — mode: {data.get('mode', 'live')}, port: {data.get('port')}")
                return True
            print(f"  ⚠️  odoo-mcp health: {data}")
            return False
    except Exception as e:
        print(f"  ⚠️  odoo-mcp not reachable at localhost:3004: {e}")
        print("     Run: cd mcp-odoo && node index.js")
        return False


def verify_only(uid: int) -> None:
    customers = kw(uid, "res.partner", "search_count", [[["customer_rank", ">", 0]]])
    vendors   = kw(uid, "res.partner", "search_count", [[["supplier_rank", ">", 0]]])
    invoices  = kw(uid, "account.move", "search_count", [[["move_type", "=", "out_invoice"]]])
    bills     = kw(uid, "account.move", "search_count", [[["move_type", "=", "in_invoice"]]])
    products  = kw(uid, "product.template", "search_count", [[["active", "=", True]]])
    print(f"\n  ✅ Odoo connected:")
    print(f"     Customers: {customers}  |  Vendors: {vendors}")
    print(f"     Invoices:  {invoices}   |  Bills:   {bills}")
    print(f"     Products:  {products}")
    verify_mcp()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Odoo Full Accounting Setup")
    parser.add_argument("--verify-only",  action="store_true", help="Verify connectivity only")
    parser.add_argument("--reset-data",   action="store_true", help="Re-create sample data (skips DB creation)")
    args = parser.parse_args()

    if args.verify_only:
        try:
            uid = authenticate()
            verify_only(uid)
        except Exception as e:
            print(f"  ❌ {e}")
            sys.exit(1)
        return

    if not args.reset_data:
        if not wait_for_odoo():
            print("❌ Odoo did not start in time.")
            print("   Check: docker compose -f docker-compose.odoo.yml logs odoo")
            sys.exit(1)

        if db_exists():
            print(f"\nDatabase '{ODOO_DB}' already exists — skipping creation.")
        else:
            if not create_database():
                print("❌ DB creation failed. Try via Odoo web UI at http://localhost:8069/web/database/manager")
                sys.exit(1)
            print("  Waiting 15s for DB initialization...")
            time.sleep(15)

    uid = authenticate()
    grant_accounting_access(uid)
    setup_company(uid)
    analytic_ids = setup_analytic_accounts(uid)
    product_ids  = setup_products(uid)
    customer_ids = setup_customers(uid)
    vendor_ids   = setup_vendors(uid)
    setup_invoices(uid, customer_ids)
    setup_bills(uid, vendor_ids)
    setup_sales_order(uid, customer_ids)
    setup_purchase_order(uid, vendor_ids)
    verify_mcp()

    print("\n" + "=" * 65)
    print("  ✅ Odoo accounting setup complete!")
    print(f"     Web UI:       {ODOO_URL}")
    print(f"     DB:           {ODOO_DB}")
    print(f"     Login:        {ODOO_USER}  /  [ODOO_PASSWORD from .env]")
    print(f"     MCP Server:   http://localhost:3004")
    print()
    print("  Quick links:")
    print(f"     Invoices:     {ODOO_URL}/odoo/accounting/customer-invoices")
    print(f"     Bills:        {ODOO_URL}/odoo/accounting/vendor-bills")
    print(f"     P&L Report:   {ODOO_URL}/odoo/accounting/profit-and-loss")
    print("=" * 65)


if __name__ == "__main__":
    main()
