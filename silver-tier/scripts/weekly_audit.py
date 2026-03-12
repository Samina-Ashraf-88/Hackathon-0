"""
scripts/weekly_audit.py — Weekly CEO Briefing Trigger

Triggered every Sunday at 22:00 by Windows Task Scheduler or cron.
Creates a WEEKLY_BRIEFING_*.md in /Needs_Action/ and triggers Claude
to run SKILL_Weekly_CEO_Briefing via the Ralph Wiggum loop.

Usage:
  python scripts/weekly_audit.py
  python scripts/weekly_audit.py --dry-run
  python scripts/weekly_audit.py --now      # Run immediately, ignore schedule

Setup (Windows Task Scheduler):
  Action: python "E:/hackathon-0/silver-tier/scripts/weekly_audit.py"
  Trigger: Weekly, Sunday, 10:00 PM
  Start In: E:/hackathon-0/silver-tier

Setup (Linux/Mac cron):
  0 22 * * 0 cd /path/to/silver-tier && python scripts/weekly_audit.py
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# ── Config ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH   = PROJECT_ROOT / "AI_Employee_Vault"
NEEDS_ACTION = VAULT_PATH / "Needs_Action"
LOGS_DIR     = VAULT_PATH / "Logs"
SKILLS_DIR   = VAULT_PATH / "Skills"

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# Dates
today    = datetime.now()
monday   = today - timedelta(days=today.weekday())   # This Monday
sunday   = monday + timedelta(days=6)                # This Sunday
next_mon = monday + timedelta(days=7)                # Next Monday


def log(msg: str, level: str = "INFO") -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}")


def create_briefing_trigger_file() -> Path:
    """Create the trigger file that Claude will pick up."""
    date_str = today.strftime("%Y%m%d")
    filename = f"WEEKLY_BRIEFING_{date_str}.md"
    filepath = NEEDS_ACTION / filename

    period_start = monday.strftime("%Y-%m-%d")
    period_end   = sunday.strftime("%Y-%m-%d")
    month_start  = today.replace(day=1).strftime("%Y-%m-%d")
    month_end    = today.strftime("%Y-%m-%d")

    content = f"""---
type: weekly_briefing
skill: SKILL_Weekly_CEO_Briefing
created: "{today.isoformat()}"
period_start: "{period_start}"
period_end: "{period_end}"
month_start: "{month_start}"
month_end: "{month_end}"
next_briefing: "{next_mon.strftime('%Y-%m-%d')}"
status: pending
priority: high
---

# Weekly CEO Briefing Request

**Period:** {period_start} to {period_end}
**Generated:** {today.strftime('%A, %B %d, %Y at %I:%M %p')}
**Next Briefing:** {next_mon.strftime('%A, %B %d, %Y')}

## Instructions for Claude
Execute **SKILL_Weekly_CEO_Briefing** completely:

1. Pull Odoo accounting data via odoo-mcp
   - Revenue: `GET http://localhost:3004/revenue?date_from={month_start}&date_to={month_end}`
   - Unpaid invoices: `GET http://localhost:3004/invoices?state=open`
   - Expenses: `GET http://localhost:3004/expenses?date_from={month_start}&date_to={month_end}`

2. Analyze `/Done/` folder for tasks completed this week ({period_start} to {period_end})

3. Read all `/Logs/*.json` for this week and aggregate metrics

4. Analyze social media activity (Facebook, Instagram, Twitter) from logs

5. Compare against `Business_Goals.md` targets

6. Run subscription audit

7. Generate proactive suggestions (3-5 actionable items)

8. Write briefing to: `/Briefings/{next_mon.strftime('%Y%m%d')}_Monday_CEO_Briefing.md`

9. Create approval files for any suggested actions requiring human sign-off

10. Update `Dashboard.md`

11. Log completion: action_type=ceo_briefing

12. Move THIS FILE to /Done/

13. Output: `<promise>TASK_COMPLETE</promise>`

