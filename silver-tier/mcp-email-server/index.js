/**
 * AI Employee — MCP Email Server
 *
 * A local HTTP server that exposes Gmail send/draft actions for Claude Code.
 * Listens on localhost:3000. Only accessible from localhost (privacy-first).
 *
 * Endpoints:
 *   GET  /health              — Check server status
 *   POST /send-email          — Send an email via Gmail
 *   POST /draft-email         — Save a draft without sending
 *   GET  /list-drafts         — List saved drafts
 *
 * Authentication:
 *   Uses OAuth2 token saved at ../token.json by the Python watcher setup.
 *   Run `python watchers/gmail_watcher.py --auth` first to generate token.json.
 *
 * Usage:
 *   npm install
 *   node index.js
 *
 * Environment variables (via .env):
 *   PORT=3000
 *   TOKEN_PATH=../token.json
 *   CREDENTIALS_PATH=../credentials.json
 *   DRY_RUN=true|false
 */

import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import { google } from 'googleapis';
import { readFileSync, existsSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..');

const PORT = parseInt(process.env.PORT || '3000', 10);
const TOKEN_PATH = process.env.TOKEN_PATH || join(PROJECT_ROOT, 'token.json');
const CREDENTIALS_PATH = process.env.CREDENTIALS_PATH || join(PROJECT_ROOT, 'credentials.json');
const DRY_RUN = process.env.DRY_RUN?.toLowerCase() !== 'false';
const SENDER_EMAIL = 'apple379tree@gmail.com';

// ─── OAuth2 Setup ────────────────────────────────────────────────────────────

function loadCredentials() {
  if (!existsSync(CREDENTIALS_PATH)) {
    throw new Error(
      `credentials.json not found at ${CREDENTIALS_PATH}. ` +
      'Download from Google Cloud Console and run: python watchers/gmail_watcher.py --auth'
    );
  }
  const raw = JSON.parse(readFileSync(CREDENTIALS_PATH, 'utf8'));
  const creds = raw.installed || raw.web;
  return creds;
}

function loadToken() {
  if (!existsSync(TOKEN_PATH)) {
    throw new Error(
      `token.json not found at ${TOKEN_PATH}. ` +
      'Run: python watchers/gmail_watcher.py --auth'
    );
  }
  return JSON.parse(readFileSync(TOKEN_PATH, 'utf8'));
}

function saveToken(tokenData) {
  writeFileSync(TOKEN_PATH, JSON.stringify(tokenData, null, 2));
}

function getAuthClient() {
  const creds = loadCredentials();
  const token = loadToken();

  const oauth2Client = new google.auth.OAuth2(
    creds.client_id,
    creds.client_secret,
    creds.redirect_uris?.[0] || 'http://localhost'
  );

  oauth2Client.setCredentials(token);

  // Auto-save refreshed tokens
  oauth2Client.on('tokens', (newTokens) => {
    const current = loadToken();
    const merged = { ...current, ...newTokens };
    saveToken(merged);
    console.log('[Auth] Token refreshed and saved.');
  });

  return oauth2Client;
}

// ─── Email Utilities ─────────────────────────────────────────────────────────

/**
 * Encode an email to base64url format for Gmail API.
 */
function encodeEmail({ to, subject, body, from = SENDER_EMAIL, cc = '', replyToId = '' }) {
  const headers = [
    `From: ${from}`,
    `To: ${to}`,
    ...(cc ? [`Cc: ${cc}`] : []),
    `Subject: ${subject}`,
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: quoted-printable',
    ...(replyToId ? [`In-Reply-To: ${replyToId}`, `References: ${replyToId}`] : []),
  ].join('\r\n');

  const email = `${headers}\r\n\r\n${body}`;
  return Buffer.from(email).toString('base64url');
}

function validateEmailPayload(body) {
  const errors = [];
  if (!body.to || typeof body.to !== 'string') errors.push('Missing or invalid "to" field');
  if (!body.subject || typeof body.subject !== 'string') errors.push('Missing "subject" field');
  if (!body.body || typeof body.body !== 'string') errors.push('Missing "body" field');

  // Basic email format check
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (body.to && !emailRegex.test(body.to)) {
    errors.push(`Invalid email address format: "${body.to}"`);
  }

  return errors;
}

// ─── Express App ─────────────────────────────────────────────────────────────

const app = express();

// Only allow localhost connections (privacy/security)
app.use((req, res, next) => {
  const ip = req.socket.remoteAddress;
  if (ip !== '127.0.0.1' && ip !== '::1' && ip !== '::ffff:127.0.0.1') {
    console.warn(`[Security] Blocked request from non-localhost: ${ip}`);
    return res.status(403).json({ error: 'Access denied: localhost only' });
  }
  next();
});

app.use(cors({ origin: /localhost/ }));
app.use(express.json({ limit: '1mb' }));

// ─── Request Logging ─────────────────────────────────────────────────────────

app.use((req, res, next) => {
  const ts = new Date().toISOString();
  console.log(`[${ts}] ${req.method} ${req.path}`);
  next();
});

// ─── Routes ──────────────────────────────────────────────────────────────────

/**
 * GET /health
 * Returns server status, Gmail connection status, and dry-run mode.
 */
app.get('/health', async (req, res) => {
  let gmailStatus = 'unknown';

  try {
    const auth = getAuthClient();
    const gmail = google.gmail({ version: 'v1', auth });
    await gmail.users.getProfile({ userId: 'me' });
    gmailStatus = 'connected';
  } catch (err) {
    gmailStatus = `error: ${err.message}`;
  }

  res.json({
    status: 'ok',
    server: 'ai-employee-email-mcp',
    version: '1.0.0',
    dryRun: DRY_RUN,
    gmail: gmailStatus,
    sender: SENDER_EMAIL,
    timestamp: new Date().toISOString(),
  });
});

/**
 * POST /send-email
 * Body: { to, subject, body, from?, cc?, replyToId? }
 * Sends an email via Gmail API.
 */
app.post('/send-email', async (req, res) => {
  const validationErrors = validateEmailPayload(req.body);
  if (validationErrors.length > 0) {
    return res.status(400).json({
      success: false,
      error: 'Validation failed',
      details: validationErrors,
    });
  }

  const { to, subject, body, from, cc, replyToId } = req.body;

  if (DRY_RUN) {
    console.log(`[DRY RUN] Would send email:\n  To: ${to}\n  Subject: ${subject}`);
    return res.json({
      success: true,
      dryRun: true,
      message: 'Dry run mode: email not actually sent',
      preview: { to, subject, bodyPreview: body.substring(0, 100) },
    });
  }

  try {
    const auth = getAuthClient();
    const gmail = google.gmail({ version: 'v1', auth });

    const encodedMessage = encodeEmail({ to, subject, body, from: from || SENDER_EMAIL, cc, replyToId });

    const response = await gmail.users.messages.send({
      userId: 'me',
      requestBody: { raw: encodedMessage },
    });

    console.log(`[Send] Email sent to ${to}. MessageId: ${response.data.id}`);

    res.json({
      success: true,
      messageId: response.data.id,
      to,
      subject,
      timestamp: new Date().toISOString(),
    });

  } catch (err) {
    console.error(`[Send] Failed to send email: ${err.message}`);
    res.status(500).json({
      success: false,
      error: 'Failed to send email',
      details: err.message,
    });
  }
});

/**
 * POST /draft-email
 * Body: { to, subject, body, from?, cc? }
 * Saves as Gmail draft without sending.
 */
app.post('/draft-email', async (req, res) => {
  const validationErrors = validateEmailPayload(req.body);
  if (validationErrors.length > 0) {
    return res.status(400).json({
      success: false,
      error: 'Validation failed',
      details: validationErrors,
    });
  }

  const { to, subject, body, from, cc } = req.body;

  if (DRY_RUN) {
    console.log(`[DRY RUN] Would save draft:\n  To: ${to}\n  Subject: ${subject}`);
    return res.json({
      success: true,
      dryRun: true,
      message: 'Dry run mode: draft not actually saved',
    });
  }

  try {
    const auth = getAuthClient();
    const gmail = google.gmail({ version: 'v1', auth });

    const encodedMessage = encodeEmail({ to, subject, body, from: from || SENDER_EMAIL, cc });

    const response = await gmail.users.drafts.create({
      userId: 'me',
      requestBody: {
        message: { raw: encodedMessage },
      },
    });

    console.log(`[Draft] Draft saved. DraftId: ${response.data.id}`);

    res.json({
      success: true,
      draftId: response.data.id,
      to,
      subject,
      timestamp: new Date().toISOString(),
    });

  } catch (err) {
    console.error(`[Draft] Failed to save draft: ${err.message}`);
    res.status(500).json({
      success: false,
      error: 'Failed to save draft',
      details: err.message,
    });
  }
});

/**
 * GET /list-drafts
 * Returns the 10 most recent Gmail drafts.
 */
app.get('/list-drafts', async (req, res) => {
  try {
    const auth = getAuthClient();
    const gmail = google.gmail({ version: 'v1', auth });

    const response = await gmail.users.drafts.list({
      userId: 'me',
      maxResults: 10,
    });

    const drafts = response.data.drafts || [];
    res.json({ success: true, count: drafts.length, drafts });

  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// ─── 404 Handler ─────────────────────────────────────────────────────────────

app.use((req, res) => {
  res.status(404).json({
    error: 'Not found',
    availableEndpoints: [
      'GET  /health',
      'POST /send-email',
      'POST /draft-email',
      'GET  /list-drafts',
    ],
  });
});

// ─── Global Error Handler ────────────────────────────────────────────────────

app.use((err, req, res, next) => {
  console.error(`[Error] ${err.message}`);
  res.status(500).json({ success: false, error: 'Internal server error' });
});

// ─── Start Server ─────────────────────────────────────────────────────────────

app.listen(PORT, '127.0.0.1', () => {
  console.log('╔══════════════════════════════════════════╗');
  console.log('║   AI Employee — MCP Email Server v1.0   ║');
  console.log('╠══════════════════════════════════════════╣');
  console.log(`║  Listening: http://127.0.0.1:${PORT}        ║`);
  console.log(`║  Sender:    ${SENDER_EMAIL}  ║`);
  console.log(`║  Dry Run:   ${DRY_RUN ? 'ENABLED (no real sends)' : 'DISABLED          '}  ║`);
  console.log('╚══════════════════════════════════════════╝');

  if (DRY_RUN) {
    console.log('\n⚠️  DRY RUN MODE: Set DRY_RUN=false in .env to enable real sends.\n');
  }

  // Verify Gmail connection on startup
  try {
    const auth = getAuthClient();
    const gmail = google.gmail({ version: 'v1', auth });
    gmail.users.getProfile({ userId: 'me' }).then(profile => {
      console.log(`✅ Gmail connected: ${profile.data.emailAddress}`);
    }).catch(err => {
      console.warn(`⚠️  Gmail not connected: ${err.message}`);
      console.warn('   Run: python watchers/gmail_watcher.py --auth');
    });
  } catch (err) {
    console.warn(`⚠️  Could not load credentials: ${err.message}`);
  }
});

export default app;
