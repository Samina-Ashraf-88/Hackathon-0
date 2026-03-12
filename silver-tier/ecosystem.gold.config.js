/**
 * ecosystem.gold.config.js — PM2 Gold Tier Ecosystem Config
 *
 * Manages all AI Employee processes:
 *   - 5 MCP servers (Node.js)
 *   - 5 Python watchers
 *   - 1 Python watchdog
 *
 * Usage:
 *   pm2 start ecosystem.gold.config.js       # Start all processes
 *   pm2 stop ecosystem.gold.config.js        # Stop all
 *   pm2 restart ecosystem.gold.config.js     # Restart all
 *   pm2 status                               # View all processes
 *   pm2 logs                                 # View all logs
 *   pm2 logs facebook-mcp                    # View specific logs
 *   pm2 save                                 # Persist process list
 *   pm2 startup                              # Auto-start on boot
 *
 * Prerequisites:
 *   npm install -g pm2
 *   pm2 install pm2-logrotate
 */

const path = require('path');
const ROOT = __dirname;
const VAULT = path.join(ROOT, 'AI_Employee_Vault');

// Load .env manually for PM2 (PM2 doesn't auto-load .env)
require('dotenv').config({ path: path.join(ROOT, '.env') });

module.exports = {
  apps: [

    // ══════════════════════════════════════════════════════════
    //  MCP SERVERS (Node.js)
    // ══════════════════════════════════════════════════════════

    {
      name: 'email-mcp',
      script: 'index.js',
      cwd: path.join(ROOT, 'mcp-email-server'),
      interpreter: 'node',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      restart_delay: 5000,
      env: {
        PORT: 3000,
        NODE_ENV: 'production',
        DRY_RUN: process.env.DRY_RUN || 'true',
        MCP_SECRET: process.env.MCP_SECRET || 'dev-secret-change-me',
        VAULT_PATH: VAULT,
      },
      log_file: path.join(VAULT, 'Logs', 'pm2-email-mcp.log'),
      error_file: path.join(VAULT, 'Logs', 'pm2-email-mcp-err.log'),
      merge_logs: true,
      time: true,
    },

    {
      name: 'facebook-mcp',
      script: 'index.js',
      cwd: path.join(ROOT, 'mcp-facebook'),
      interpreter: 'node',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      restart_delay: 10000,
      env: {
        PORT: 3001,
        NODE_ENV: 'production',
        DRY_RUN: process.env.DRY_RUN || 'true',
        MCP_SECRET: process.env.MCP_SECRET || 'dev-secret-change-me',
        FACEBOOK_SESSION_PATH: path.join(ROOT, '.sessions', 'facebook'),
        FACEBOOK_PAGE_ID: process.env.FACEBOOK_PAGE_ID || '61586406776621',
        FACEBOOK_PROFILE_URL: 'https://www.facebook.com/profile.php?id=61586406776621',
        VAULT_PATH: VAULT,
      },
      log_file: path.join(VAULT, 'Logs', 'pm2-facebook-mcp.log'),
      error_file: path.join(VAULT, 'Logs', 'pm2-facebook-mcp-err.log'),
      merge_logs: true,
      time: true,
    },

    {
      name: 'instagram-mcp',
      script: 'index.js',
      cwd: path.join(ROOT, 'mcp-instagram'),
      interpreter: 'node',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      restart_delay: 10000,
      env: {
        PORT: 3002,
        NODE_ENV: 'production',
        DRY_RUN: process.env.DRY_RUN || 'true',
        MCP_SECRET: process.env.MCP_SECRET || 'dev-secret-change-me',
        INSTAGRAM_SESSION_PATH: path.join(ROOT, '.sessions', 'instagram'),
        INSTAGRAM_USERNAME: 'apple379tree',
        VAULT_PATH: VAULT,
      },
      log_file: path.join(VAULT, 'Logs', 'pm2-instagram-mcp.log'),
      error_file: path.join(VAULT, 'Logs', 'pm2-instagram-mcp-err.log'),
      merge_logs: true,
      time: true,
    },

    {
      name: 'twitter-mcp',
      script: 'index.js',
      cwd: path.join(ROOT, 'mcp-twitter'),
      interpreter: 'node',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      restart_delay: 10000,
      env: {
        PORT: 3003,
        NODE_ENV: 'production',
        DRY_RUN: process.env.DRY_RUN || 'true',
        MCP_SECRET: process.env.MCP_SECRET || 'dev-secret-change-me',
        TWITTER_SESSION_PATH: path.join(ROOT, '.sessions', 'twitter'),
        TWITTER_USERNAME: 'SaminaAshr24675',
        VAULT_PATH: VAULT,
      },
      log_file: path.join(VAULT, 'Logs', 'pm2-twitter-mcp.log'),
      error_file: path.join(VAULT, 'Logs', 'pm2-twitter-mcp-err.log'),
      merge_logs: true,
      time: true,
    },

    {
      name: 'odoo-mcp',
      script: 'index.js',
      cwd: path.join(ROOT, 'mcp-odoo'),
      interpreter: 'node',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      restart_delay: 5000,
      env: {
        PORT: 3004,
        NODE_ENV: 'production',
        DRY_RUN: process.env.DRY_RUN || 'true',
        MCP_SECRET: process.env.MCP_SECRET || 'dev-secret-change-me',
        ODOO_URL: process.env.ODOO_URL || 'http://localhost:8069',
        ODOO_DB: process.env.ODOO_DB || 'ai_employee_db',
        ODOO_USERNAME: process.env.ODOO_USERNAME || 'admin',
        ODOO_PASSWORD: process.env.ODOO_PASSWORD || '',
        VAULT_PATH: VAULT,
      },
      log_file: path.join(VAULT, 'Logs', 'pm2-odoo-mcp.log'),
      error_file: path.join(VAULT, 'Logs', 'pm2-odoo-mcp-err.log'),
      merge_logs: true,
      time: true,
    },

    // ══════════════════════════════════════════════════════════
    //  PYTHON WATCHERS
    // ══════════════════════════════════════════════════════════

    {
      name: 'gmail-watcher',
      script: 'gmail_watcher.py',
      cwd: path.join(ROOT, 'watchers'),
      interpreter: 'python',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      restart_delay: 15000,
      env: {
        VAULT_PATH: VAULT,
        CREDENTIALS_PATH: path.join(ROOT, 'credentials.json'),
        TOKEN_PATH: path.join(ROOT, 'token.json'),
        DRY_RUN: process.env.DRY_RUN || 'true',
        MCP_SECRET: process.env.MCP_SECRET || 'dev-secret-change-me',
        GMAIL_CHECK_INTERVAL: '120',
      },
      log_file: path.join(VAULT, 'Logs', 'pm2-gmail-watcher.log'),
      error_file: path.join(VAULT, 'Logs', 'pm2-gmail-watcher-err.log'),
      merge_logs: true,
      time: true,
    },

    {
      name: 'linkedin-watcher',
      script: 'linkedin_watcher.py',
      cwd: path.join(ROOT, 'watchers'),
      interpreter: 'python',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      restart_delay: 30000,
      env: {
        VAULT_PATH: VAULT,
        LINKEDIN_SESSION_PATH: path.join(ROOT, '.sessions', 'linkedin'),
        DRY_RUN: process.env.DRY_RUN || 'true',
        MCP_SECRET: process.env.MCP_SECRET || 'dev-secret-change-me',
        LINKEDIN_CHECK_INTERVAL: '300',
      },
      log_file: path.join(VAULT, 'Logs', 'pm2-linkedin-watcher.log'),
      error_file: path.join(VAULT, 'Logs', 'pm2-linkedin-watcher-err.log'),
      merge_logs: true,
      time: true,
    },

    {
      name: 'facebook-watcher',
      script: 'facebook_watcher.py',
      cwd: path.join(ROOT, 'watchers'),
      interpreter: 'python',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      restart_delay: 20000,
      env: {
        VAULT_PATH: VAULT,
        FACEBOOK_MCP_URL: 'http://localhost:3001',
        DRY_RUN: process.env.DRY_RUN || 'true',
        MCP_SECRET: process.env.MCP_SECRET || 'dev-secret-change-me',
        FACEBOOK_CHECK_INTERVAL: '300',
      },
      log_file: path.join(VAULT, 'Logs', 'pm2-facebook-watcher.log'),
      error_file: path.join(VAULT, 'Logs', 'pm2-facebook-watcher-err.log'),
      merge_logs: true,
      time: true,
    },

    {
      name: 'instagram-watcher',
      script: 'instagram_watcher.py',
      cwd: path.join(ROOT, 'watchers'),
      interpreter: 'python',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      restart_delay: 20000,
      env: {
        VAULT_PATH: VAULT,
        INSTAGRAM_MCP_URL: 'http://localhost:3002',
        DRY_RUN: process.env.DRY_RUN || 'true',
        MCP_SECRET: process.env.MCP_SECRET || 'dev-secret-change-me',
        INSTAGRAM_CHECK_INTERVAL: '300',
      },
      log_file: path.join(VAULT, 'Logs', 'pm2-instagram-watcher.log'),
      error_file: path.join(VAULT, 'Logs', 'pm2-instagram-watcher-err.log'),
      merge_logs: true,
      time: true,
    },

    {
      name: 'twitter-watcher',
      script: 'twitter_watcher.py',
      cwd: path.join(ROOT, 'watchers'),
      interpreter: 'python',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      restart_delay: 20000,
      env: {
        VAULT_PATH: VAULT,
        TWITTER_MCP_URL: 'http://localhost:3003',
        DRY_RUN: process.env.DRY_RUN || 'true',
        MCP_SECRET: process.env.MCP_SECRET || 'dev-secret-change-me',
        TWITTER_CHECK_INTERVAL: '300',
      },
      log_file: path.join(VAULT, 'Logs', 'pm2-twitter-watcher.log'),
      error_file: path.join(VAULT, 'Logs', 'pm2-twitter-watcher-err.log'),
      merge_logs: true,
      time: true,
    },

    // ── Odoo Accounting Watcher ────────────────────────────────
    {
      name: 'odoo-watcher',
      script: 'odoo_watcher.py',
      cwd: path.join(ROOT, 'watchers'),
      interpreter: 'python',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '128M',
      restart_delay: 15000,
      env: {
        VAULT_PATH: VAULT,
        ODOO_MCP_URL: 'http://localhost:3004',
        DRY_RUN: process.env.DRY_RUN || 'true',
        MCP_SECRET: process.env.MCP_SECRET || 'dev-secret-change-me',
        ODOO_CHECK_INTERVAL: '3600',  // Check every 1 hour
        ODOO_URL: process.env.ODOO_URL || 'http://localhost:8069',
      },
      log_file: path.join(VAULT, 'Logs', 'pm2-odoo-watcher.log'),
      error_file: path.join(VAULT, 'Logs', 'pm2-odoo-watcher-err.log'),
      merge_logs: true,
      time: true,
    },

    // ══════════════════════════════════════════════════════════
    //  WATCHDOG
    // ══════════════════════════════════════════════════════════

    {
      name: 'watchdog',
      script: 'watchdog.py',
      cwd: path.join(ROOT, 'watchers'),
      interpreter: 'python',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '128M',
      restart_delay: 30000,
      env: {
        VAULT_PATH: VAULT,
        DRY_RUN: process.env.DRY_RUN || 'true',
        WATCHDOG_CHECK_INTERVAL: '60',
        WATCHDOG_MAX_RESTARTS: '5',
      },
      log_file: path.join(VAULT, 'Logs', 'pm2-watchdog.log'),
      error_file: path.join(VAULT, 'Logs', 'pm2-watchdog-err.log'),
      merge_logs: true,
      time: true,
    },

  ] // end apps
};