## Data Collection Checklist
- [ ] Odoo revenue data fetched
- [ ] Odoo unpaid invoices fetched
- [ ] Odoo expenses fetched
- [ ] Task completion analysis done
- [ ] Log aggregation done
- [ ] Social media summary compiled
- [ ] Goals comparison done
- [ ] Subscription audit done
- [ ] Briefing file written
- [ ] Dashboard updated
- [ ] Completion logged
"""

    NEEDS_ACTION.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    log(f"Created briefing trigger: {filename}")
    return filepath


def trigger_claude(briefing_file: Path) -> None:
    """Trigger Claude CLI to process the briefing."""
    vault_str = str(VAULT_PATH)
    skill_path = str(SKILLS_DIR / "SKILL_Weekly_CEO_Briefing.md")
    ralph_path = str(SKILLS_DIR / "SKILL_Ralph_Wiggum_Autonomous_Loop.md")

    prompt = (
        f"Execute SKILL_Ralph_Wiggum_Autonomous_Loop. "
        f"Start with SKILL_Weekly_CEO_Briefing as defined in {skill_path}. "
        f"Process the briefing trigger file: {briefing_file}. "
        f"Vault path: {vault_str}. "
        f"Complete all steps and output <promise>TASK_COMPLETE</promise> when done."
    )

    cmd = ["claude", "--print", prompt, "--cwd", vault_str]

    if DRY_RUN:
        log(f"[DRY RUN] Would trigger Claude: claude --print '...' --cwd {vault_str}")
        return

    log("Triggering Claude to generate CEO Briefing...")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        log(f"Claude process started (PID: {proc.pid})")

        # Don't wait — let the Ralph Wiggum loop run independently
        stdout, stderr = proc.communicate(timeout=1800)  # 30 min max
        if proc.returncode == 0:
            log("✅ Claude CEO Briefing complete")
        else:
            log(f"Claude exited with code {proc.returncode}. Check logs.", "WARNING")
            if stderr:
                log(f"STDERR: {stderr[:500]}", "WARNING")

    except subprocess.TimeoutExpired:
        log("Claude process timed out after 30 minutes. Briefing may be partial.", "WARNING")
    except FileNotFoundError:
        log("Claude CLI not found. Install: npm install -g @anthropic/claude-code", "ERROR")
    except Exception as e:
        log(f"Failed to trigger Claude: {e}", "ERROR")


def write_audit_log(briefing_file: Path) -> None:
    """Write audit entry for this weekly audit trigger."""
    log_file = LOGS_DIR / f"{today.strftime('%Y-%m-%d')}.json"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text())
        except Exception:
            entries = []

    entries.append({
        "timestamp": today.isoformat(),
        "action_type": "system_event",
        "actor": "weekly_audit_script",
        "component": "scheduler",
        "skill_invoked": "SKILL_Weekly_CEO_Briefing",
        "result": "triggered",
        "source_file": str(briefing_file),
        "dry_run": DRY_RUN,
        "period": f"{monday.strftime('%Y-%m-%d')} to {sunday.strftime('%Y-%m-%d')}"
    })

    log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False))
    log(f"Audit log written: {log_file.name}")


def main():
    parser = argparse.ArgumentParser(description="Weekly CEO Briefing Trigger")
    parser.add_argument("--dry-run", action="store_true", help="Create file but don't trigger Claude")
    parser.add_argument("--now", action="store_true", help="Run immediately")
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"

    log(f"Weekly CEO Briefing Trigger")
    log(f"Period: {monday.strftime('%Y-%m-%d')} to {sunday.strftime('%Y-%m-%d')}")
    log(f"DRY_RUN: {DRY_RUN}")

    briefing_file = create_briefing_trigger_file()
    write_audit_log(briefing_file)

    if not args.dry_run:
        trigger_claude(briefing_file)
    else:
        log(f"Dry run complete. Briefing trigger file: {briefing_file}")
        log("Run without --dry-run to trigger Claude automatically.")


if __name__ == "__main__":
    main()
