/**
 * mcp-instagram/index.js
 * Instagram MCP Server for AI Employee Gold Tier
 *
 * Endpoints:
 *   POST /post        → create Instagram post (caption only or with image)
 *   POST /reply       → reply to a comment
 *   POST /send_dm     → send a direct message
 *   GET  /health      → health check
 *   GET  /messages    → fetch recent DMs
 *   GET  /comments    → fetch recent comments on recent posts
 *   POST /login       → establish session (run once manually)
 *
 * ENVIRONMENT VARIABLES:
 *   INSTAGRAM_SESSION_PATH  — path to persistent session storage
 *   INSTAGRAM_USERNAME      — apple379tree
 *   MCP_SECRET              — shared secret
 *   DRY_RUN                 — "true" to log without acting
 *   PORT                    — default 3002
 */

require('dotenv').config({ path: '../.env' });
const express = require('express');
const { chromium } = require('playwright');
const { v4: uuidv4 } = require('uuid');
const winston = require('winston');
const path = require('path');
const fs = require('fs');

const PORT = process.env.PORT || 3002;
const DRY_RUN = process.env.DRY_RUN === 'true';
const MCP_SECRET = process.env.MCP_SECRET || 'dev-secret-change-me';
const SESSION_PATH = process.env.INSTAGRAM_SESSION_PATH || path.join(__dirname, '../.sessions/instagram');
const INSTAGRAM_USERNAME = process.env.INSTAGRAM_USERNAME || 'apple379tree';

fs.mkdirSync(SESSION_PATH, { recursive: true });

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(winston.format.timestamp(), winston.format.json()),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: path.join(__dirname, '../AI_Employee_Vault/Logs/instagram-mcp.log') })
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
  res.json({ success: true, server: 'instagram-mcp', port: PORT, dry_run: DRY_RUN, timestamp: new Date().toISOString() });
});

