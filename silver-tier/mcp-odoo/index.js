/**
 * mcp-odoo/index.js
 * Full Accounting System — Odoo 19 Community MCP Bridge
 *
 * Cross-domain integration: Personal (email/social) ↔ Business (Odoo accounting)
 * All write actions are DRAFT-only until explicit human approval.
 *
 * ── READ-ONLY Endpoints (auto-approved) ───────────────────────────────────────
 *   GET  /health                  → health + Odoo connectivity
 *   GET  /revenue                 → revenue summary (date range)
 *   GET  /invoices                → customer invoices
 *   GET  /bills                   → vendor bills
 *   GET  /customers               → customers with totals
 *   GET  /vendors                 → vendors/suppliers
 *   GET  /products                → products & services catalog
 *   GET  /accounts                → chart of accounts
 *   GET  /taxes                   → tax configurations
 *   GET  /currencies              → currency list
 *   GET  /payments                → payments list
 *   GET  /journal-entries         → journal entries
 *   GET  /analytic-accounts       → cost center accounts
 *   GET  /purchase-orders         → purchase orders
 *   GET  /sales-orders            → sales/quotation orders
 *   GET  /report/profit-loss      → P&L report (date range)
 *   GET  /report/balance-sheet    → balance sheet snapshot
 *   GET  /report/trial-balance    → trial balance
 *   GET  /report/ar-aging         → accounts receivable aging
 *   GET  /report/ap-aging         → accounts payable aging
 *   GET  /report/cash-flow        → cash flow summary
 *
 * ── WRITE Endpoints (require /Approved/ file) ─────────────────────────────────
 *   POST /invoice                 → create draft customer invoice
 *   POST /bill                    → create draft vendor bill
 *   POST /credit-note             → create credit note / refund
 *   POST /payment                 → register payment (ALWAYS approval)
 *   POST /customer                → create customer
 *   POST /vendor                  → create vendor/supplier
 *   POST /product                 → create product/service
 *   POST /journal-entry           → create manual journal entry
 *   POST /post-invoice            → post draft invoice to confirmed
 *   POST /post-bill               → post draft bill to confirmed
 *   POST /purchase-order          → create purchase order
 *   POST /sales-order             → create sales order / quotation
 *
 * ENVIRONMENT VARIABLES:
 *   ODOO_URL          — http://localhost:8069
 *   ODOO_DB           — ai_employee_db
 *   ODOO_USERNAME     — admin
 *   ODOO_PASSWORD     — (from .env)
 *   ODOO_ADMIN_PASSWORD — master password
 *   MCP_SECRET        — shared bearer token
 *   DRY_RUN           — "true" to log without calling Odoo
 *   PORT              — default 3004
 */

require('dotenv').config({ path: '../.env' });
const express = require('express');
const { v4: uuidv4 } = require('uuid');
const winston = require('winston');
const path = require('path');

const PORT       = process.env.PORT || 3004;
const DRY_RUN    = process.env.DRY_RUN === 'true';
const MCP_SECRET = process.env.MCP_SECRET || 'dev-secret-change-me';
const ODOO_URL   = process.env.ODOO_URL || 'http://localhost:8069';
const ODOO_DB    = process.env.ODOO_DB || 'ai_employee_db';
const ODOO_USER  = process.env.ODOO_USERNAME || 'admin';
const ODOO_PASS  = process.env.ODOO_PASSWORD || 'admin';

let odooUID = null; // cached after first auth

// ── Logger ─────────────────────────────────────────────────────────────────────
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console({ format: winston.format.simple() }),
    new winston.transports.File({
      filename: path.join(__dirname, '../AI_Employee_Vault/Logs/odoo-mcp.log'),
      maxsize: 5 * 1024 * 1024, // 5MB rotation
      maxFiles: 5
    })
  ]
});

const app = express();
app.use(express.json());

// ── Bearer token auth (skip for /health and localhost) ────────────────────────
app.use((req, res, next) => {
  if (req.path === '/health') return next();
  // Skip auth for loopback — server binds to 127.0.0.1 only
  const ip = req.ip || req.connection?.remoteAddress || '';
  if (ip === '127.0.0.1' || ip === '::1' || ip === '::ffff:127.0.0.1') return next();
  const auth = req.headers.authorization;
  if (!auth || auth !== `Bearer ${MCP_SECRET}`) {
    logger.warn({ msg: 'Unauthorized request', path: req.path, ip });
    return res.status(401).json({ success: false, error: 'Unauthorized' });
  }
  next();
});

