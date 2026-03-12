#!/usr/bin/env python3
"""
filesystem_watcher.py — AI Employee File System Watcher
========================================================
Monitors the AI_Employee_Vault/Inbox folder for new file drops.
For each new file:
  1. Copies it to Needs_Action/ as FILE_{name}{ext}
  2. Creates a companion metadata .md file (FILE_{name}.md)
  3. Optionally triggers Claude CLI to process the vault

Part of: Personal AI Employee — Bronze Tier
Hackathon: Building Autonomous FTEs in 2026

Usage:
    python filesystem_watcher.py
    python filesystem_watcher.py --vault /path/to/AI_Employee_Vault
    python filesystem_watcher.py --auto-trigger   # enables Claude CLI invocation

Requirements:
    pip install watchdog
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path


# ─── Default Configuration ────────────────────────────────────────────────────

DEFAULT_VAULT = Path("AI_Employee_Vault")
CLAUDE_SKILL  = "Skills/SKILL_Process_File_Drop.md"
MAX_LOG_LINES = 10_000   # rotate log after this many lines
SETTLE_DELAY  = 0.8      # seconds to wait after file creation before copying


# ─── Logging Setup ────────────────────────────────────────────────────────────

def setup_logging(logs_dir: Path) -> logging.Logger:
    """Configure structured logging to both console and a rolling daily file."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"watcher_{datetime.now().strftime('%Y-%m-%d')}.log"

    fmt = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger("FileSystemWatcher")
    logger.info(f"Log file: {log_file.resolve()}")
    return logger


# ─── Audit Logger ─────────────────────────────────────────────────────────────

def write_audit_log(logs_dir: Path, action_type: str, source: str,
                    destination: str, result: str) -> None:
    """Append a structured JSON audit entry to /Logs/YYYY-MM-DD.json."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"

    entry = {
        "timestamp":   datetime.now().isoformat(),
        "action_type": action_type,
        "actor":       "filesystem_watcher",
        "source":      source,
        "destination": destination,
        "result":      result,
    }

    entries: list = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            entries = []

    entries.append(entry)
    log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                        encoding="utf-8")


# ─── Claude Trigger ───────────────────────────────────────────────────────────

def trigger_claude(vault_root: Path, meta_file: Path,
                   logger: logging.Logger) -> None:
    """
    Invoke process_vault.py to process a newly queued file via Anthropic SDK.
    Only called when --auto-trigger flag is set.
    """
    processor = Path(__file__).parent / "process_vault.py"
    if not processor.exists():
        logger.error(
            "process_vault.py not found next to filesystem_watcher.py. "
            "Run: python process_vault.py --help"
        )
        return

    try:
        logger.info(f"Auto-triggering processor for: {meta_file.name} ...")
        result = subprocess.run(
            [sys.executable, str(processor),
             "--vault", str(vault_root),
             "--file", meta_file.name],
            cwd=str(vault_root.parent),
            capture_output=False,   # let output stream to the console
            text=True,
            timeout=180,
            env={**__import__("os").environ},
        )
        if result.returncode == 0:
            logger.info(f"[OK] Processor completed for: {meta_file.name}")
        else:
            logger.warning(f"Processor exited with code {result.returncode}")
    except subprocess.TimeoutExpired:
        logger.error("Processor timed out (180 s). File remains in Needs_Action/ for manual processing.")
    except Exception as exc:
        logger.error(f"Failed to trigger processor: {exc}", exc_info=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def human_size(size_bytes: int) -> str:
    """Convert bytes to a human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes:.1f} PB"


FILE_TYPE_MAP: dict[str, str] = {
    ".pdf":  "document",  ".docx": "document", ".doc": "document",
    ".txt":  "text",      ".md":   "markdown",
    ".csv":  "spreadsheet", ".xlsx": "spreadsheet", ".xls": "spreadsheet",
    ".png":  "image",     ".jpg":  "image",    ".jpeg": "image", ".gif": "image",
    ".mp4":  "video",     ".mp3":  "audio",
    ".zip":  "archive",   ".tar":  "archive",  ".gz":  "archive",
    ".json": "data",      ".xml":  "data",     ".yaml": "data",
}


