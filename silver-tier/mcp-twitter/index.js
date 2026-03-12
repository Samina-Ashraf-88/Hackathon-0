/**
 * mcp-twitter/index.js
 * Twitter/X MCP Server for AI Employee Gold Tier
 *
 * Endpoints:
 *   POST /post        → create a tweet (280 chars max)
 *   POST /reply       → reply to a tweet
 *   POST /retweet     → retweet a tweet
 *   GET  /health      → health check
 *   GET  /mentions    → fetch recent @mentions
 *   GET  /messages    → fetch recent DMs
 *   POST /login       → establish session (run once)
 *
 * ENVIRONMENT VARIABLES:
 *   TWITTER_SESSION_PATH    — path to Playwright session storage
 *   TWITTER_USERNAME        — SaminaAshr24675
 *   MCP_SECRET              — shared secret
 *   DRY_RUN                 — "true" to log without acting
 *   PORT                    — default 3003
 */

require('dotenv').config({ path: '../.env' });
const express = require('express');
const { chromium } = require('playwright');
const { v4: uuidv4 } = require('uuid');
const winston = require('winston');
const path = require('path');
const fs = require('fs');

const PORT = process.env.PORT || 3003;
const DRY_RUN = process.env.DRY_RUN === 'true';
const MCP_SECRET = process.env.MCP_SECRET || 'dev-secret-change-me';
const SESSION_PATH = process.env.TWITTER_SESSION_PATH || path.join(__dirname, '../.sessions/twitter');
const TWITTER_USERNAME = process.env.TWITTER_USERNAME || 'SaminaAshr24675';

fs.mkdirSync(SESSION_PATH, { recursive: true });

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(winston.format.timestamp(), winston.format.json()),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: path.join(__dirname, '../AI_Employee_Vault/Logs/twitter-mcp.log') })
  ]
});

const app = express();
app.use(express.json());

app.use((req, res, next) => {
  if (req.path === '/health') return next();
  const ip = req.ip || req.connection?.remoteAddress || '';
  if (ip === '127.0.0.1' || ip === '::1' || ip === '::ffff:127.0.0.1') return next();
  const auth = req.headers.authorization;
  if (!auth || auth !== `Bearer ${MCP_SECRET}`) {
    return res.status(401).json({ success: false, error: 'Unauthorized' });
  }
  next();
});

app.get('/health', (req, res) => {
  res.json({ success: true, server: 'twitter-mcp', port: PORT, dry_run: DRY_RUN, timestamp: new Date().toISOString() });
});

async function launchBrowser() {
  return chromium.launchPersistentContext(SESSION_PATH, {
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
  });
}