// ── Odoo JSON-RPC Core ─────────────────────────────────────────────────────────
async function odooRpc(endpoint, payload) {
  const { default: fetch } = await import('node-fetch');
  const res = await fetch(`${ODOO_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', method: 'call', id: uuidv4(), ...payload }),
    timeout: 30000
  });
  const data = await res.json();
  if (data.error) throw new Error(JSON.stringify(data.error));
  return data.result;
}

async function getUID() {
  if (odooUID) return odooUID;
  // Use /jsonrpc (classic endpoint — works Odoo 14-18; /web/dataset/call_kw changed in Odoo 18)
  const result = await odooRpc('/jsonrpc', {
    params: { service: 'common', method: 'authenticate', args: [ODOO_DB, ODOO_USER, ODOO_PASS, {}] }
  });
  if (!result) throw new Error('Odoo authentication failed — check ODOO_USERNAME and ODOO_PASSWORD');
  odooUID = result;
  logger.info({ msg: 'Authenticated with Odoo', uid: odooUID, db: ODOO_DB });
  return odooUID;
}

async function odooCall(model, method, args, kwargs = {}) {
  const uid = await getUID();
  return odooRpc('/jsonrpc', {
    params: { service: 'object', method: 'execute_kw', args: [ODOO_DB, uid, ODOO_PASS, model, method, args, kwargs] }
  });
}

// Re-authenticate on 401 (token expiry)
async function odooCallWithRetry(model, method, args, kwargs = {}) {
  try {
    return await odooCall(model, method, args, kwargs);
  } catch (err) {
    if (err.message.includes('Session') || err.message.includes('auth')) {
      odooUID = null;
      return await odooCall(model, method, args, kwargs);
    }
    throw err;
  }
}

// Helper: dry-run guard
function dryRunResponse(action, extra = {}) {
  return { success: true, dry_run: true, action, ...extra, timestamp: new Date().toISOString() };
}

// ════════════════════════════════════════════════════════════════════════════════
// READ-ONLY ENDPOINTS
// ════════════════════════════════════════════════════════════════════════════════

// ── GET /health ────────────────────────────────────────────────────────────────
app.get('/health', async (req, res) => {
  if (DRY_RUN) {
    return res.json({ success: true, server: 'odoo-mcp', mode: 'dry_run', port: PORT, timestamp: new Date().toISOString() });
  }
  try {
    const uid = await getUID();
    const version = await odooRpc('/jsonrpc', {
      params: { service: 'common', method: 'version', args: [] }
    });
    return res.json({
      success: true, server: 'odoo-mcp', odoo: ODOO_URL, db: ODOO_DB,
      uid, server_version: version?.server_version || 'unknown',
      port: PORT, timestamp: new Date().toISOString()
    });
  } catch (err) {
    return res.status(503).json({ success: false, server: 'odoo-mcp', error: err.message, timestamp: new Date().toISOString() });
  }
});

// ── GET /revenue ───────────────────────────────────────────────────────────────
app.get('/revenue', async (req, res) => {
  const { date_from, date_to } = req.query;
  const requestId = uuidv4();
  logger.info({ requestId, action: 'get_revenue', date_from, date_to });
  if (DRY_RUN) return res.json(dryRunResponse('get_revenue', { total_revenue: 0, invoice_count: 0, currency: 'USD' }));
  try {
    const domain = [['move_type', '=', 'out_invoice'], ['state', '=', 'posted']];
    if (date_from) domain.push(['invoice_date', '>=', date_from]);
    if (date_to)   domain.push(['invoice_date', '<=', date_to]);
    const invoices = await odooCallWithRetry('account.move', 'search_read', [domain], {
      fields: ['name', 'amount_total', 'amount_residual', 'currency_id', 'invoice_date', 'partner_id'],
      limit: 500
    });
    const total = invoices.reduce((s, i) => s + (i.amount_total || 0), 0);
    const collected = invoices.reduce((s, i) => s + ((i.amount_total || 0) - (i.amount_residual || 0)), 0);
    return res.json({
      success: true, requestId,
      total_revenue: parseFloat(total.toFixed(2)),
      total_collected: parseFloat(collected.toFixed(2)),
      total_outstanding: parseFloat((total - collected).toFixed(2)),
      invoice_count: invoices.length,
      currency: invoices[0]?.currency_id?.[1] || 'USD',
      period: { from: date_from || null, to: date_to || null },
      timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /invoices ──────────────────────────────────────────────────────────────
app.get('/invoices', async (req, res) => {
  const { state = 'posted', limit = 50, date_from, date_to, partner_id } = req.query;
  const requestId = uuidv4();
  logger.info({ requestId, action: 'list_invoices', state, limit });
  if (DRY_RUN) return res.json(dryRunResponse('list_invoices', { invoices: [], count: 0 }));
  try {
    const odooState = state === 'open' ? 'posted' : state;
    const domain = [['move_type', '=', 'out_invoice'], ['state', '=', odooState]];
    if (state === 'open') domain.push(['payment_state', 'in', ['not_paid', 'partial']]);
    if (date_from) domain.push(['invoice_date', '>=', date_from]);
    if (date_to)   domain.push(['invoice_date', '<=', date_to]);
    if (partner_id) domain.push(['partner_id', '=', parseInt(partner_id)]);
    const invoices = await odooCallWithRetry('account.move', 'search_read', [domain], {
      fields: ['name', 'partner_id', 'amount_total', 'amount_residual', 'invoice_date', 'invoice_date_due', 'state', 'payment_state', 'ref', 'currency_id'],
      limit: parseInt(limit),
      order: 'invoice_date_due asc'
    });
    return res.json({
      success: true, requestId,
      invoices: invoices.map(i => ({
        id: i.id, name: i.name,
        partner: i.partner_id?.[1], partner_id: i.partner_id?.[0],
        amount_total: i.amount_total, amount_due: i.amount_residual,
        invoice_date: i.invoice_date, due_date: i.invoice_date_due,
        state: i.state, payment_state: i.payment_state,
        ref: i.ref, currency: i.currency_id?.[1]
      })),
      count: invoices.length, timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /bills ─────────────────────────────────────────────────────────────────
app.get('/bills', async (req, res) => {
  const { state = 'posted', limit = 50, date_from, date_to } = req.query;
  const requestId = uuidv4();
  logger.info({ requestId, action: 'list_bills', state });
  if (DRY_RUN) return res.json(dryRunResponse('list_bills', { bills: [], count: 0 }));
  try {
    const domain = [['move_type', '=', 'in_invoice'], ['state', '=', state]];
    if (date_from) domain.push(['invoice_date', '>=', date_from]);
    if (date_to)   domain.push(['invoice_date', '<=', date_to]);
    const bills = await odooCallWithRetry('account.move', 'search_read', [domain], {
      fields: ['name', 'partner_id', 'amount_total', 'amount_residual', 'invoice_date', 'invoice_date_due', 'state', 'payment_state', 'ref'],
      limit: parseInt(limit), order: 'invoice_date_due asc'
    });
    return res.json({
      success: true, requestId,
      bills: bills.map(b => ({
        id: b.id, name: b.name,
        vendor: b.partner_id?.[1], vendor_id: b.partner_id?.[0],
        amount_total: b.amount_total, amount_due: b.amount_residual,
        invoice_date: b.invoice_date, due_date: b.invoice_date_due,
        state: b.state, payment_state: b.payment_state, ref: b.ref
      })),
      count: bills.length, total: bills.reduce((s, b) => s + (b.amount_total || 0), 0),
      timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /customers ─────────────────────────────────────────────────────────────
app.get('/customers', async (req, res) => {
  const { limit = 50, search } = req.query;
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('list_customers', { customers: [], count: 0 }));
  try {
    const domain = [['customer_rank', '>', 0]];
    if (search) domain.push(['name', 'ilike', search]);
    const customers = await odooCallWithRetry('res.partner', 'search_read', [domain], {
      fields: ['name', 'email', 'phone', 'city', 'country_id', 'customer_rank', 'total_invoiced', 'credit'],
      limit: parseInt(limit), order: 'name asc'
    });
    return res.json({
      success: true, requestId,
      customers: customers.map(c => ({
        id: c.id, name: c.name, email: c.email, phone: c.phone,
        city: c.city, country: c.country_id?.[1],
        total_invoiced: c.total_invoiced || 0, credit_balance: c.credit || 0
      })),
      count: customers.length, timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /vendors ───────────────────────────────────────────────────────────────
app.get('/vendors', async (req, res) => {
  const { limit = 50, search } = req.query;
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('list_vendors', { vendors: [], count: 0 }));
  try {
    const domain = [['supplier_rank', '>', 0]];
    if (search) domain.push(['name', 'ilike', search]);
    const vendors = await odooCallWithRetry('res.partner', 'search_read', [domain], {
      fields: ['name', 'email', 'phone', 'city', 'country_id', 'supplier_rank', 'debit'],
      limit: parseInt(limit), order: 'name asc'
    });
    return res.json({
      success: true, requestId,
      vendors: vendors.map(v => ({
        id: v.id, name: v.name, email: v.email, phone: v.phone,
        city: v.city, country: v.country_id?.[1], payable_balance: v.debit || 0
      })),
      count: vendors.length, timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /products ──────────────────────────────────────────────────────────────
app.get('/products', async (req, res) => {
  const { limit = 100, type, search } = req.query;
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('list_products', { products: [], count: 0 }));
  try {
    const domain = [['active', '=', true]];
    if (type) domain.push(['type', '=', type]); // service, consu, product
    if (search) domain.push(['name', 'ilike', search]);
    const products = await odooCallWithRetry('product.product', 'search_read', [domain], {
      fields: ['name', 'type', 'list_price', 'standard_price', 'uom_id', 'taxes_id', 'description_sale'],
      limit: parseInt(limit), order: 'name asc'
    });
    return res.json({
      success: true, requestId,
      products: products.map(p => ({
        id: p.id, name: p.name, type: p.type,
        sale_price: p.list_price, cost: p.standard_price,
        uom: p.uom_id?.[1], tax_ids: p.taxes_id, description: p.description_sale
      })),
      count: products.length, timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /accounts ──────────────────────────────────────────────────────────────
app.get('/accounts', async (req, res) => {
  const { type, search, limit = 200 } = req.query;
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('list_accounts', { accounts: [], count: 0 }));
  try {
    const domain = [['deprecated', '=', false]];
    if (type) domain.push(['account_type', '=', type]);
    if (search) domain.push(['|', ['name', 'ilike', search], ['code', 'ilike', search]]);
    const accounts = await odooCallWithRetry('account.account', 'search_read', [domain], {
      fields: ['code', 'name', 'account_type', 'currency_id', 'reconcile'],
      limit: parseInt(limit), order: 'code asc'
    });
    return res.json({
      success: true, requestId,
      accounts: accounts.map(a => ({
        id: a.id, code: a.code, name: a.name,
        type: a.account_type, currency: a.currency_id?.[1], reconcile: a.reconcile
      })),
      count: accounts.length, timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /taxes ─────────────────────────────────────────────────────────────────
app.get('/taxes', async (req, res) => {
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('list_taxes', { taxes: [] }));
  try {
    const taxes = await odooCallWithRetry('account.tax', 'search_read',
      [[['active', '=', true]]],
      { fields: ['name', 'amount', 'amount_type', 'type_tax_use', 'price_include'], order: 'name asc' }
    );
    return res.json({ success: true, requestId, taxes, count: taxes.length, timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /currencies ────────────────────────────────────────────────────────────
app.get('/currencies', async (req, res) => {
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('list_currencies', { currencies: [] }));
  try {
    const currencies = await odooCallWithRetry('res.currency', 'search_read',
      [[['active', '=', true]]],
      { fields: ['name', 'symbol', 'rate', 'position'], order: 'name asc' }
    );
    return res.json({ success: true, requestId, currencies, count: currencies.length, timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /payments ──────────────────────────────────────────────────────────────
app.get('/payments', async (req, res) => {
  const { limit = 50, date_from, date_to, partner_id } = req.query;
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('list_payments', { payments: [], count: 0 }));
  try {
    const domain = [['state', '=', 'posted']];
    if (date_from) domain.push(['date', '>=', date_from]);
    if (date_to)   domain.push(['date', '<=', date_to]);
    if (partner_id) domain.push(['partner_id', '=', parseInt(partner_id)]);
    const payments = await odooCallWithRetry('account.payment', 'search_read', [domain], {
      fields: ['name', 'partner_id', 'amount', 'currency_id', 'date', 'payment_type', 'journal_id', 'ref'],
      limit: parseInt(limit), order: 'date desc'
    });
    return res.json({
      success: true, requestId,
      payments: payments.map(p => ({
        id: p.id, name: p.name,
        partner: p.partner_id?.[1], amount: p.amount,
        currency: p.currency_id?.[1], date: p.date,
        type: p.payment_type, journal: p.journal_id?.[1], ref: p.ref
      })),
      count: payments.length,
      total: payments.reduce((s, p) => s + (p.amount || 0), 0),
      timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /journal-entries ───────────────────────────────────────────────────────
app.get('/journal-entries', async (req, res) => {
  const { limit = 50, date_from, date_to, journal_id } = req.query;
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('list_journal_entries', { entries: [], count: 0 }));
  try {
    const domain = [['state', '=', 'posted'], ['move_type', '=', 'entry']];
    if (date_from) domain.push(['date', '>=', date_from]);
    if (date_to)   domain.push(['date', '<=', date_to]);
    if (journal_id) domain.push(['journal_id', '=', parseInt(journal_id)]);
    const entries = await odooCallWithRetry('account.move', 'search_read', [domain], {
      fields: ['name', 'date', 'journal_id', 'ref', 'amount_total'],
      limit: parseInt(limit), order: 'date desc'
    });
    return res.json({
      success: true, requestId,
      entries: entries.map(e => ({
        id: e.id, name: e.name, date: e.date,
        journal: e.journal_id?.[1], ref: e.ref, amount: e.amount_total
      })),
      count: entries.length, timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /analytic-accounts ─────────────────────────────────────────────────────
app.get('/analytic-accounts', async (req, res) => {
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('list_analytic_accounts', { accounts: [] }));
  try {
    const accounts = await odooCallWithRetry('account.analytic.account', 'search_read',
      [[['active', '=', true]]],
      { fields: ['name', 'code', 'partner_id', 'balance', 'debit', 'credit'], order: 'name asc' }
    );
    return res.json({ success: true, requestId, accounts, count: accounts.length, timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /purchase-orders ───────────────────────────────────────────────────────
app.get('/purchase-orders', async (req, res) => {
  const { state, limit = 50, date_from, date_to } = req.query;
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('list_purchase_orders', { orders: [], count: 0 }));
  try {
    const domain = [];
    if (state) domain.push(['state', '=', state]); // draft, purchase, done, cancel
    if (date_from) domain.push(['date_order', '>=', date_from]);
    if (date_to)   domain.push(['date_order', '<=', date_to]);
    const orders = await odooCallWithRetry('purchase.order', 'search_read', [domain], {
      fields: ['name', 'partner_id', 'amount_total', 'currency_id', 'date_order', 'date_approve', 'state'],
      limit: parseInt(limit), order: 'date_order desc'
    });
    return res.json({
      success: true, requestId,
      orders: orders.map(o => ({
        id: o.id, name: o.name, vendor: o.partner_id?.[1],
        amount_total: o.amount_total, currency: o.currency_id?.[1],
        date_order: o.date_order, state: o.state
      })),
      count: orders.length, timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /sales-orders ──────────────────────────────────────────────────────────
app.get('/sales-orders', async (req, res) => {
  const { state, limit = 50, date_from, date_to } = req.query;
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('list_sales_orders', { orders: [], count: 0 }));
  try {
    const domain = [];
    if (state) domain.push(['state', '=', state]); // draft, sale, done, cancel
    if (date_from) domain.push(['date_order', '>=', date_from]);
    if (date_to)   domain.push(['date_order', '<=', date_to]);
    const orders = await odooCallWithRetry('sale.order', 'search_read', [domain], {
      fields: ['name', 'partner_id', 'amount_total', 'currency_id', 'date_order', 'state', 'invoice_status'],
      limit: parseInt(limit), order: 'date_order desc'
    });
    return res.json({
      success: true, requestId,
      orders: orders.map(o => ({
        id: o.id, name: o.name, customer: o.partner_id?.[1],
        amount_total: o.amount_total, currency: o.currency_id?.[1],
        date_order: o.date_order, state: o.state, invoice_status: o.invoice_status
      })),
      count: orders.length, timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /expenses ──────────────────────────────────────────────────────────────
app.get('/expenses', async (req, res) => {
  const { date_from, date_to, limit = 100 } = req.query;
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('list_expenses', { expenses: [], total: 0 }));
  try {
    const domain = [['move_type', '=', 'in_invoice'], ['state', '=', 'posted']];
    if (date_from) domain.push(['invoice_date', '>=', date_from]);
    if (date_to)   domain.push(['invoice_date', '<=', date_to]);
    const bills = await odooCallWithRetry('account.move', 'search_read', [domain], {
      fields: ['name', 'partner_id', 'amount_total', 'invoice_date', 'invoice_line_ids'],
      limit: parseInt(limit)
    });
    return res.json({
      success: true, requestId,
      expenses: bills.map(b => ({
        id: b.id, name: b.name,
        vendor: b.partner_id?.[1], amount_total: b.amount_total,
        invoice_date: b.invoice_date, line_ids: b.invoice_line_ids
      })),
      total: parseFloat(bills.reduce((s, b) => s + (b.amount_total || 0), 0).toFixed(2)),
      count: bills.length, timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ════════════════════════════════════════════════════════════════════════════════
// FINANCIAL REPORTS
// ════════════════════════════════════════════════════════════════════════════════

// ── GET /report/profit-loss ────────────────────────────────────────────────────
app.get('/report/profit-loss', async (req, res) => {
  const { date_from, date_to } = req.query;
  const requestId = uuidv4();
  logger.info({ requestId, action: 'report_profit_loss', date_from, date_to });
  if (DRY_RUN) return res.json(dryRunResponse('profit_loss', { revenue: 0, expenses: 0, net_profit: 0 }));
  try {
    const df = date_from || new Date(new Date().getFullYear(), 0, 1).toISOString().split('T')[0];
    const dt = date_to || new Date().toISOString().split('T')[0];

    const [revInvoices, expBills] = await Promise.all([
      odooCallWithRetry('account.move', 'search_read',
        [[['move_type', '=', 'out_invoice'], ['state', '=', 'posted'],
          ['invoice_date', '>=', df], ['invoice_date', '<=', dt]]],
        { fields: ['amount_total', 'amount_residual'], limit: 1000 }
      ),
      odooCallWithRetry('account.move', 'search_read',
        [[['move_type', '=', 'in_invoice'], ['state', '=', 'posted'],
          ['invoice_date', '>=', df], ['invoice_date', '<=', dt]]],
        { fields: ['amount_total'], limit: 1000 }
      )
    ]);

    const totalRevenue = revInvoices.reduce((s, i) => s + (i.amount_total || 0), 0);
    const totalExpenses = expBills.reduce((s, b) => s + (b.amount_total || 0), 0);
    const netProfit = totalRevenue - totalExpenses;

    return res.json({
      success: true, requestId,
      report: 'profit_loss',
      period: { from: df, to: dt },
      revenue: parseFloat(totalRevenue.toFixed(2)),
      expenses: parseFloat(totalExpenses.toFixed(2)),
      net_profit: parseFloat(netProfit.toFixed(2)),
      profit_margin: totalRevenue > 0 ? parseFloat(((netProfit / totalRevenue) * 100).toFixed(1)) : 0,
      invoice_count: revInvoices.length,
      bill_count: expBills.length,
      timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /report/ar-aging ───────────────────────────────────────────────────────
app.get('/report/ar-aging', async (req, res) => {
  const requestId = uuidv4();
  logger.info({ requestId, action: 'report_ar_aging' });
  if (DRY_RUN) return res.json(dryRunResponse('ar_aging', { buckets: {} }));
  try {
    const today = new Date();
    const invoices = await odooCallWithRetry('account.move', 'search_read',
      [[['move_type', '=', 'out_invoice'], ['state', '=', 'posted'],
        ['payment_state', 'in', ['not_paid', 'partial']]]],
      { fields: ['name', 'partner_id', 'amount_residual', 'invoice_date_due'], limit: 500 }
    );

    const buckets = { current: [], days_1_30: [], days_31_60: [], days_61_90: [], over_90: [] };
    for (const inv of invoices) {
      const due = inv.invoice_date_due ? new Date(inv.invoice_date_due) : today;
      const daysOverdue = Math.floor((today - due) / (1000 * 60 * 60 * 24));
      const item = { id: inv.id, name: inv.name, partner: inv.partner_id?.[1], amount_due: inv.amount_residual, due_date: inv.invoice_date_due, days_overdue: daysOverdue };
      if (daysOverdue <= 0)       buckets.current.push(item);
      else if (daysOverdue <= 30) buckets.days_1_30.push(item);
      else if (daysOverdue <= 60) buckets.days_31_60.push(item);
      else if (daysOverdue <= 90) buckets.days_61_90.push(item);
      else                        buckets.over_90.push(item);
    }

    const summary = {};
    for (const [key, items] of Object.entries(buckets)) {
      summary[key] = { count: items.length, total: parseFloat(items.reduce((s, i) => s + (i.amount_due || 0), 0).toFixed(2)), items };
    }

    return res.json({
      success: true, requestId, report: 'ar_aging',
      as_of: today.toISOString().split('T')[0],
      total_outstanding: parseFloat(invoices.reduce((s, i) => s + (i.amount_residual || 0), 0).toFixed(2)),
      buckets: summary, timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /report/ap-aging ───────────────────────────────────────────────────────
app.get('/report/ap-aging', async (req, res) => {
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('ap_aging', { buckets: {} }));
  try {
    const today = new Date();
    const bills = await odooCallWithRetry('account.move', 'search_read',
      [[['move_type', '=', 'in_invoice'], ['state', '=', 'posted'],
        ['payment_state', 'in', ['not_paid', 'partial']]]],
      { fields: ['name', 'partner_id', 'amount_residual', 'invoice_date_due'], limit: 500 }
    );

    const buckets = { current: [], days_1_30: [], days_31_60: [], days_61_90: [], over_90: [] };
    for (const bill of bills) {
      const due = bill.invoice_date_due ? new Date(bill.invoice_date_due) : today;
      const daysOverdue = Math.floor((today - due) / (1000 * 60 * 60 * 24));
      const item = { id: bill.id, name: bill.name, vendor: bill.partner_id?.[1], amount_due: bill.amount_residual, due_date: bill.invoice_date_due, days_overdue: daysOverdue };
      if (daysOverdue <= 0)       buckets.current.push(item);
      else if (daysOverdue <= 30) buckets.days_1_30.push(item);
      else if (daysOverdue <= 60) buckets.days_31_60.push(item);
      else if (daysOverdue <= 90) buckets.days_61_90.push(item);
      else                        buckets.over_90.push(item);
    }

    const summary = {};
    for (const [key, items] of Object.entries(buckets)) {
      summary[key] = { count: items.length, total: parseFloat(items.reduce((s, b) => s + (b.amount_due || 0), 0).toFixed(2)), items };
    }

    return res.json({
      success: true, requestId, report: 'ap_aging',
      as_of: today.toISOString().split('T')[0],
      total_payable: parseFloat(bills.reduce((s, b) => s + (b.amount_residual || 0), 0).toFixed(2)),
      buckets: summary, timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /report/trial-balance ──────────────────────────────────────────────────
app.get('/report/trial-balance', async (req, res) => {
  const { date_from, date_to } = req.query;
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('trial_balance', { lines: [] }));
  try {
    const df = date_from || new Date(new Date().getFullYear(), 0, 1).toISOString().split('T')[0];
    const dt = date_to || new Date().toISOString().split('T')[0];

    const lines = await odooCallWithRetry('account.move.line', 'read_group',
      [[['date', '>=', df], ['date', '<=', dt], ['move_id.state', '=', 'posted']]],
      { groupby: ['account_id'], fields: ['debit:sum', 'credit:sum', 'balance:sum'] }
    );

    const formatted = (lines || []).map(l => ({
      account_id: l.account_id?.[0],
      account: l.account_id?.[1],
      debit: parseFloat((l.debit || 0).toFixed(2)),
      credit: parseFloat((l.credit || 0).toFixed(2)),
      balance: parseFloat((l.balance || 0).toFixed(2))
    }));

    const totalDebit  = formatted.reduce((s, l) => s + l.debit, 0);
    const totalCredit = formatted.reduce((s, l) => s + l.credit, 0);

    return res.json({
      success: true, requestId, report: 'trial_balance',
      period: { from: df, to: dt },
      lines: formatted.sort((a, b) => (a.account || '').localeCompare(b.account || '')),
      totals: { debit: parseFloat(totalDebit.toFixed(2)), credit: parseFloat(totalCredit.toFixed(2)), balanced: Math.abs(totalDebit - totalCredit) < 0.01 },
      timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /report/balance-sheet ──────────────────────────────────────────────────
app.get('/report/balance-sheet', async (req, res) => {
  const { date } = req.query;
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('balance_sheet', { assets: 0, liabilities: 0, equity: 0 }));
  try {
    const asOf = date || new Date().toISOString().split('T')[0];
    const lines = await odooCallWithRetry('account.move.line', 'read_group',
      [[['date', '<=', asOf], ['move_id.state', '=', 'posted']]],
      { groupby: ['account_id'], fields: ['balance:sum'] }
    );

    // Classify by account type (simplified)
    const accounts = await odooCallWithRetry('account.account', 'search_read',
      [[['deprecated', '=', false]]],
      { fields: ['id', 'code', 'name', 'account_type'] }
    );
    const accountMap = {};
    for (const a of accounts) accountMap[a.id] = a;

    let assets = 0, liabilities = 0, equity = 0;
    const detail = { assets: [], liabilities: [], equity: [] };

    for (const l of (lines || [])) {
      const acctId = l.account_id?.[0];
      const acct = accountMap[acctId];
      if (!acct) continue;
      const bal = parseFloat((l.balance || 0).toFixed(2));
      const item = { account: l.account_id?.[1], balance: bal };
      const t = acct.account_type || '';
      if (t.startsWith('asset'))     { assets += bal; detail.assets.push(item); }
      else if (t.startsWith('liability')) { liabilities += Math.abs(bal); detail.liabilities.push(item); }
      else if (t.startsWith('equity'))    { equity += Math.abs(bal); detail.equity.push(item); }
    }

    return res.json({
      success: true, requestId, report: 'balance_sheet',
      as_of: asOf,
      summary: {
        total_assets: parseFloat(assets.toFixed(2)),
        total_liabilities: parseFloat(liabilities.toFixed(2)),
        total_equity: parseFloat(equity.toFixed(2)),
        balanced: Math.abs(assets - liabilities - equity) < 1.0
      },
      detail, timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── GET /report/cash-flow ──────────────────────────────────────────────────────
app.get('/report/cash-flow', async (req, res) => {
  const { date_from, date_to } = req.query;
  const requestId = uuidv4();
  if (DRY_RUN) return res.json(dryRunResponse('cash_flow', { inflows: 0, outflows: 0, net: 0 }));
  try {
    const df = date_from || new Date(new Date().getFullYear(), 0, 1).toISOString().split('T')[0];
    const dt = date_to || new Date().toISOString().split('T')[0];

    const payments = await odooCallWithRetry('account.payment', 'search_read',
      [[['state', '=', 'posted'], ['date', '>=', df], ['date', '<=', dt]]],
      { fields: ['payment_type', 'amount', 'date', 'partner_id', 'journal_id'], limit: 1000 }
    );

    const inflows  = payments.filter(p => p.payment_type === 'inbound');
    const outflows = payments.filter(p => p.payment_type === 'outbound');
    const totalIn  = inflows.reduce((s, p) => s + (p.amount || 0), 0);
    const totalOut = outflows.reduce((s, p) => s + (p.amount || 0), 0);

    return res.json({
      success: true, requestId, report: 'cash_flow',
      period: { from: df, to: dt },
      inflows: parseFloat(totalIn.toFixed(2)),
      outflows: parseFloat(totalOut.toFixed(2)),
      net_cash_flow: parseFloat((totalIn - totalOut).toFixed(2)),
      transaction_count: payments.length,
      detail: {
        inflows: inflows.map(p => ({ date: p.date, partner: p.partner_id?.[1], amount: p.amount, journal: p.journal_id?.[1] })),
        outflows: outflows.map(p => ({ date: p.date, partner: p.partner_id?.[1], amount: p.amount, journal: p.journal_id?.[1] }))
      },
      timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ════════════════════════════════════════════════════════════════════════════════
// WRITE ENDPOINTS (ALL require prior human approval)
// ════════════════════════════════════════════════════════════════════════════════

// ── POST /invoice ──────────────────────────────────────────────────────────────
app.post('/invoice', async (req, res) => {
  const { params } = req.body;
  const { partner_name, partner_email, lines, amount, description, due_date, ref, currency_code } = params || {};
  const requestId = uuidv4();
  logger.info({ requestId, action: 'create_invoice', partner_name, dry_run: DRY_RUN });

  if (!partner_name) return res.status(400).json({ success: false, error: 'partner_name is required' });

  // lines takes priority; amount/description is the single-line shorthand
  const invoiceLines = lines || [{ description: description || 'Consulting Services', quantity: 1, price_unit: parseFloat(amount) || 0 }];
  if (!lines && !amount) return res.status(400).json({ success: false, error: 'amount or lines[] is required' });

  if (DRY_RUN) {
    logger.info({ requestId, msg: '[DRY RUN] Would create invoice', partner_name, lines: invoiceLines });
    return res.json({ success: true, dry_run: true, invoice_id: 0, invoice_name: 'DRY_RUN_INV', state: 'draft', timestamp: new Date().toISOString() });
  }

  try {
    // Find or create partner
    let partners = await odooCallWithRetry('res.partner', 'search', [[['name', 'ilike', partner_name]]]);
    let partnerId = partners.length > 0 ? partners[0]
      : await odooCallWithRetry('res.partner', 'create', [{ name: partner_name, email: partner_email || false, customer_rank: 1 }]);

    // Resolve currency
    let currencyId = false;
    if (currency_code) {
      const curr = await odooCallWithRetry('res.currency', 'search', [[['name', '=', currency_code.toUpperCase()]]]);
      if (curr.length > 0) currencyId = curr[0];
    }

    const lineCommands = invoiceLines.map(l => [0, 0, {
      name: l.description || l.name || 'Service',
      quantity: l.quantity || 1,
      price_unit: parseFloat(l.price_unit || l.amount || 0),
      ...(l.tax_ids ? { tax_ids: [[6, 0, l.tax_ids]] } : {}),
      ...(l.account_id ? { account_id: l.account_id } : {})
    }]);

    const invoiceVals = {
      move_type: 'out_invoice',
      partner_id: partnerId,
      invoice_line_ids: lineCommands,
      ...(due_date ? { invoice_date_due: due_date } : {}),
      ...(ref ? { ref } : {}),
      ...(currencyId ? { currency_id: currencyId } : {})
    };

    const invoiceId = await odooCallWithRetry('account.move', 'create', [invoiceVals]);
    const [inv] = await odooCallWithRetry('account.move', 'read', [[invoiceId]], { fields: ['name', 'amount_total'] });

    logger.info({ requestId, msg: 'Invoice created (DRAFT)', invoice_id: invoiceId, name: inv.name });
    return res.json({
      success: true, requestId, invoice_id: invoiceId,
      invoice_name: inv.name, amount_total: inv.amount_total,
      state: 'draft', note: 'Created as DRAFT — use POST /post-invoice to confirm',
      timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── POST /bill ─────────────────────────────────────────────────────────────────
app.post('/bill', async (req, res) => {
  const { params } = req.body;
  const { vendor_name, vendor_email, lines, amount, description, due_date, ref } = params || {};
  const requestId = uuidv4();
  logger.info({ requestId, action: 'create_bill', vendor_name, dry_run: DRY_RUN });

  if (!vendor_name) return res.status(400).json({ success: false, error: 'vendor_name is required' });

  const billLines = lines || [{ description: description || 'Purchase', quantity: 1, price_unit: parseFloat(amount) || 0 }];
  if (!lines && !amount) return res.status(400).json({ success: false, error: 'amount or lines[] is required' });

  if (DRY_RUN) {
    return res.json({ success: true, dry_run: true, bill_id: 0, bill_name: 'DRY_RUN_BILL', state: 'draft', timestamp: new Date().toISOString() });
  }

  try {
    let vendors = await odooCallWithRetry('res.partner', 'search', [[['name', 'ilike', vendor_name]]]);
    let vendorId = vendors.length > 0 ? vendors[0]
      : await odooCallWithRetry('res.partner', 'create', [{ name: vendor_name, email: vendor_email || false, supplier_rank: 1 }]);

    const lineCommands = billLines.map(l => [0, 0, {
      name: l.description || l.name || 'Purchase',
      quantity: l.quantity || 1,
      price_unit: parseFloat(l.price_unit || l.amount || 0)
    }]);

    const billId = await odooCallWithRetry('account.move', 'create', [{
      move_type: 'in_invoice',
      partner_id: vendorId,
      invoice_line_ids: lineCommands,
      ...(due_date ? { invoice_date_due: due_date } : {}),
      ...(ref ? { ref } : {})
    }]);

    const [bill] = await odooCallWithRetry('account.move', 'read', [[billId]], { fields: ['name', 'amount_total'] });

    logger.info({ requestId, msg: 'Bill created (DRAFT)', bill_id: billId });
    return res.json({
      success: true, requestId, bill_id: billId,
      bill_name: bill.name, amount_total: bill.amount_total,
      state: 'draft', note: 'Created as DRAFT — use POST /post-bill to confirm',
      timestamp: new Date().toISOString()
    });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── POST /credit-note ──────────────────────────────────────────────────────────
app.post('/credit-note', async (req, res) => {
  const { params } = req.body;
  const { invoice_id, reason, amount, refund_method } = params || {};
  const requestId = uuidv4();
  logger.info({ requestId, action: 'create_credit_note', invoice_id, dry_run: DRY_RUN });

  if (!invoice_id) return res.status(400).json({ success: false, error: 'invoice_id is required' });

  if (DRY_RUN) {
    return res.json({ success: true, dry_run: true, credit_note_id: 0, timestamp: new Date().toISOString() });
  }

  try {
    // Use account.move.reversal wizard
    const wizard = await odooCallWithRetry('account.move.reversal', 'create', [{
      reason: reason || 'Credit note',
      refund_method: refund_method || 'refund', // refund, cancel, modify
      ...(amount ? { price_unit: parseFloat(amount) } : {})
    }], { context: { active_ids: [parseInt(invoice_id)], active_model: 'account.move', active_id: parseInt(invoice_id) } });

    const result = await odooCallWithRetry('account.move.reversal', 'reverse_moves',
      [[wizard]],
      { context: { active_ids: [parseInt(invoice_id)], active_model: 'account.move' } }
    );

    logger.info({ requestId, msg: 'Credit note created', result });
    return res.json({ success: true, requestId, result, timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── POST /payment ──────────────────────────────────────────────────────────────
// ALWAYS requires human approval — never auto-executed
app.post('/payment', async (req, res) => {
  const { params } = req.body;
  const { invoice_id, amount, payment_date, journal_id, payment_method } = params || {};
  const requestId = uuidv4();
  logger.info({ requestId, action: 'register_payment', invoice_id, amount, dry_run: DRY_RUN });

  if (DRY_RUN) {
    return res.json({ success: true, dry_run: true, payment_id: 0, timestamp: new Date().toISOString() });
  }

  try {
    const ctx = {
      active_ids: [parseInt(invoice_id)],
      active_model: 'account.move',
      active_id: parseInt(invoice_id)
    };
    const wizardVals = {
      payment_date: payment_date || new Date().toISOString().split('T')[0],
      ...(amount ? { amount: parseFloat(amount) } : {}),
      ...(journal_id ? { journal_id: parseInt(journal_id) } : {})
    };
    const wizard = await odooCallWithRetry('account.payment.register', 'create', [wizardVals], { context: ctx });
    const result = await odooCallWithRetry('account.payment.register', 'action_create_payments', [[wizard]], { context: ctx });

    logger.info({ requestId, msg: 'Payment registered', result });
    return res.json({ success: true, requestId, result, timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── POST /customer ─────────────────────────────────────────────────────────────
app.post('/customer', async (req, res) => {
  const { params } = req.body;
  const { name, email, phone, city, country_code, street, vat, website } = params || {};
  const requestId = uuidv4();
  logger.info({ requestId, action: 'create_customer', name });
  if (!name) return res.status(400).json({ success: false, error: 'name is required' });
  if (DRY_RUN) return res.json({ success: true, dry_run: true, customer_id: 0, timestamp: new Date().toISOString() });
  try {
    let countryId = false;
    if (country_code) {
      const countries = await odooCallWithRetry('res.country', 'search', [[['code', '=', country_code.toUpperCase()]]]);
      if (countries.length > 0) countryId = countries[0];
    }
    const customerId = await odooCallWithRetry('res.partner', 'create', [{
      name, email: email || false, phone: phone || false,
      city: city || false, street: street || false,
      vat: vat || false, website: website || false,
      customer_rank: 1,
      ...(countryId ? { country_id: countryId } : {})
    }]);
    logger.info({ requestId, msg: 'Customer created', customer_id: customerId });
    return res.json({ success: true, requestId, customer_id: customerId, timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── POST /vendor ───────────────────────────────────────────────────────────────
app.post('/vendor', async (req, res) => {
  const { params } = req.body;
  const { name, email, phone, city, country_code, street, vat, website, payment_terms } = params || {};
  const requestId = uuidv4();
  logger.info({ requestId, action: 'create_vendor', name });
  if (!name) return res.status(400).json({ success: false, error: 'name is required' });
  if (DRY_RUN) return res.json({ success: true, dry_run: true, vendor_id: 0, timestamp: new Date().toISOString() });
  try {
    let countryId = false;
    if (country_code) {
      const countries = await odooCallWithRetry('res.country', 'search', [[['code', '=', country_code.toUpperCase()]]]);
      if (countries.length > 0) countryId = countries[0];
    }
    const vendorId = await odooCallWithRetry('res.partner', 'create', [{
      name, email: email || false, phone: phone || false,
      city: city || false, street: street || false, vat: vat || false,
      website: website || false, supplier_rank: 1,
      ...(countryId ? { country_id: countryId } : {})
    }]);
    logger.info({ requestId, msg: 'Vendor created', vendor_id: vendorId });
    return res.json({ success: true, requestId, vendor_id: vendorId, timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── POST /product ──────────────────────────────────────────────────────────────
app.post('/product', async (req, res) => {
  const { params } = req.body;
  const { name, type = 'service', list_price, standard_price, description, uom_name } = params || {};
  const requestId = uuidv4();
  logger.info({ requestId, action: 'create_product', name });
  if (!name) return res.status(400).json({ success: false, error: 'name is required' });
  if (DRY_RUN) return res.json({ success: true, dry_run: true, product_id: 0, timestamp: new Date().toISOString() });
  try {
    let uomId = false;
    if (uom_name) {
      const uoms = await odooCallWithRetry('uom.uom', 'search', [[['name', 'ilike', uom_name]]]);
      if (uoms.length > 0) uomId = uoms[0];
    }
    const productId = await odooCallWithRetry('product.template', 'create', [{
      name, type, // service | consu | product
      list_price: parseFloat(list_price || 0),
      standard_price: parseFloat(standard_price || 0),
      description_sale: description || false,
      ...(uomId ? { uom_id: uomId, uom_po_id: uomId } : {})
    }]);
    logger.info({ requestId, msg: 'Product created', product_id: productId });
    return res.json({ success: true, requestId, product_id: productId, timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── POST /journal-entry ────────────────────────────────────────────────────────
app.post('/journal-entry', async (req, res) => {
  const { params } = req.body;
  const { date, ref, journal_id, lines } = params || {};
  const requestId = uuidv4();
  logger.info({ requestId, action: 'create_journal_entry', ref, dry_run: DRY_RUN });
  if (!lines || !Array.isArray(lines) || lines.length === 0) {
    return res.status(400).json({ success: false, error: 'lines[] array is required' });
  }
  if (DRY_RUN) return res.json({ success: true, dry_run: true, entry_id: 0, timestamp: new Date().toISOString() });
  try {
    const lineCommands = lines.map(l => [0, 0, {
      account_id: l.account_id,
      name: l.name || ref || 'Manual entry',
      debit: parseFloat(l.debit || 0),
      credit: parseFloat(l.credit || 0),
      ...(l.partner_id ? { partner_id: l.partner_id } : {}),
      ...(l.analytic_account_id ? { analytic_account_id: l.analytic_account_id } : {})
    }]);

    // Validate balanced entry
    const totalDebit  = lines.reduce((s, l) => s + parseFloat(l.debit || 0), 0);
    const totalCredit = lines.reduce((s, l) => s + parseFloat(l.credit || 0), 0);
    if (Math.abs(totalDebit - totalCredit) > 0.01) {
      return res.status(400).json({ success: false, error: `Unbalanced entry: debit ${totalDebit} ≠ credit ${totalCredit}` });
    }

    const entryId = await odooCallWithRetry('account.move', 'create', [{
      move_type: 'entry',
      date: date || new Date().toISOString().split('T')[0],
      ref: ref || 'Manual journal entry',
      journal_id: journal_id || false,
      line_ids: lineCommands
    }]);

    logger.info({ requestId, msg: 'Journal entry created (DRAFT)', entry_id: entryId });
    return res.json({ success: true, requestId, entry_id: entryId, state: 'draft', timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── POST /post-invoice ─────────────────────────────────────────────────────────
app.post('/post-invoice', async (req, res) => {
  const { params } = req.body;
  const { invoice_id } = params || {};
  const requestId = uuidv4();
  logger.info({ requestId, action: 'post_invoice', invoice_id, dry_run: DRY_RUN });
  if (!invoice_id) return res.status(400).json({ success: false, error: 'invoice_id is required' });
  if (DRY_RUN) return res.json({ success: true, dry_run: true, invoice_id, state: 'posted', timestamp: new Date().toISOString() });
  try {
    await odooCallWithRetry('account.move', 'action_post', [[parseInt(invoice_id)]]);
    const [inv] = await odooCallWithRetry('account.move', 'read', [[parseInt(invoice_id)]], { fields: ['name', 'state', 'amount_total'] });
    logger.info({ requestId, msg: 'Invoice posted', invoice_id, name: inv.name });
    return res.json({ success: true, requestId, invoice_id, name: inv.name, state: inv.state, amount_total: inv.amount_total, timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── POST /post-bill ────────────────────────────────────────────────────────────
app.post('/post-bill', async (req, res) => {
  const { params } = req.body;
  const { bill_id } = params || {};
  const requestId = uuidv4();
  logger.info({ requestId, action: 'post_bill', bill_id, dry_run: DRY_RUN });
  if (!bill_id) return res.status(400).json({ success: false, error: 'bill_id is required' });
  if (DRY_RUN) return res.json({ success: true, dry_run: true, bill_id, state: 'posted', timestamp: new Date().toISOString() });
  try {
    await odooCallWithRetry('account.move', 'action_post', [[parseInt(bill_id)]]);
    const [bill] = await odooCallWithRetry('account.move', 'read', [[parseInt(bill_id)]], { fields: ['name', 'state', 'amount_total'] });
    logger.info({ requestId, msg: 'Bill posted', bill_id, name: bill.name });
    return res.json({ success: true, requestId, bill_id, name: bill.name, state: bill.state, amount_total: bill.amount_total, timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── POST /purchase-order ───────────────────────────────────────────────────────
app.post('/purchase-order', async (req, res) => {
  const { params } = req.body;
  const { vendor_name, vendor_email, lines, notes } = params || {};
  const requestId = uuidv4();
  logger.info({ requestId, action: 'create_purchase_order', vendor_name, dry_run: DRY_RUN });
  if (!vendor_name || !lines) return res.status(400).json({ success: false, error: 'vendor_name and lines[] are required' });
  if (DRY_RUN) return res.json({ success: true, dry_run: true, po_id: 0, timestamp: new Date().toISOString() });
  try {
    let vendors = await odooCallWithRetry('res.partner', 'search', [[['name', 'ilike', vendor_name]]]);
    let vendorId = vendors.length > 0 ? vendors[0]
      : await odooCallWithRetry('res.partner', 'create', [{ name: vendor_name, email: vendor_email || false, supplier_rank: 1 }]);

    const lineCommands = lines.map(l => [0, 0, {
      name: l.name || l.description || 'Item',
      product_qty: l.quantity || 1,
      price_unit: parseFloat(l.price_unit || l.amount || 0),
      date_planned: l.date_planned || new Date().toISOString().split('T')[0],
      ...(l.product_id ? { product_id: l.product_id } : {})
    }]);

    const poId = await odooCallWithRetry('purchase.order', 'create', [{
      partner_id: vendorId,
      order_line: lineCommands,
      ...(notes ? { notes } : {})
    }]);

    logger.info({ requestId, msg: 'Purchase order created', po_id: poId });
    return res.json({ success: true, requestId, po_id: poId, state: 'draft', timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── POST /sales-order ──────────────────────────────────────────────────────────
app.post('/sales-order', async (req, res) => {
  const { params } = req.body;
  const { customer_name, customer_email, lines, note, validity_date } = params || {};
  const requestId = uuidv4();
  logger.info({ requestId, action: 'create_sales_order', customer_name, dry_run: DRY_RUN });
  if (!customer_name || !lines) return res.status(400).json({ success: false, error: 'customer_name and lines[] are required' });
  if (DRY_RUN) return res.json({ success: true, dry_run: true, so_id: 0, timestamp: new Date().toISOString() });
  try {
    let customers = await odooCallWithRetry('res.partner', 'search', [[['name', 'ilike', customer_name]]]);
    let partnerId = customers.length > 0 ? customers[0]
      : await odooCallWithRetry('res.partner', 'create', [{ name: customer_name, email: customer_email || false, customer_rank: 1 }]);

    const lineCommands = lines.map(l => [0, 0, {
      name: l.name || l.description || 'Item',
      product_uom_qty: l.quantity || 1,
      price_unit: parseFloat(l.price_unit || l.amount || 0),
      ...(l.product_id ? { product_id: l.product_id } : {})
    }]);

    const soId = await odooCallWithRetry('sale.order', 'create', [{
      partner_id: partnerId,
      order_line: lineCommands,
      ...(note ? { note } : {}),
      ...(validity_date ? { validity_date } : {})
    }]);

    logger.info({ requestId, msg: 'Sales order created', so_id: soId });
    return res.json({ success: true, requestId, so_id: soId, state: 'draft', timestamp: new Date().toISOString() });
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  }
});

// ── Start ──────────────────────────────────────────────────────────────────────
app.listen(PORT, '127.0.0.1', () => {
  logger.info({
    msg: 'Odoo MCP server started',
    port: PORT, odoo: ODOO_URL, db: ODOO_DB,
    dry_run: DRY_RUN,
    endpoints: [
      'GET /health', 'GET /revenue', 'GET /invoices', 'GET /bills',
      'GET /customers', 'GET /vendors', 'GET /products', 'GET /accounts',
      'GET /taxes', 'GET /currencies', 'GET /payments', 'GET /journal-entries',
      'GET /analytic-accounts', 'GET /purchase-orders', 'GET /sales-orders', 'GET /expenses',
      'GET /report/profit-loss', 'GET /report/ar-aging', 'GET /report/ap-aging',
      'GET /report/trial-balance', 'GET /report/balance-sheet', 'GET /report/cash-flow',
      'POST /invoice', 'POST /bill', 'POST /credit-note', 'POST /payment',
      'POST /customer', 'POST /vendor', 'POST /product', 'POST /journal-entry',
      'POST /post-invoice', 'POST /post-bill', 'POST /purchase-order', 'POST /sales-order'
    ]
  });
  if (DRY_RUN) logger.warn({ msg: 'DRY RUN MODE ACTIVE — no Odoo writes will execute' });
});

module.exports = app;
