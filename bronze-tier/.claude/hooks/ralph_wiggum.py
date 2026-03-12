#!/usr/bin/env python3
"""
ralph_wiggum.py — Ralph Wiggum Stop Hook
=========================================
Intercepts Claude Code's exit signal and re-injects the task prompt if
there are still unprocessed files in /Needs_Action.

Named after Ralph Wiggum (The Simpsons) — keeps going and going
until the job is actually done.

How it works:
  1. Claude finishes a turn and tries to stop.
  2. Claude Code calls this script (configured in .claude/settings.json).
  3. Script checks: are there still FILE_*.md files in Needs_Action/?
  4a. YES → exit code 2, JSON with "block" decision → Claude gets re-injected prompt.
  4b. NO  → exit code 0, JSON with "allow" decision → Claude exits cleanly.

Configuration:
  Add to .claude/settings.json:
  {
    "hooks": {
      "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "python .claude/hooks/ralph_wiggum.py"}]}]
    }
  }

References:
  Hackathon doc Section 2D: "Persistence (The Ralph Wiggum Loop)"
"""

import json
import sys
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────

VAULT_PATH        = Path("AI_Employee_Vault")
NEEDS_ACTION_PATH = VAULT_PATH / "Needs_Action"
MAX_ITERATIONS    = 10        # hard cap — prevents infinite loops
TASK_COMPLETE_TAG = "<TASK_COMPLETE>"   # Claude outputs this when truly done


# ── Helpers ───────────────────────────────────────────────────────────────────

def pending_files(directory: Path) -> list[Path]:
    """Return FILE_*.md files in Needs_Action that are still pending."""
    if not directory.exists():
        return []
    return [
        f for f in directory.glob("FILE_*.md")
        if not f.name.startswith((".","~"))
    ]


def allow_stop(reason: str) -> None:
    """Output allow decision and exit 0 → Claude stops normally."""
    print(json.dumps({"decision": "allow", "reason": reason}))
    sys.exit(0)


def block_stop(reason: str) -> None:
    """Output block decision and exit 2 → Claude gets re-injected prompt."""
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(2)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # Read the JSON payload Claude Code sends on stdin
    try:
        raw = sys.stdin.read().strip()
        payload: dict = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, OSError):
        payload = {}

    # ── Check 1: Has Claude explicitly signalled completion? ──────────────────
    # Claude outputs <TASK_COMPLETE> in its final message when done.
    transcript_text: str = payload.get("transcript_text", "")
    if TASK_COMPLETE_TAG in transcript_text:
        allow_stop("Claude signalled TASK_COMPLETE — all done.")

    # ── Check 2: Iteration guard ──────────────────────────────────────────────
    iteration: int = payload.get("ralph_iteration", 0)
    if iteration >= MAX_ITERATIONS:
        allow_stop(
            f"Max iterations ({MAX_ITERATIONS}) reached. "
            "Stopping to prevent infinite loop. "
            "Review Needs_Action/ manually."
        )

    # ── Check 3: Are there still pending files? ───────────────────────────────
    pending = pending_files(NEEDS_ACTION_PATH)

    if not pending:
        allow_stop("Needs_Action/ is empty — task complete.")

    # ── Still files to process → block exit and re-inject ────────────────────
    names = [f.name for f in pending[:5]]
    more  = f" (+{len(pending) - 5} more)" if len(pending) > 5 else ""
    file_list = "\n".join(f"  • {n}" for n in names) + more

    re_injection = (
        f"RALPH WIGGUM LOOP — Iteration {iteration + 1}/{MAX_ITERATIONS}\n\n"
        f"There are still {len(pending)} unprocessed file(s) in Needs_Action/:\n"
        f"{file_list}\n\n"
        f"Continue processing:\n"
        f"1. Read Skills/SKILL_Process_File_Drop.md\n"
        f"2. Read Company_Handbook.md\n"
        f"3. Process each FILE_*.md in Needs_Action/ one by one\n"
        f"4. Move each completed file to Done/ (or create Pending_Approval/ file)\n"
        f"5. Update Dashboard.md\n"
        f"6. When ALL files are processed, output: {TASK_COMPLETE_TAG}\n"
    )

    block_stop(re_injection)


if __name__ == "__main__":
    main()
