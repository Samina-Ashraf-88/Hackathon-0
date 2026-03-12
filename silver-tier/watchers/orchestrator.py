"""
orchestrator.py — Master orchestration script for the AI Employee.

Responsibilities:
  - Watch /Needs_Action/ for new files and trigger Claude reasoning loop
  - Watch /Approved/ for approved actions and dispatch execution
  - Schedule periodic tasks (daily briefing, sales post generation)
  - Manage the Ralph Wiggum loop state
  - Monitor health of all components

Run continuously: python orchestrator.py
Run once for test: python orchestrator.py --once
"""

import os
import sys
import time
import json
import signal
import argparse
import subprocess
import threading
import shutil
from pathlib import Path
from datetime import datetime, time as dtime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH = PROJECT_ROOT / "AI_Employee_Vault"
SKILLS_PATH = VAULT_PATH / "Skills"
LOGS_DIR = VAULT_PATH / "Logs"

POLL_INTERVAL = 30          # seconds between vault checks
SCHEDULING_INTERVAL = 60    # seconds between schedule checks

# Schedule configuration
SALES_POST_DAYS = {0, 2, 4}   # Monday, Wednesday, Friday (0=Mon)
SALES_POST_HOUR = 9
BRIEFING_DAY = 0              # Monday
BRIEFING_HOUR = 7