def build_metadata(source: Path, dest_file: Path, meta_file: Path) -> str:
    """Return the YAML-frontmatter metadata .md file content."""
    ext       = source.suffix.lower()
    file_type = FILE_TYPE_MAP.get(ext, "unknown")
    size_b    = source.stat().st_size
    now       = datetime.now()

    return f"""\
---
type: file_drop
original_name: {source.name}
safe_name: {dest_file.name}
file_type: {file_type}
extension: {ext or "none"}
size_bytes: {size_b}
size_human: {human_size(size_b)}
source_path: {source}
vault_path: {dest_file}
received: {now.isoformat()}
timestamp: {now.strftime("%Y%m%d_%H%M%S")}
status: pending
processed_by: filesystem_watcher
skill_to_apply: {CLAUDE_SKILL}
---

# File Drop: {source.name}

A new file has been detected and queued for processing.

## File Details

| Field          | Value                        |
|----------------|------------------------------|
| Original Name  | `{source.name}`              |
| Type           | {file_type}                  |
| Extension      | `{ext or "none"}`            |
| Size           | {human_size(size_b)}         |
| Received       | {now.strftime("%Y-%m-%d %H:%M:%S")} |

## Required Actions

- [ ] Review file contents and determine required action
- [ ] Check `Company_Handbook.md` for applicable rules
- [ ] Create plan using `SKILL_Generate_Plan.md`
- [ ] If approval needed → create file in `/Pending_Approval/`
- [ ] If no approval needed → complete plan, move to `/Done/`
- [ ] Update `Dashboard.md` — Recent Activity
- [ ] Write log entry to `/Logs/{{date}}.json`

## Process with Claude CLI

```bash
claude "Read Skills/SKILL_Process_File_Drop.md. \\
Process the file drop at Needs_Action/{meta_file.name}. \\
Read Company_Handbook.md first."
```

---
*Auto-generated by File System Watcher | {now.strftime("%Y-%m-%d %H:%M:%S")}*
"""


# ─── Event Handler ────────────────────────────────────────────────────────────

class DropFolderHandler:
    """
    Minimal cross-platform file event handler.
    Works without the watchdog FileSystemEventHandler base class so it can
    also be used as a standalone polling loop if watchdog is unavailable.
    """

    def __init__(self, vault_root: Path, auto_trigger: bool,
                 logger: logging.Logger) -> None:
        self.vault_root    = vault_root
        self.inbox         = vault_root / "Inbox"
        self.needs_action  = vault_root / "Needs_Action"
        self.logs_dir      = vault_root / "Logs"
        self.auto_trigger  = auto_trigger
        self.logger        = logger
        self._seen: set[str] = set()        # tracks already-processed source paths
        self._last_event: dict[str, float] = {}  # debounce: path → last event time
        self._lock = threading.Lock()            # thread-safe debounce

    # ── public ────────────────────────────────────────────────────────────────

    def handle_new_file(self, source: Path) -> None:
        """Called whenever a new file is created in Inbox."""
        key = str(source.resolve())
        now = time.monotonic()

        # Thread-safe debounce: ignore duplicate events within 3 seconds
        with self._lock:
            if now - self._last_event.get(key, 0) < 3.0:
                return
            if key in self._seen:
                return
            self._last_event[key] = now
            self._seen.add(key)

        # Skip hidden / temp / system files
        if source.name.startswith((".", "~", "$")):
            return
        # Skip directories
        if source.is_dir():
            return

        self.logger.info(f">> New file detected: {source.name}")
        time.sleep(SETTLE_DELAY)   # let the write finish

        try:
            self._process(source)
        except PermissionError as exc:
            # WinError 32: another thread already copied the file — check if done
            safe_stem = source.stem.replace(" ", "_")
            existing  = list(self.needs_action.glob(f"FILE_{safe_stem}*.md"))
            if existing:
                self.logger.info(f"[SKIP] Already processed by another thread: {source.name}")
            else:
                self.logger.error(f"Permission error on {source.name}: {exc}")
                write_audit_log(self.logs_dir, "file_drop_detected",
                                str(source), "", f"error:{exc}")
        except Exception as exc:
            self.logger.error(
                f"Error processing {source.name}: {exc}", exc_info=True
            )
            write_audit_log(
                self.logs_dir, "file_drop_detected",
                str(source), "", f"error:{exc}"
            )

    # ── private ───────────────────────────────────────────────────────────────

    def _process(self, source: Path) -> None:
        self.needs_action.mkdir(parents=True, exist_ok=True)

        safe_stem  = source.stem.replace(" ", "_")
        dest_file  = self.needs_action / f"FILE_{safe_stem}{source.suffix}"
        meta_file  = self.needs_action / f"FILE_{safe_stem}.md"

        # Guard: if a metadata file for this source already exists (any counter),
        # skip entirely — prevents duplicate processing from rapid watchdog events.
        existing = list(self.needs_action.glob(f"FILE_{safe_stem}*.md"))
        if existing:
            self.logger.info(f"[SKIP] Already queued: {source.name} → {existing[0].name}")
            return

        # Resolve naming conflicts (safety net for edge cases)
        n = 1
        while dest_file.exists() or meta_file.exists():
            dest_file = self.needs_action / f"FILE_{safe_stem}_{n}{source.suffix}"
            meta_file = self.needs_action / f"FILE_{safe_stem}_{n}.md"
            n += 1

        # 1. Copy original file
        shutil.copy2(source, dest_file)
        self.logger.info(f"   OK Copied  -> {dest_file.name}")

        # 2. Write metadata
        meta_file.write_text(
            build_metadata(source, dest_file, meta_file),
            encoding="utf-8",
        )
        self.logger.info(f"   OK Metadata -> {meta_file.name}")

        # 3. Audit log
        write_audit_log(
            self.logs_dir, "file_drop_detected",
            str(source), str(dest_file), "success"
        )

        # 4. Print processing hint
        self.logger.info(
            f"\n   +-- To process manually ---------------------------------------+\n"
            f"   |  claude \"Read Skills/SKILL_Process_File_Drop.md.            |\n"
            f"   |          Process Needs_Action/{meta_file.name}\"  |\n"
            f"   +-------------------------------------------------------------+\n"
        )

        # 5. Optionally call Claude
        if self.auto_trigger:
            trigger_claude(self.vault_root, meta_file, self.logger)

        self.logger.info(f"[DONE] File processed: {source.name}\n")


