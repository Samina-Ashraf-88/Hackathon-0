"""
watchdog.py — Gold Tier Process Watchdog

Monitors all AI Employee processes (watchers + MCP servers + orchestrator)
and automatically restarts them if they crash. Sends alert emails on persistent
failures. Creates system error files in /Needs_Action/ for Claude to process.

Run:
  python watchdog.py

Monitors:
  - orchestrator.py
  - gmail_watcher.py
  - linkedin_watcher.py
  - facebook_watcher.py
  - instagram_watcher.py
  - twitter_watcher.py
  - All MCP servers (health checks via HTTP)

Environment:
  VAULT_PATH      — path to AI_Employee_Vault
  CHECK_INTERVAL  — seconds between health checks (default 60)
  DRY_RUN         — "true" to log without restarting
"""

import os
import sys
import json
import time
import subprocess
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional

# ── Configuration ──────────────────────────────────────────────────────────────
VAULT_PATH = Path(os.getenv("VAULT_PATH", str(Path(__file__).parent.parent / "AI_Employee_Vault")))
PROJECT_ROOT = Path(__file__).parent.parent
CHECK_INTERVAL = int(os.getenv("WATCHDOG_CHECK_INTERVAL", "60"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
MAX_RESTART_ATTEMPTS = int(os.getenv("WATCHDOG_MAX_RESTARTS", "5"))
RESTART_WINDOW = 3600  # 1 hour — max restarts per window

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Watchdog] %(levelname)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(VAULT_PATH / "Logs" / "watchdog.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("Watchdog")

# ── Process Registry ───────────────────────────────────────────────────────────
PYTHON = sys.executable

PYTHON_PROCESSES = {
    "orchestrator": {
        "cmd": [PYTHON, str(PROJECT_ROOT / "watchers" / "orchestrator.py")],
        "cwd": str(PROJECT_ROOT),
        "pid_file": PROJECT_ROOT / ".pids" / "orchestrator.pid",
        "critical": True,
    },
    "gmail_watcher": {
        "cmd": [PYTHON, str(PROJECT_ROOT / "watchers" / "gmail_watcher.py")],
        "cwd": str(PROJECT_ROOT / "watchers"),
        "pid_file": PROJECT_ROOT / ".pids" / "gmail_watcher.pid",
        "critical": False,
    },
    "linkedin_watcher": {
        "cmd": [PYTHON, str(PROJECT_ROOT / "watchers" / "linkedin_watcher.py")],
        "cwd": str(PROJECT_ROOT / "watchers"),
        "pid_file": PROJECT_ROOT / ".pids" / "linkedin_watcher.pid",
        "critical": False,
    },
    "facebook_watcher": {
        "cmd": [PYTHON, str(PROJECT_ROOT / "watchers" / "facebook_watcher.py")],
        "cwd": str(PROJECT_ROOT / "watchers"),
        "pid_file": PROJECT_ROOT / ".pids" / "facebook_watcher.pid",
        "critical": False,
    },
    "instagram_watcher": {
        "cmd": [PYTHON, str(PROJECT_ROOT / "watchers" / "instagram_watcher.py")],
        "cwd": str(PROJECT_ROOT / "watchers"),
        "pid_file": PROJECT_ROOT / ".pids" / "instagram_watcher.pid",
        "critical": False,
    },
    "twitter_watcher": {
        "cmd": [PYTHON, str(PROJECT_ROOT / "watchers" / "twitter_watcher.py")],
        "cwd": str(PROJECT_ROOT / "watchers"),
        "pid_file": PROJECT_ROOT / ".pids" / "twitter_watcher.pid",
        "critical": False,
    },
}

MCP_SERVERS = {
    "email-mcp":     {"port": 3000, "dir": "mcp-email-server",  "cmd": ["node", "index.js"]},
    "facebook-mcp":  {"port": 3001, "dir": "mcp-facebook",       "cmd": ["node", "index.js"]},
    "instagram-mcp": {"port": 3002, "dir": "mcp-instagram",      "cmd": ["node", "index.js"]},
    "twitter-mcp":   {"port": 3003, "dir": "mcp-twitter",        "cmd": ["node", "index.js"]},
    "odoo-mcp":      {"port": 3004, "dir": "mcp-odoo",           "cmd": ["node", "index.js"]},
}

# ── State Tracking ─────────────────────────────────────────────────────────────
restart_counts: dict[str, list] = {name: [] for name in list(PYTHON_PROCESSES) + list(MCP_SERVERS)}
process_handles: dict[str, Optional[subprocess.Popen]] = {}


def is_pid_running(pid: int) -> bool:
    """Check if a PID is alive (cross-platform)."""
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True
            )
            return str(pid) in result.stdout
        else:
            import signal
            os.kill(pid, 0)
            return True
    except (ProcessLookupError, PermissionError, FileNotFoundError):
        return False


def read_pid(pid_file: Path) -> Optional[int]:
    """Read PID from file."""
    try:
        if pid_file.exists():
            return int(pid_file.read_text().strip())
    except Exception:
        pass
    return None


def write_pid(pid_file: Path, pid: int) -> None:
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid))