class Orchestrator:
    def __init__(self, vault_path: Path = VAULT_PATH):
        self.vault_path = vault_path
        self.needs_action = vault_path / "Needs_Action"
        self.approved = vault_path / "Approved"
        self.pending_approval = vault_path / "Pending_Approval"

        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self._setup_logging()

        self._dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        self._running = True
        self._last_sales_post_date = None
        self._last_briefing_date = None

        # Track known files to detect new arrivals
        self._known_needs_action: set = set()
        self._known_approved: set = set()

        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _setup_logging(self):
        import logging
        log_file = LOGS_DIR / f"orchestrator_{datetime.now().strftime('%Y-%m-%d')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [Orchestrator] %(levelname)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        self.log = logging.getLogger("Orchestrator")

    def _handle_shutdown(self, signum, frame):
        self.log.info("Shutdown signal received. Stopping orchestrator...")
        self._running = False

    def _trigger_claude(self, skill: str, context: str = "") -> subprocess.Popen | None:
        """Launch Claude CLI with a skill prompt."""
        skill_file = SKILLS_PATH / f"{skill}.md"
        if not skill_file.exists():
            self.log.error(f"Skill file not found: {skill_file}")
            return None

        prompt = (
            f"Execute {skill} as defined in {skill_file}. "
            f"Vault path: {self.vault_path}. "
            f"{context}"
        )

        # Resolve claude binary — on Windows npm installs .cmd wrappers
        claude_bin = shutil.which("claude") or shutil.which("claude.cmd")
        if not claude_bin:
            # Fallback: common Windows npm global path
            npm_global = Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd"
            if npm_global.exists():
                claude_bin = str(npm_global)

        cmd = [
            claude_bin or "claude",
            "--print",
            prompt,
            "--cwd", str(self.vault_path),
        ]

        if self._dry_run:
            self.log.info(f"[DRY RUN] Would run Claude with skill: {skill}")
            return None

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=None,   # inherit — avoids pipe deadlock on large output
                stderr=None,
                text=True,
                shell=(sys.platform == "win32"),  # needed for .cmd on Windows
            )
            self.log.info(f"Claude started (PID {proc.pid}) with skill: {skill}")
            return proc
        except FileNotFoundError:
            self.log.error("Claude CLI not found. Install: npm install -g @anthropic/claude-code")
            return None
        except Exception as e:
            self.log.error(f"Failed to start Claude: {e}")
            return None

    def _scan_needs_action(self) -> list:
        """Return new .md files in /Needs_Action/ not seen before."""
        if not self.needs_action.exists():
            return []

        current = set(f.name for f in self.needs_action.glob("*.md"))
        new_files = current - self._known_needs_action
        self._known_needs_action = current
        return list(new_files)

    def _scan_approved(self) -> list:
        """Return new files in /Approved/ not seen before."""
        if not self.approved.exists():
            return []

        current = set(f.name for f in self.approved.glob("*.md"))
        new_files = current - self._known_approved
        self._known_approved = current
        return list(new_files)

    def _dispatch_approved_action(self, filename: str) -> None:
        """Route an approved file to the correct execution handler."""
        fn_lower = filename.lower()

        if fn_lower.startswith("email_reply") or fn_lower.startswith("email_send"):
            self.log.info(f"Dispatching email send for: {filename}")
            self._trigger_claude(
                "SKILL_Send_Email_via_MCP",
                context=f"Process approved file: {filename}"
            )

        elif fn_lower.startswith("linkedin_post"):
            self.log.info(f"Dispatching LinkedIn post for: {filename}")
            self._run_linkedin_poster(filename)

        elif fn_lower.startswith("linkedin_dm") or fn_lower.startswith("linkedin_message"):
            self.log.info(f"LinkedIn DM approved: {filename} — dispatch manually via linkedin_poster.py")

        elif fn_lower.startswith("facebook_post") or fn_lower.startswith("post_facebook") or fn_lower.startswith("post_fb"):
            self.log.info(f"Dispatching Facebook post for: {filename}")
            self._run_social_poster("facebook", filename)

        elif fn_lower.startswith("instagram_post") or fn_lower.startswith("post_instagram") or fn_lower.startswith("post_ig"):
            self.log.info(f"Dispatching Instagram post for: {filename}")
            self._run_social_poster("instagram", filename)

        elif fn_lower.startswith("twitter_post") or fn_lower.startswith("post_twitter") or fn_lower.startswith("post_tw"):
            self.log.info(f"Dispatching Twitter post for: {filename}")
            self._run_social_poster("twitter", filename)

        elif (fn_lower.startswith("odoo_")
              or fn_lower.startswith("ceo_action_")
              or fn_lower.startswith("invoice_")
              or fn_lower.startswith("payment_")
              or fn_lower.startswith("bill_")):
            self.log.info(f"Dispatching Odoo accounting action for: {filename}")
            self._trigger_claude(
                "SKILL_Odoo_Accounting_Actions",
                context=(
                    f"Process approved Odoo action from file: "
                    f"{self.approved / filename}. "
                    "Execute the action via odoo-mcp (http://localhost:3004), "
                    "log the result to /Logs/, and move the file to /Done/ when complete."
                )
            )

        else:
            self.log.info(f"Unknown approved action type: {filename} — triggering reasoning loop")
            self._trigger_claude("SKILL_Reasoning_Loop")

    def _run_linkedin_poster(self, filename: str) -> None:
        """Run linkedin_poster.py for an approved post file."""
        script = Path(__file__).parent / "linkedin_poster.py"
        approved_file = self.approved / filename

        cmd = [
            sys.executable, str(script),
            "--file", str(approved_file),
            "--vault", str(self.vault_path),
        ]

        if self._dry_run:
            cmd.append("--dry-run")

        try:
            subprocess.Popen(cmd)
            self.log.info(f"LinkedIn poster launched for: {filename}")
        except Exception as e:
            self.log.error(f"Failed to launch linkedin_poster.py: {e}")

    def _run_social_poster(self, platform: str, filename: str) -> None:
        """Run social_poster.py for an approved social post file."""
        script = Path(__file__).parent / "social_poster.py"
        approved_file = self.approved / filename

        cmd = [
            sys.executable, str(script),
            "--platform", platform,
            "--file", str(approved_file),
            "--vault", str(self.vault_path),
        ]

        if self._dry_run:
            cmd.append("--dry-run")

        try:
            subprocess.Popen(cmd)
            self.log.info(f"Social poster launched ({platform}) for: {filename}")
        except Exception as e:
            self.log.error(f"Failed to launch social_poster.py: {e}")

    def _should_generate_sales_post(self) -> bool:
        """Check if it's time to generate a scheduled sales post."""
        now = datetime.now()
        today = now.date()
        weekday = today.weekday()
        hour = now.hour

        if weekday not in SALES_POST_DAYS:
            return False
        if hour < SALES_POST_HOUR:
            return False
        if self._last_sales_post_date == today:
            return False

        return True

    def _should_generate_briefing(self) -> bool:
        """Check if it's Monday morning briefing time."""
        now = datetime.now()
        today = now.date()

        if now.weekday() != BRIEFING_DAY:
            return False
        if now.hour < BRIEFING_HOUR:
            return False
        if self._last_briefing_date == today:
            return False

        return True

    def _run_scheduled_tasks(self) -> None:
        """Check and run scheduled tasks."""
        if self._should_generate_sales_post():
            self.log.info("Scheduled: Generating LinkedIn sales post...")
            self._trigger_claude(
                "SKILL_Generate_Sales_Post",
                context="Generate a scheduled LinkedIn sales post. Choose the best content pillar."
            )
            self.log.info("Scheduled: Generating cross-platform social posts (FB/IG/TW)...")
            for platform in ("facebook", "instagram", "twitter"):
                self._trigger_claude(
                    "SKILL_Process_Social_Post",
                    context=(
                        f"Generate a scheduled {platform.title()} post for today. "
                        f"Choose an engaging AI automation tip. "
                        f"Target platform: {platform}. "
                        f"Create POST_REQUEST_{platform.upper()}_SCHEDULED_"
                        f"{datetime.now().strftime('%Y%m%d')}.md in /Needs_Action/."
                    )
                )
            self._last_sales_post_date = datetime.now().date()

        if self._should_generate_briefing():
            self.log.info("Scheduled: Generating Monday CEO Briefing...")
            self._trigger_claude(
                "SKILL_Weekly_CEO_Briefing",
                context=(
                    "Generate the full Monday Morning CEO Briefing. "
                    "Pull Odoo accounting data via odoo-mcp (http://localhost:3004): "
                    "revenue, unpaid invoices, AR aging, cash flow, P&L. "
                    "Analyze Done/ folder tasks completed this week. "
                    "Read all Logs/*.json for this week. "
                    "Compare against Business_Goals.md targets. "
                    "Save briefing to Briefings/YYYYMMDD_Monday_CEO_Briefing.md. "
                    "Update Dashboard.md. Move WEEKLY_BRIEFING_*.md to Done/."
                )
            )
            self._last_briefing_date = datetime.now().date()

    def _update_dashboard_status(self, component: str, status: str) -> None:
        """Update a component status in Dashboard.md."""
        dashboard = self.vault_path / "Dashboard.md"
        if not dashboard.exists():
            return
        try:
            content = dashboard.read_text(encoding="utf-8")
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            # Replace status line for this component
            content = content.replace(
                f"| {component} | ⬜ Not started |",
                f"| {component} | {status} | {ts} |"
            ).replace(
                f"| {component} | ✅ Running |",
                f"| {component} | {status} | {ts} |"
            ).replace(
                f"| {component} | ❌ Error |",
                f"| {component} | {status} | {ts} |"
            )
            dashboard.write_text(content, encoding="utf-8")
        except Exception as e:
            self.log.debug(f"Could not update dashboard: {e}")

    def run_once(self) -> None:
        """Run a single check cycle (for testing)."""
        self.log.info("Running single check cycle...")

        new_items = self._scan_needs_action()
        if new_items:
            self.log.info(f"New items in Needs_Action: {new_items}")
            self._trigger_claude("SKILL_Reasoning_Loop")
        else:
            self.log.info("No new items in Needs_Action.")

        new_approved = self._scan_approved()
        for filename in new_approved:
            self._dispatch_approved_action(filename)

        self.log.info("Single check complete.")

    def run(self) -> None:
        """Main orchestration loop."""
        self.log.info(f"Orchestrator starting. Vault: {self.vault_path}")
        self.log.info(f"Dry run: {self._dry_run}")
        self._update_dashboard_status("Orchestrator", "✅ Running")

        # Initialize known file sets
        self._known_needs_action = set(
            f.name for f in self.needs_action.glob("*.md")
        ) if self.needs_action.exists() else set()
        self._known_approved = set(
            f.name for f in self.approved.glob("*.md")
        ) if self.approved.exists() else set()

        schedule_counter = 0

        while self._running:
            try:
                # Check for new items in Needs_Action
                new_items = self._scan_needs_action()
                if new_items:
                    self.log.info(f"New items detected in Needs_Action: {new_items}")
                    self._trigger_claude("SKILL_Reasoning_Loop")

                # Check for newly approved actions
                new_approved = self._scan_approved()
                for filename in new_approved:
                    self.log.info(f"Approved action detected: {filename}")
                    self._dispatch_approved_action(filename)

                # Check scheduled tasks every minute
                schedule_counter += 1
                if schedule_counter >= (SCHEDULING_INTERVAL // POLL_INTERVAL):
                    self._run_scheduled_tasks()
                    schedule_counter = 0

            except Exception as e:
                self.log.error(f"Orchestrator loop error: {e}")

            time.sleep(POLL_INTERVAL)

        self._update_dashboard_status("Orchestrator", "⬜ Stopped")
        self.log.info("Orchestrator stopped.")


def main():
    parser = argparse.ArgumentParser(description="AI Employee Orchestrator")
    parser.add_argument("--vault", default=str(VAULT_PATH), help="Vault path")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument(
        "--trigger", choices=["reasoning_loop", "sales_post", "briefing"],
        help="Manually trigger a specific skill"
    )
    args = parser.parse_args()

    orch = Orchestrator(vault_path=Path(args.vault))

    if args.trigger:
        skill_map = {
            "reasoning_loop": "SKILL_Reasoning_Loop",
            "sales_post": "SKILL_Generate_Sales_Post",
            "briefing": "SKILL_Reasoning_Loop",
        }
        orch._trigger_claude(skill_map[args.trigger])
        return

    if args.once:
        orch.run_once()
        return

    orch.run()


if __name__ == "__main__":
    main()