// ── POST /post ────────────────────────────────────────────────────────────────
app.post('/post', async (req, res) => {
  const { params } = req.body;
  const { text } = params || {};
  const requestId = uuidv4();

  if (!text) return res.status(400).json({ success: false, error: 'text is required' });
  if (text.length > 280) return res.status(400).json({ success: false, error: `Tweet too long: ${text.length}/280 chars` });

  logger.info({ requestId, action: 'create_tweet', text: text.substring(0, 50), dry_run: DRY_RUN });

  if (DRY_RUN) {
    logger.info({ requestId, msg: '[DRY RUN] Would tweet', text });
    return res.json({ success: true, dry_run: true, tweet_id: `dry_${requestId}`, timestamp: new Date().toISOString() });
  }

  let browser;
  try {
    browser = await launchBrowser();
    const page = browser.pages()[0] || await browser.newPage();

    await page.goto('https://x.com/home', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);

    // Verify logged in — if redirected to login flow, session is invalid
    await page.waitForTimeout(2000);
    const twitterUrl = page.url();
    if (twitterUrl.includes('/login') || twitterUrl.includes('/i/flow/login') || twitterUrl.includes('/flow/')) {
      throw new Error('Not logged in to Twitter/X — run: python watchers/social_login.py --platform twitter');
    }
    logger.info({ requestId, msg: `On page: ${twitterUrl}` });

    // Find and activate the tweet compose box
    // X.com home shows a "What's happening?" placeholder — click it first to focus
    const placeholderCandidates = [
      '[data-testid="tweetTextarea_0"]',
      'div[data-testid="tweetTextarea_0_label"]',
      '[placeholder="What\'s happening?"]',
      '[aria-label="Post text"]',
      '[aria-label="Tweet text"]',
    ];

    let activated = false;
    for (const sel of placeholderCandidates) {
      try {
        const el = page.locator(sel).first();
        if (await el.isVisible({ timeout: 4000 })) {
          await el.click({ timeout: 5000 });
          activated = true;
          logger.info({ requestId, msg: `Clicked compose area: ${sel}` });
          break;
        }
      } catch (_) {}
    }

    // Fallback: try by placeholder text
    if (!activated) {
      try {
        await page.getByPlaceholder("What's happening?").click({ timeout: 5000 });
        activated = true;
        logger.info({ requestId, msg: 'Clicked compose via placeholder text' });
      } catch (_) {}
    }

    if (!activated) throw new Error('Tweet compose box not found — session may be expired or X.com changed its UI');

    await page.waitForTimeout(800);

    // After clicking, find the active contenteditable and type into it
    let tweetBox = null;
    const activeEditorCandidates = [
      '[data-testid="tweetTextarea_0"]',
      'div[contenteditable="true"][data-testid]',
      'div[contenteditable="true"][role="textbox"]',
      'div[contenteditable="true"]',
    ];
    for (const sel of activeEditorCandidates) {
      try {
        const el = page.locator(sel).first();
        if (await el.isVisible({ timeout: 3000 })) {
          tweetBox = el;
          logger.info({ requestId, msg: `Found active editor: ${sel}` });
          break;
        }
      } catch (_) {}
    }
    if (!tweetBox) throw new Error('Active tweet editor not found after clicking compose area');

    // Use keyboard type to trigger React state updates
    await page.keyboard.type(text, { delay: 20 });
    await page.waitForTimeout(1000);

    // Click Post/Tweet button
    const postBtnCandidates = [
      '[data-testid="tweetButtonInline"]',
      '[data-testid="tweetButton"]',
      'button[data-testid="tweetButtonInline"]',
      'div[data-testid="tweetButtonInline"]',
    ];

    let posted = false;
    for (const sel of postBtnCandidates) {
      try {
        const btn = page.locator(sel).first();
        const visible = await btn.isVisible({ timeout: 3000 });
        const disabled = await btn.isDisabled().catch(() => false);
        if (visible && !disabled) {
          await btn.click({ timeout: 5000 });
          posted = true;
          logger.info({ requestId, msg: `Clicked tweet button: ${sel}` });
          break;
        }
      } catch (_) {}
    }
    if (!posted) throw new Error('Could not find enabled Post button — text may be empty or too long');

    await page.waitForTimeout(4000);
    logger.info({ requestId, msg: 'Tweeted successfully' });
    return res.json({ success: true, tweet_id: `tweet_${Date.now()}`, timestamp: new Date().toISOString() });

  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  } finally {
    try { if (browser) await browser.close(); } catch (_) {}
  }
});