# ─── Watchdog Integration ─────────────────────────────────────────────────────

def run_with_watchdog(handler: DropFolderHandler, logger: logging.Logger) -> None:
    """Use the watchdog library for efficient OS-level file watching."""
    from watchdog.events import FileSystemEventHandler   # type: ignore
    from watchdog.observers import Observer               # type: ignore

    class _WatchdogBridge(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                handler.handle_new_file(Path(event.src_path))

    observer = Observer()
    observer.schedule(_WatchdogBridge(), str(handler.inbox), recursive=False)
    observer.start()
    logger.info(f"[OK] watchdog observer started on: {handler.inbox.resolve()}")
    logger.info("   Drop files into Inbox/ to trigger processing.")
    logger.info("   Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nShutting down (watchdog) …")
        observer.stop()
        observer.join()


# ─── Polling Fallback ─────────────────────────────────────────────────────────

def run_with_polling(handler: DropFolderHandler, logger: logging.Logger,
                     interval: int = 5) -> None:
    """
    Pure-Python polling fallback — no watchdog required.
    Scans Inbox every `interval` seconds for new files.
    """
    seen: set[str] = set()
    logger.info(f"[OK] Polling watcher started on: {handler.inbox.resolve()}")
    logger.info(f"   Interval: {interval}s | Drop files into Inbox/.")
    logger.info("   Press Ctrl+C to stop.\n")
    try:
        while True:
            if handler.inbox.exists():
                for f in handler.inbox.iterdir():
                    key = str(f.resolve())
                    if key not in seen and f.is_file():
                        seen.add(key)
                        handler.handle_new_file(f)
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("\nShutting down (polling) …")


# ─── Vault Structure Bootstrap ────────────────────────────────────────────────

def ensure_vault_structure(vault_root: Path, logger: logging.Logger) -> None:
    """Create all required vault directories if they don't exist."""
    dirs = [
        vault_root / "Inbox",
        vault_root / "Needs_Action",
        vault_root / "Done",
        vault_root / "Plans",
        vault_root / "Logs",
        vault_root / "Pending_Approval",
        vault_root / "Approved",
        vault_root / "Rejected",
        vault_root / "Briefings",
        vault_root / "Skills",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    logger.info(f"Vault structure verified at: {vault_root.resolve()}")


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="AI Employee File System Watcher — Bronze Tier"
    )
    p.add_argument(
        "--vault", type=Path, default=DEFAULT_VAULT,
        help="Path to AI_Employee_Vault (default: ./AI_Employee_Vault)",
    )
    p.add_argument(
        "--auto-trigger", action="store_true", default=True,
        help="Automatically invoke process_vault.py when a new file is detected (default: ON)",
    )
    p.add_argument(
        "--no-auto-trigger", dest="auto_trigger", action="store_false",
        help="Disable auto-processing (only queue files to Needs_Action/)",
    )
    p.add_argument(
        "--poll", action="store_true",
        help="Use polling fallback instead of watchdog (slower but no extra deps)",
    )
    p.add_argument(
        "--interval", type=int, default=5,
        help="Polling interval in seconds (only used with --poll, default: 5)",
    )
    return p.parse_args()


def main() -> None:
    args     = parse_args()
    vault    = args.vault.resolve()
    logs_dir = vault / "Logs"

    logger = setup_logging(logs_dir)
    logger.info("=" * 60)
    logger.info(" AI Employee — File System Watcher")
    logger.info("=" * 60)
    logger.info(f"Vault        : {vault}")
    logger.info(f"Watching     : {vault / 'Inbox'}")
    logger.info(f"Needs Action : {vault / 'Needs_Action'}")
    logger.info(f"Auto-trigger : {'ON (process_vault.py)' if args.auto_trigger else 'OFF (manual)'}")

    ensure_vault_structure(vault, logger)

    handler = DropFolderHandler(
        vault_root=vault,
        auto_trigger=args.auto_trigger,
        logger=logger,
    )

    if args.poll:
        run_with_polling(handler, logger, interval=args.interval)
    else:
        try:
            run_with_watchdog(handler, logger)
        except ImportError:
            logger.warning(
                "watchdog not installed — falling back to polling mode.\n"
                "Install with: pip install watchdog"
            )
            run_with_polling(handler, logger, interval=args.interval)


if __name__ == "__main__":
    main()