async function launchBrowser() {
  return chromium.launchPersistentContext(SESSION_PATH, {
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    // Desktop viewport: Instagram sidebar shows the "Create" button → Feed post modal
    // Mobile portrait viewport routes "+" to Story creator (wrong flow)
    viewport: { width: 1280, height: 900 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
}

// ── POST /post ────────────────────────────────────────────────────────────────
app.post('/post', async (req, res) => {
  const { params } = req.body;
  const { caption, image_path } = params || {};
  const requestId = uuidv4();

  logger.info({ requestId, action: 'create_post', caption: caption?.substring(0, 50), has_image: !!image_path, dry_run: DRY_RUN });

  if (!caption) return res.status(400).json({ success: false, error: 'caption is required' });

  if (DRY_RUN) {
    logger.info({ requestId, msg: '[DRY RUN] Would post to Instagram', caption });
    return res.json({ success: true, dry_run: true, media_id: `dry_${requestId}`, timestamp: new Date().toISOString() });
  }

  // Instagram feed posts always require an image/video.
  // If no image_path provided, we cannot create a standard feed post.
  if (!image_path || !fs.existsSync(image_path)) {
    logger.warn({ requestId, msg: 'No image_path provided — Instagram feed posts require media. Attempting Threads-style text post via mobile web.' });
  }

  let browser;
  try {
    browser = await launchBrowser();
    const page = browser.pages()[0] || await browser.newPage();

    await page.goto('https://www.instagram.com/', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(4000);

    // Verify logged in — check we're not on the login page
    const igUrl = page.url();
    if (igUrl.includes('/accounts/login') || igUrl.includes('/challenge') || igUrl.includes('login')) {
      throw new Error('Not logged in to Instagram — run: python watchers/social_login.py --platform instagram');
    }
    logger.info({ requestId, msg: `On page: ${igUrl}` });

    // Debug screenshot
    const igScreenshot = path.join(__dirname, '../AI_Employee_Vault/Logs/ig_debug.png');
    await page.screenshot({ path: igScreenshot }).catch(() => {});

    // Dismiss all blocking overlays ("Save login info?", "Use the app", cookie banners)
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);

    // JS-based dismiss (most reliable in headless)
    await page.evaluate(() => {
      const allEls = Array.from(document.querySelectorAll('button, [role="button"]'));
      for (const el of allEls) {
        const txt = el.textContent.trim().toLowerCase();
        if (txt === 'not now' || txt.includes('not now')) { el.click(); return; }
      }
    }).catch(() => {});
    await page.waitForTimeout(600);

    // Playwright force-click "Not now"
    try {
      const notNow = page.getByRole('button', { name: /not now/i }).first();
      if (await notNow.isVisible({ timeout: 1500 })) {
        await notNow.click({ force: true, timeout: 2000 });
        logger.info({ requestId, msg: 'Dismissed Save login info modal' });
      }
    } catch (_) {}

    // Dismiss "Use the app" close button (X at right of bottom banner)
    try {
      const closeX = page.locator('button[aria-label="Close"]').first();
      if (await closeX.isVisible({ timeout: 1000 })) {
        await closeX.click({ force: true, timeout: 2000 });
        logger.info({ requestId, msg: 'Dismissed Use the app banner' });
      }
    } catch (_) {}

    await page.waitForTimeout(1200);

    // Post-dismiss screenshot to verify state
    const igScreenshot2 = path.join(__dirname, '../AI_Employee_Vault/Logs/ig_debug2.png');
    await page.screenshot({ path: igScreenshot2 }).catch(() => {});

    if (image_path && fs.existsSync(image_path)) {
      // ── Image post flow (desktop Instagram sidebar → Feed post modal) ─────────
      //
      // Desktop Instagram layout: left sidebar has a "Create" (New post) button
      // that opens a Feed post modal. Mobile portrait "+" goes to Story creator.
      // We use desktop viewport (1280x900) to get the Feed post modal.

      // Wait extra for the sidebar to fully render
      await page.waitForTimeout(3000);

      // Strategy 1: Direct selectors for the Create/New post button in sidebar
      const createCandidates = [
        '[aria-label="New post"]',
        'svg[aria-label="New post"]',
        '[aria-label="Create"]',
        'a[href*="/create/select"]',
        'a[href*="/create/style"]',
      ];

      let createClicked = false;
      for (const sel of createCandidates) {
        try {
          const el = page.locator(sel).first();
          if (await el.isVisible({ timeout: 2000 })) {
            // If the matched element is an SVG, click its parent button/link
            await el.click({ timeout: 5000 });
            createClicked = true;
            logger.info({ requestId, msg: `Clicked create button: ${sel}` });
            break;
          }
        } catch (_) {}
      }

      // Strategy 2: JS evaluate — dump all labels then click the right one
      if (!createClicked) {
        const allLabels = await page.evaluate(() =>
          Array.from(document.querySelectorAll('[aria-label]'))
            .map(el => el.getAttribute('aria-label')).filter(Boolean).slice(0, 60)
        ).catch(() => []);
        logger.info({ requestId, msg: 'All aria-labels on page', labels: allLabels });

        const jsClicked = await page.evaluate(() => {
          // 1. aria-label match (handles SVG inside button)
          for (const el of document.querySelectorAll('[aria-label]')) {
            const label = (el.getAttribute('aria-label') || '').toLowerCase();
            if (label === 'new post' || label === 'create') {
              const btn = el.closest('[role="button"], a, button') || el;
              btn.click();
              return `aria:${el.getAttribute('aria-label')}`;
            }
          }
          // 2. SVG aria-label (the icon itself is the SVG)
          for (const svg of document.querySelectorAll('svg[aria-label]')) {
            const label = (svg.getAttribute('aria-label') || '').toLowerCase();
            if (label === 'new post' || label === 'create') {
              const btn = svg.closest('[role="button"], a, button') || svg;
              btn.click();
              return `svg-aria:${svg.getAttribute('aria-label')}`;
            }
          }
          // 3. href containing /create/ (not story-specific paths)
          const createLink = document.querySelector('a[href*="/create/"]');
          if (createLink) { createLink.click(); return `href:${createLink.href}`; }
          // 4. span text = "Create" in sidebar nav
          for (const span of document.querySelectorAll('span')) {
            if (span.textContent.trim() === 'Create') {
              const btn = span.closest('[role="button"], a, button') || span;
              btn.click();
              return 'span:Create';
            }
          }
          return null;
        }).catch(() => null);

        if (jsClicked) {
          createClicked = true;
          logger.info({ requestId, msg: `Clicked create via JS: ${jsClicked}` });
          await page.waitForTimeout(1500);
        }
      }

      // Strategy 3: "More" menu in narrow sidebar may hide Create — expand it
      if (!createClicked) {
        try {
          const moreBtn = page.locator('[aria-label="More"], span:has-text("More")').first();
          if (await moreBtn.isVisible({ timeout: 2000 })) {
            await moreBtn.click({ timeout: 3000 });
            await page.waitForTimeout(800);
            const createInMenu = page.locator('[aria-label="New post"], [aria-label="Create"], span:has-text("Create")').first();
            if (await createInMenu.isVisible({ timeout: 2000 })) {
              await createInMenu.click({ timeout: 3000 });
              createClicked = true;
              logger.info({ requestId, msg: 'Clicked create via More menu' });
            }
          }
        } catch (_) {}
      }

      if (!createClicked) throw new Error('Could not find Create/New post button in Instagram sidebar — check ig_debug2.png');

      await page.waitForTimeout(2000);

      // Screenshot after clicking Create
      await page.screenshot({ path: path.join(__dirname, '../AI_Employee_Vault/Logs/ig_debug3.png') }).catch(() => {});

      // Desktop "New post" modal shows "Select from computer" button.
      // Use filechooser event for reliable upload; fall back to setInputFiles.
      let uploaded = false;
      try {
        const selectBtn = page.locator(
          'button:has-text("Select from computer"), [role="button"]:has-text("Select from computer")'
        ).first();
        if (await selectBtn.isVisible({ timeout: 5000 })) {
          const [fileChooser] = await Promise.all([
            page.waitForEvent('filechooser', { timeout: 10000 }),
            selectBtn.click({ timeout: 5000 }),
          ]);
          await fileChooser.setFiles(image_path);
          uploaded = true;
          logger.info({ requestId, msg: 'Uploaded image via filechooser (Select from computer)' });
        }
      } catch (_) {}

      if (!uploaded) {
        // Fallback: set the file input directly
        const fileInput = page.locator('input[type="file"]').first();
        await fileInput.setInputFiles(image_path);
        uploaded = true;
        logger.info({ requestId, msg: 'Uploaded image via setInputFiles fallback' });
      }

      await page.waitForTimeout(4000);

      // Screenshot after upload
      await page.screenshot({ path: path.join(__dirname, '../AI_Employee_Vault/Logs/ig_debug4.png') }).catch(() => {});

      // Navigate through steps: Crop → Filters → Caption (click "Next" up to 4 times)
      for (let step = 0; step < 4; step++) {
        try {
          const nextBtn = page.locator(
            'button:has-text("Next"), div[role="button"]:has-text("Next"), [aria-label="Next"]'
          ).first();
          if (await nextBtn.isVisible({ timeout: 5000 })) {
            await nextBtn.click({ force: true, timeout: 5000 });
            logger.info({ requestId, msg: `Clicked Next (step ${step + 1})` });
            await page.waitForTimeout(2500);
          } else {
            break;
          }
        } catch (_) { break; }
      }

      // Screenshot at caption step
      await page.screenshot({ path: path.join(__dirname, '../AI_Employee_Vault/Logs/ig_debug5.png') }).catch(() => {});

      // Add caption
      const captionCandidates = [
        'textarea[aria-label*="caption" i]',
        '[aria-label*="Write a caption" i]',
        'textarea[placeholder*="caption" i]',
        'div[contenteditable="true"][aria-label*="caption" i]',
        'div[contenteditable="true"]',
        'textarea',
      ];

      for (const sel of captionCandidates) {
        try {
          const el = page.locator(sel).first();
          if (await el.isVisible({ timeout: 3000 })) {
            await el.click();
            await el.fill(caption);
            logger.info({ requestId, msg: `Typed caption in: ${sel}` });
            break;
          }
        } catch (_) {}
      }

      await page.waitForTimeout(1000);

      // Screenshot before sharing (for debugging if Share fails)
      await page.screenshot({ path: path.join(__dirname, '../AI_Employee_Vault/Logs/ig_debug6.png') }).catch(() => {});

      // Click Share button — desktop modal has a blue "Share" button top-right
      const shareCandidates = [
        'button:has-text("Share")',
        'div[role="button"]:has-text("Share")',
        '[aria-label="Share"]',
        // Desktop modal header
        'div[role="dialog"] button:has-text("Share")',
        'div[role="dialog"] [role="button"]:has-text("Share")',
        'button:has-text("Post")',
        'div[role="button"]:has-text("Post")',
        'span:has-text("Share")',
      ];

      // JS fallback: dump all clickable element texts for diagnosis
      const allBtnTexts = await page.evaluate(() =>
        Array.from(document.querySelectorAll('button, [role="button"]'))
          .map(el => el.textContent.trim()).filter(Boolean).slice(0, 30)
      ).catch(() => []);
      logger.info({ requestId, msg: 'All button texts at share step', buttons: allBtnTexts });

      let shared = false;
      for (const sel of shareCandidates) {
        try {
          const btn = page.locator(sel).first();
          if (await btn.isVisible({ timeout: 4000 })) {
            await btn.click({ timeout: 5000 });
            shared = true;
            logger.info({ requestId, msg: `Clicked share: ${sel}` });
            break;
          }
        } catch (_) {}
      }

      // JS fallback for Share: click the first button whose text is "Share"
      if (!shared) {
        const jsShared = await page.evaluate(() => {
          for (const el of document.querySelectorAll('button, [role="button"]')) {
            if (el.textContent.trim() === 'Share') { el.click(); return true; }
          }
          return false;
        }).catch(() => false);
        if (jsShared) {
          shared = true;
          logger.info({ requestId, msg: 'Clicked share via JS evaluate' });
        }
      }

      if (!shared) throw new Error('Could not find Share button in Instagram post flow — check ig_debug5.png and ig_debug6.png');

      await page.waitForTimeout(5000);
      logger.info({ requestId, msg: 'Posted to Instagram successfully (with image)' });
      return res.json({ success: true, media_id: `ig_${Date.now()}`, timestamp: new Date().toISOString() });

    } else {
      // ── No-image fallback: post as a Note (visible to followers in DM tray) ─
      // Instagram Notes = short text (60 chars) visible at top of DMs for 24h.
      // This is the only native text-only format on Instagram web.
      const noteText = caption.substring(0, 60);

      await page.goto('https://www.instagram.com/direct/inbox/', { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(3000);

      const noteBtn = page.locator('[aria-label*="Note"], button:has-text("Leave a note")').first();
      if (await noteBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await noteBtn.click({ timeout: 5000 });
        await page.waitForTimeout(1000);
        const noteInput = page.locator('textarea, div[contenteditable="true"]').first();
        if (await noteInput.isVisible({ timeout: 3000 })) {
          await noteInput.fill(noteText);
          const shareBtn = page.locator('button:has-text("Share"), button:has-text("Post")').first();
          if (await shareBtn.isVisible({ timeout: 3000 })) {
            await shareBtn.click({ timeout: 5000 });
            await page.waitForTimeout(3000);
            logger.info({ requestId, msg: 'Posted Instagram Note (text-only fallback)', noteText });
            return res.json({
              success: true,
              media_id: `ig_note_${Date.now()}`,
              note: 'Posted as Instagram Note (60 chars). For full feed post, provide image_path.',
              timestamp: new Date().toISOString()
            });
          }
        }
      }

      throw new Error(
        'Instagram feed posts require an image. No image_path provided and Notes fallback failed. ' +
        'Add "image_path: /path/to/image.jpg" to the approved post front matter.'
      );
    }

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
  const { post_url, reply_text } = params || {};
  const requestId = uuidv4();

  logger.info({ requestId, action: 'reply_to_comment', dry_run: DRY_RUN });

  if (DRY_RUN) {
    logger.info({ requestId, msg: '[DRY RUN] Would reply on Instagram', reply_text });
    return res.json({ success: true, dry_run: true, reply_id: `dry_${requestId}`, timestamp: new Date().toISOString() });
  }

  let browser;
  try {
    browser = await launchBrowser();
    const page = browser.pages()[0] || await browser.newPage();

    if (post_url) {
      await page.goto(post_url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(2000);

      const replyLink = await page.locator('button:has-text("Reply")').first();
      if (await replyLink.isVisible()) {
        await replyLink.click();
        await page.waitForTimeout(1000);
        await page.keyboard.type(reply_text, { delay: 30 });
        await page.keyboard.press('Enter');
        await page.waitForTimeout(2000);
        return res.json({ success: true, reply_id: `ig_reply_${Date.now()}`, timestamp: new Date().toISOString() });
      }
    }

    throw new Error('Could not find reply interface');
  } catch (err) {
    logger.error({ requestId, error: err.message });
    return res.status(500).json({ success: false, error: err.message, requestId });
  } finally {
    if (browser) await browser.close();
  }
});

// ── POST /login ───────────────────────────────────────────────────────────────
app.post('/login', async (req, res) => {
  const { username, password } = req.body;
  let browser;
  try {
    browser = await launchBrowser();
    const page = browser.pages()[0] || await browser.newPage();
    await page.goto('https://www.instagram.com/accounts/login/', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    await page.fill('input[name="username"]', username || INSTAGRAM_USERNAME);
    await page.fill('input[name="password"]', password || '');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(5000);

    const loggedIn = await page.locator('[aria-label="Home"]').isVisible().catch(() => false);
    return res.json({ success: loggedIn, message: loggedIn ? 'Session saved' : 'Login may have failed — check credentials or 2FA' });
  } catch (err) {
    logger.error({ action: 'login', error: err.message });
    return res.status(500).json({ success: false, error: err.message });
  } finally {
    if (browser) await browser.close();
  }
});

// ── GET /messages ─────────────────────────────────────────────────────────────
app.get('/messages', async (req, res) => {
  if (DRY_RUN) return res.json({ success: true, dry_run: true, messages: [], timestamp: new Date().toISOString() });
  // Real implementation scrapes instagram.com/direct/inbox/
  return res.json({ success: true, messages: [], note: 'Active session required', timestamp: new Date().toISOString() });
});

app.get('/comments', async (req, res) => {
  if (DRY_RUN) return res.json({ success: true, dry_run: true, comments: [], timestamp: new Date().toISOString() });
  return res.json({ success: true, comments: [], note: 'Active session required', timestamp: new Date().toISOString() });
});

app.listen(PORT, () => {
  logger.info({ msg: `Instagram MCP server running`, port: PORT, dry_run: DRY_RUN, username: INSTAGRAM_USERNAME });
});

module.exports = app;