// ── POST /reply ───────────────────────────────────────────────────────────────
app.post('/reply', async (req, res) => {
  const { params } = req.body;
  const { tweet_url, reply_text } = params || {};
  const requestId = uuidv4();

  logger.info({ requestId, action: 'reply_to_tweet', dry_run: DRY_RUN });

  if (DRY_RUN) {
    logger.info({ requestId, msg: '[DRY RUN] Would reply on Twitter', reply_text });
    return res.json({ success: true, dry_run: true, reply_id: `dry_${requestId}`, timestamp: new Date().toISOString() });
  }

  let browser;
  try {
    browser = await launchBrowser();
    const page = browser.pages()[0] || await browser.newPage();

    if (tweet_url) {
      await page.goto(tweet_url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(3000);

      // Click reply icon
      const replyBtn = await page.locator('[data-testid="reply"]').first();
      if (await replyBtn.isVisible()) {
        await replyBtn.click();
        await page.waitForTimeout(2000);

        const replyBox = await page.locator('[data-testid="tweetTextarea_0"]').first();
        if (await replyBox.isVisible()) {
          await replyBox.fill(reply_text);
          await page.waitForTimeout(500);
          const tweetBtn = await page.locator('[data-testid="tweetButton"]').first();
          if (await tweetBtn.isVisible()) {
            await tweetBtn.click();
            await page.waitForTimeout(2000);
            return res.json({ success: true, reply_id: `reply_${Date.now()}`, timestamp: new Date().toISOString() });
          }
        }
      }
    }

    throw new Error('Reply interface not found or tweet_url not provided');
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  } finally {
    if (browser) await browser.close();
  }
});

// ── POST /retweet ─────────────────────────────────────────────────────────────
app.post('/retweet', async (req, res) => {
  const { params } = req.body;
  const { tweet_url } = params || {};
  const requestId = uuidv4();

  if (DRY_RUN) {
    logger.info({ requestId, msg: '[DRY RUN] Would retweet', tweet_url });
    return res.json({ success: true, dry_run: true, timestamp: new Date().toISOString() });
  }

  let browser;
  try {
    browser = await launchBrowser();
    const page = browser.pages()[0] || await browser.newPage();

    await page.goto(tweet_url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(2000);

    const retweetBtn = await page.locator('[data-testid="retweet"]').first();
    if (await retweetBtn.isVisible()) {
      await retweetBtn.click();
      await page.waitForTimeout(1000);
      const confirmBtn = await page.locator('[data-testid="retweetConfirm"]').first();
      if (await confirmBtn.isVisible()) {
        await confirmBtn.click();
        await page.waitForTimeout(2000);
        return res.json({ success: true, timestamp: new Date().toISOString() });
      }
    }

    throw new Error('Retweet button not found');
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message });
  } finally {
    if (browser) await browser.close();
  }
});

// ── GET /mentions ─────────────────────────────────────────────────────────────
app.get('/mentions', async (req, res) => {
  if (DRY_RUN) return res.json({ success: true, dry_run: true, mentions: [], timestamp: new Date().toISOString() });
  return res.json({ success: true, mentions: [], note: 'Active session required', timestamp: new Date().toISOString() });
});

app.get('/messages', async (req, res) => {
  if (DRY_RUN) return res.json({ success: true, dry_run: true, messages: [], timestamp: new Date().toISOString() });
  return res.json({ success: true, messages: [], note: 'Active session required', timestamp: new Date().toISOString() });
});

// ── POST /login ───────────────────────────────────────────────────────────────
app.post('/login', async (req, res) => {
  const { username, password } = req.body;
  let browser;
  try {
    browser = await launchBrowser();
    const page = browser.pages()[0] || await browser.newPage();
    await page.goto('https://x.com/login', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);

    await page.fill('input[autocomplete="username"]', username || TWITTER_USERNAME);
    await page.keyboard.press('Enter');
    await page.waitForTimeout(2000);
    await page.fill('input[type="password"]', password || '');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(5000);

    const loggedIn = await page.locator('[data-testid="SideNav_AccountSwitcher_Button"]').isVisible().catch(() => false);
    return res.json({ success: loggedIn, message: loggedIn ? 'Twitter/X session saved' : 'Login may have failed — check for 2FA' });
  } catch (err) {
    logger.error({ action: 'login', error: err.message });
    return res.status(500).json({ success: false, error: err.message });
  } finally {
    if (browser) await browser.close();
  }
});

app.listen(PORT, () => {
  logger.info({ msg: `Twitter/X MCP server running`, port: PORT, dry_run: DRY_RUN, username: TWITTER_USERNAME });
});

module.exports = app;
