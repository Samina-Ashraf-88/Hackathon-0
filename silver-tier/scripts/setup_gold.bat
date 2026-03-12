@echo off
REM =============================================================================
REM setup_gold.bat — Gold Tier Setup Script for Windows
REM
REM Runs all one-time setup steps for the Gold Tier AI Employee:
REM   1. Install Python dependencies
REM   2. Install Node.js dependencies for all MCP servers
REM   3. Install Playwright browsers
REM   4. Start Odoo via Docker
REM   5. Run Odoo initial setup
REM   6. Register Windows Task Scheduler job for weekly audit
REM   7. Health check all systems
REM
REM Prerequisites:
REM   - Python 3.13+  (python --version)
REM   - Node.js v24+  (node --version)
REM   - Docker Desktop running
REM   - .env file configured (copy from .env.gold.example)
REM =============================================================================

setlocal enabledelayedexpansion

echo.
echo =====================================================
echo   AI Employee Gold Tier — Setup Script (Windows)
echo =====================================================
echo.

set ROOT=%~dp0..
cd /d "%ROOT%"

REM ── Load .env ────────────────────────────────────────────────────────────────
if not exist .env (
    echo ERROR: .env file not found!
    echo Copy .env.gold.example to .env and fill in your credentials.
    pause
    exit /b 1
)

REM ── Step 1: Python Dependencies ───────────────────────────────────────────────
echo [1/7] Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. Check Python version and requirements.txt
    pause
    exit /b 1
)
echo      OK

REM ── Step 2: Node.js MCP Servers ───────────────────────────────────────────────
echo [2/7] Installing Node.js dependencies for MCP servers...

for %%D in (mcp-email-server mcp-facebook mcp-instagram mcp-twitter mcp-odoo) do (
    echo   Installing %%D...
    cd "%ROOT%\%%D"
    call npm install --silent
    if errorlevel 1 (
        echo   WARNING: npm install failed for %%D
    )
    cd "%ROOT%"
)
echo      OK

REM ── Step 3: Playwright Browsers ───────────────────────────────────────────────
echo [3/7] Installing Playwright browsers (Chromium)...
cd "%ROOT%\mcp-facebook"
call npx playwright install chromium --with-deps
cd "%ROOT%"
echo      OK

REM ── Step 4: Odoo Docker Setup ─────────────────────────────────────────────────
echo [4/7] Starting Odoo via Docker...
if exist docker-compose.odoo.yml (
    docker compose -f docker-compose.odoo.yml up -d
    echo   Waiting 30 seconds for Odoo to initialize...
    timeout /t 30 /nobreak >nul
    echo      Docker: OK
) else (
    echo   WARNING: docker-compose.odoo.yml not found. Skipping Odoo.
)

REM ── Step 5: Odoo Initial Data Setup ──────────────────────────────────────────
echo [5/7] Running Odoo initial setup...
python scripts\setup_odoo.py
echo      OK

REM ── Step 6: Windows Task Scheduler (Weekly CEO Briefing) ─────────────────────
echo [6/7] Registering weekly CEO briefing task...
schtasks /create /tn "AI_Employee_Weekly_CEO_Briefing" ^
  /tr "python \"%ROOT%\scripts\weekly_audit.py\"" ^
  /sc weekly /d SUN /st 22:00 ^
  /f /rl HIGHEST >nul 2>&1
if errorlevel 1 (
    echo   WARNING: Could not create Task Scheduler job. Create manually:
    echo   Action: python "%ROOT%\scripts\weekly_audit.py"
    echo   Trigger: Weekly, Sunday, 10:00 PM
) else (
    echo      Task Scheduler: AI_Employee_Weekly_CEO_Briefing registered
)

REM ── Step 7: Health Check ─────────────────────────────────────────────────────
echo [7/7] Running health checks...

python -c "import requests; r=requests.get('http://localhost:3000/health',timeout=3); print('  email-mcp:', r.status_code)" 2>nul || echo   email-mcp: not running ^(start manually^)
python -c "import requests; r=requests.get('http://localhost:3001/health',timeout=3); print('  facebook-mcp:', r.status_code)" 2>nul || echo   facebook-mcp: not running ^(start with PM2^)
python -c "import requests; r=requests.get('http://localhost:3002/health',timeout=3); print('  instagram-mcp:', r.status_code)" 2>nul || echo   instagram-mcp: not running
python -c "import requests; r=requests.get('http://localhost:3003/health',timeout=3); print('  twitter-mcp:', r.status_code)" 2>nul || echo   twitter-mcp: not running
python -c "import requests; r=requests.get('http://localhost:3004/health',timeout=3); print('  odoo-mcp:', r.status_code)" 2>nul || echo   odoo-mcp: not running

echo.
echo =====================================================
echo   Gold Tier Setup Complete!
echo.
echo   Next steps:
echo   1. Start all MCP servers: pm2 start ecosystem.gold.config.js
echo   2. Login to social media:
echo      POST http://localhost:3001/login (Facebook)
echo      POST http://localhost:3002/login (Instagram)
echo      POST http://localhost:3003/login (Twitter)
echo   3. Start Gmail OAuth: python watchers/gmail_watcher.py --auth
echo   4. Set DRY_RUN=false in .env when ready for live operation
echo   5. Start watchdog: python watchers/watchdog.py
echo =====================================================
echo.
pause
