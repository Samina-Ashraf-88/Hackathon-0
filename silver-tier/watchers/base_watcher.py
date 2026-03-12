"""
base_watcher.py — Abstract base class for all AI Employee Watchers.
All watchers inherit from this class for consistent behaviour.
"""

import time
import logging
import subprocess
import json
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime


def setup_logging(name: str, log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name}_{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # File handler
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.INFO)
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger


class BaseWatcher(ABC):
    """
    Base class for all watchers. Provides run loop, logging,
    vault path management, and Claude CLI trigger functionality.
    """

    def __init__(self, vault_path: str, check_interval: int = 60):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / "Needs_Action"
        self.done = self.vault_path / "Done"
        self.logs_dir = self.vault_path / "Logs"
        self.check_interval = check_interval

        # Ensure key directories exist
        self.needs_action.mkdir(parents=True, exist_ok=True)
        self.done.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.logger = setup_logging(self.__class__.__name__, self.logs_dir)
        self._dry_run = self._get_dry_run_flag()

        if self._dry_run:
            self.logger.info("DRY RUN MODE ENABLED — no real external actions will be taken")

    def _get_dry_run_flag(self) -> bool:
        import os
        return os.getenv("DRY_RUN", "true").lower() == "true"

    @abstractmethod
    def check_for_updates(self) -> list:
        """Return list of new items to process."""
        pass

    @abstractmethod
    def create_action_file(self, item) -> Path:
        """Create a .md file in Needs_Action folder and return the path."""
        pass

    def trigger_claude(self, skill: str = "SKILL_Reasoning_Loop") -> None:
        """
        Trigger Claude CLI to process the vault using a specified skill.
        Claude CLI must be installed and available in PATH.
        """
        vault_str = str(self.vault_path)
        skill_path = str(self.vault_path / "Skills" / f"{skill}.md")

        cmd = [
            "claude",
            "--print",
            f"Execute {skill} as defined in {skill_path}. "
            f"Process all pending items in {vault_str}/Needs_Action/.",
            "--cwd", vault_str,
        ]

        if self._dry_run:
            self.logger.info(f"[DRY RUN] Would trigger Claude: {' '.join(cmd)}")
            return

        try:
            self.logger.info(f"Triggering Claude with skill: {skill}")
            result = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.logger.info(f"Claude process started (PID: {result.pid})")
        except FileNotFoundError:
            self.logger.error(
                "Claude CLI not found. Install it: npm install -g @anthropic/claude-code"
            )
        except Exception as e:
            self.logger.error(f"Failed to trigger Claude: {e}")

    def write_action_log(self, entry: dict) -> None:
        """Append an action entry to today's log file."""
        log_file = self.logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"
        entries = []

        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    entries = json.load(f)
            except json.JSONDecodeError:
                entries = []

        entry["timestamp"] = datetime.now().isoformat()
        entry["actor"] = self.__class__.__name__
        entries.append(entry)

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

    def run(self) -> None:
        """Main polling loop. Runs indefinitely."""
        self.logger.info(
            f"Starting {self.__class__.__name__} "
            f"(interval: {self.check_interval}s, vault: {self.vault_path})"
        )

        consecutive_errors = 0
        max_consecutive_errors = 5

        while True:
            try:
                items = self.check_for_updates()

                if items:
                    self.logger.info(f"Found {len(items)} new item(s) to process")
                    files_created = []

                    for item in items:
                        try:
                            filepath = self.create_action_file(item)
                            files_created.append(filepath)
                            self.logger.info(f"Created action file: {filepath.name}")
                        except Exception as e:
                            self.logger.error(f"Failed to create action file for item: {e}")

                    if files_created:
                        self.trigger_claude()

                consecutive_errors = 0

            except KeyboardInterrupt:
                self.logger.info("Watcher stopped by user.")
                break
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"Error in check loop: {e}")

                if consecutive_errors >= max_consecutive_errors:
                    self.logger.critical(
                        f"Too many consecutive errors ({consecutive_errors}). "
                        "Sleeping 5 minutes before retrying."
                    )
                    time.sleep(300)
                    consecutive_errors = 0

            time.sleep(self.check_interval)