def check_mcp_health(name: str, port: int) -> bool:
    """HTTP health check on MCP server."""
    try:
        resp = requests.get(f"http://localhost:{port}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def restart_count_ok(name: str) -> bool:
    """True if we haven't exceeded MAX_RESTART_ATTEMPTS in the last RESTART_WINDOW seconds."""
    now = time.time()
    # Prune old entries
    restart_counts[name] = [t for t in restart_counts[name] if now - t < RESTART_WINDOW]
    return len(restart_counts[name]) < MAX_RESTART_ATTEMPTS


def record_restart(name: str) -> None:
    restart_counts[name].append(time.time())


def create_alert_file(component: str, message: str, restart_count: int) -> None:
    """Create an alert file in /Needs_Action/ for Claude to process."""
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"SYSTEM_ERROR_{component.upper()}_{date_str}.md"
    filepath = VAULT_PATH / "Needs_Action" / filename

    content = f"""---
type: system_error
component: "{component}"
error_category: "system"
failure_count: {restart_count}
timestamp: "{datetime.now().isoformat()}"
status: pending
priority: high
auto_alert: true
---

## Watchdog Alert — {component}

**Component:** {component}
**Message:** {message}
**Restarts in last hour:** {restart_count}

## Required Action
Execute SKILL_Error_Recovery_Graceful_Degradation for component: {component}

## What Watchdog Did
- Detected process not running
- Attempted restart ({restart_count} times in last hour)
{"- MAX RESTARTS REACHED — manual intervention required" if restart_count >= MAX_RESTART_ATTEMPTS else "- Process restarted successfully"}

## Human Action Required
{"Manual restart needed: check logs in AI_Employee_Vault/Logs/" if restart_count >= MAX_RESTART_ATTEMPTS else "Monitor situation — may stabilize automatically"}
"""

    if not DRY_RUN:
        filepath.write_text(content, encoding="utf-8")
    logger.info(f"{'[DRY RUN] Would create' if DRY_RUN else 'Created'} alert: {filename}")


def start_python_process(name: str, config: dict) -> Optional[subprocess.Popen]:
    """Start a Python process."""
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would start: {name}")
        return None
    try:
        proc = subprocess.Popen(
            config["cmd"],
            cwd=config.get("cwd", str(PROJECT_ROOT)),
            stdout=open(VAULT_PATH / "Logs" / f"{name}.stdout.log", "a"),
            stderr=open(VAULT_PATH / "Logs" / f"{name}.stderr.log", "a"),
        )
        write_pid(config["pid_file"], proc.pid)
        record_restart(name)
        logger.info(f"Started {name} (PID: {proc.pid})")
        return proc
    except Exception as e:
        logger.error(f"Failed to start {name}: {e}")
        return None


def start_mcp_server(name: str, config: dict) -> Optional[subprocess.Popen]:
    """Start a Node.js MCP server."""
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would start MCP: {name}")
        return None
    try:
        server_dir = PROJECT_ROOT / config["dir"]
        proc = subprocess.Popen(
            config["cmd"],
            cwd=str(server_dir),
            stdout=open(VAULT_PATH / "Logs" / f"{name}.stdout.log", "a"),
            stderr=open(VAULT_PATH / "Logs" / f"{name}.stderr.log", "a"),
            env={**os.environ, "PORT": str(config["port"])},
        )
        pid_file = PROJECT_ROOT / ".pids" / f"{name}.pid"
        write_pid(pid_file, proc.pid)
        record_restart(name)
        logger.info(f"Started {name} on port {config['port']} (PID: {proc.pid})")
        return proc
    except Exception as e:
        logger.error(f"Failed to start MCP server {name}: {e}")
        return None


def update_dashboard_status(statuses: dict) -> None:
    """Update Dashboard.md with current component health."""
    dashboard_file = VAULT_PATH / "Dashboard.md"
    if not dashboard_file.exists() or DRY_RUN:
        return

    try:
        content = dashboard_file.read_text(encoding="utf-8")
        # Build new status table
        status_table = "## System Health (Watchdog)\n\n"
        status_table += "| Component | Status | Last Check |\n"
        status_table += "|-----------|--------|------------|\n"
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for comp, is_healthy in statuses.items():
            icon = "✅" if is_healthy else "❌"
            status_table += f"| {comp} | {icon} | {now} |\n"

        # Replace existing system health section or append
        if "## System Health (Watchdog)" in content:
            start = content.find("## System Health (Watchdog)")
            end = content.find("\n## ", start + 1)
            if end == -1:
                content = content[:start] + status_table
            else:
                content = content[:start] + status_table + "\n" + content[end:]
        else:
            content += "\n\n" + status_table

        dashboard_file.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to update Dashboard.md: {e}")


def check_and_restart_all() -> dict:
    """Main watchdog loop body. Returns dict of {component: is_healthy}."""
    statuses = {}

    # Check Python processes
    for name, config in PYTHON_PROCESSES.items():
        pid = read_pid(config["pid_file"])
        running = pid and is_pid_running(pid)

        if running:
            statuses[name] = True
        else:
            logger.warning(f"{name} is NOT running (PID: {pid})")
            statuses[name] = False

            if restart_count_ok(name):
                proc = start_python_process(name, config)
                statuses[name] = proc is not None
            else:
                count = len(restart_counts[name])
                logger.critical(f"{name} has crashed {count} times in the last hour. Manual intervention needed.")
                create_alert_file(name, f"Process crashed {count} times in 1 hour", count)

    # Check MCP servers
    for name, config in MCP_SERVERS.items():
        healthy = check_mcp_health(name, config["port"])
        statuses[name] = healthy

        if not healthy:
            logger.warning(f"{name} health check FAILED (port {config['port']})")

            if restart_count_ok(name):
                proc = start_mcp_server(name, config)
                time.sleep(3)  # Give it time to start
                healthy_after = check_mcp_health(name, config["port"])
                statuses[name] = healthy_after
                if not healthy_after:
                    logger.error(f"{name} failed to start properly")
                    create_alert_file(name, "MCP server failed to start", len(restart_counts[name]))
            else:
                count = len(restart_counts[name])
                logger.critical(f"{name} unreachable after {count} restart attempts")
                create_alert_file(name, f"MCP server down after {count} restarts", count)

    return statuses


def write_watchdog_log(statuses: dict) -> None:
    """Append watchdog status to daily log."""
    log_file = VAULT_PATH / "Logs" / f"{datetime.now().strftime('%Y-%m-%d')}.json"
    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text())
        except Exception:
            entries = []

    entries.append({
        "timestamp": datetime.now().isoformat(),
        "action_type": "system_event",
        "actor": "watchdog",
        "component": "all",
        "result": "healthy" if all(statuses.values()) else "degraded",
        "statuses": statuses,
        "dry_run": DRY_RUN
    })

    if not DRY_RUN:
        log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False))


def main():
    logger.info(f"Watchdog starting (interval: {CHECK_INTERVAL}s, dry_run: {DRY_RUN})")
    logger.info(f"Monitoring {len(PYTHON_PROCESSES)} Python processes + {len(MCP_SERVERS)} MCP servers")

    if DRY_RUN:
        logger.warning("DRY RUN MODE — no processes will be started or restarted")

    while True:
        try:
            statuses = check_and_restart_all()
            write_watchdog_log(statuses)
            update_dashboard_status(statuses)

            healthy_count = sum(1 for v in statuses.values() if v)
            total = len(statuses)
            logger.info(f"Health: {healthy_count}/{total} components OK")

        except KeyboardInterrupt:
            logger.info("Watchdog stopped by user.")
            break
        except Exception as e:
            logger.error(f"Watchdog loop error: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
