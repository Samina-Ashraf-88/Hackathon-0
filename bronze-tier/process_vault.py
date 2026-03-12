#!/usr/bin/env python3
"""
process_vault.py — AI Employee Vault Processor
===============================================
Scans Needs_Action/ for pending FILE_*.md files and processes each one:
  1. Reads the file metadata + original file content
  2. Calls Claude to classify, plan, and summarise
  3. Writes a Plan.md to Plans/
  4. Moves the metadata to Done/ (or creates a Pending_Approval/ request)
  5. Updates Dashboard.md and the JSON audit log

Usage:
    python process_vault.py
    python process_vault.py --vault /path/to/AI_Employee_Vault
    python process_vault.py --dry-run        # preview, no changes
    python process_vault.py --file FILE_foo.md   # process one file only

Requires:
    pip install anthropic
    ANTHROPIC_API_KEY must be set in the environment.
"""

import argparse
import json
import os
import shutil
import sys
import textwrap
from datetime import datetime
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("[ERROR] anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)


# ─── Configuration ────────────────────────────────────────────────────────────

DEFAULT_VAULT  = Path("AI_Employee_Vault")
MODEL          = "claude-sonnet-4-6"
MAX_FILE_CHARS = 8_000   # max characters read from a dropped text file


# ─── Vault Helpers ────────────────────────────────────────────────────────────

def read_skill(vault: Path, skill_name: str) -> str:
    path = vault / "Skills" / skill_name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_handbook(vault: Path) -> str:
    path = vault / "Company_Handbook.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_dashboard(vault: Path) -> str:
    path = vault / "Dashboard.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_dropped_file(meta_path: Path, needs_action: Path) -> str:
    """Return up to MAX_FILE_CHARS of the original dropped file's content."""
    stem = meta_path.stem          # e.g. FILE_hackathon_brief
    # Find companion non-.md file (the actual dropped file)
    candidates = [
        f for f in needs_action.glob(f"{stem}.*")
        if f.suffix.lower() != ".md"
    ]
    if not candidates:
        return "[No companion file found in Needs_Action/]"

    actual = candidates[0]
    text_exts = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ".log", ".py", ".js", ".ts"}
    if actual.suffix.lower() in text_exts:
        try:
            content = actual.read_text(encoding="utf-8", errors="replace")
            if len(content) > MAX_FILE_CHARS:
                content = content[:MAX_FILE_CHARS] + "\n\n[... truncated ...]"
            return content
        except Exception as exc:
            return f"[Could not read file: {exc}]"
    else:
        size = actual.stat().st_size
        return f"[Binary/non-text file: {actual.name} — {size:,} bytes. Cannot display contents.]"


# ─── Audit Log ────────────────────────────────────────────────────────────────

def write_audit_log(logs_dir: Path, action_type: str,
                    file_name: str, result: str) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"
    entries: list = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            entries = []
    entries.append({
        "timestamp":   datetime.now().isoformat(),
        "action_type": action_type,
        "actor":       "process_vault",
        "file":        file_name,
        "result":      result,
    })
    log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                        encoding="utf-8")


# ─── Dashboard Update ─────────────────────────────────────────────────────────

def update_dashboard(vault: Path, entry: str) -> None:
    """Prepend a one-line activity entry under '## Recent Activity'."""
    dash = vault / "Dashboard.md"
    if not dash.exists():
        return
    text = dash.read_text(encoding="utf-8")
    marker = "## Recent Activity"
    if marker not in text:
        return
    idx  = text.index(marker) + len(marker)
    line = f"\n- {datetime.now().strftime('%Y-%m-%d %H:%M')} — {entry}"
    dash.write_text(text[:idx] + line + text[idx:], encoding="utf-8")


# ─── Claude Processing ────────────────────────────────────────────────────────

PROMPT_TEMPLATE = """\
You are an AI Employee operating under the rules in the Company Handbook.
A new file has been dropped into the vault's Inbox and queued for processing.

== COMPANY HANDBOOK ==
{handbook}

== FILE METADATA (from Needs_Action/) ==
{metadata}

== FILE CONTENTS ==
{file_content}

== YOUR TASK ==
Follow the SKILL_Process_File_Drop procedure:

1. Classify the file (document / text / spreadsheet / image / archive / unknown).
2. Check the handbook — does this file require human approval before action?
3. Generate a concise but complete Plan.md following SKILL_Generate_Plan schema.
4. Determine the summary action to record in logs and Dashboard.

Reply in EXACTLY this format (keep the delimiters):

---CLASSIFICATION---
file_type: <type>
category: <category>
---END_CLASSIFICATION---

---PLAN---
---
plan_id: PLAN_{slug}_{timestamp}
created: {now_iso}
triggered_by: Needs_Action/{meta_name}
status: pending
requires_approval: <true|false>
approval_items: []
skill_used: SKILL_Generate_Plan v1.0
---

# Plan: <Human-readable Title>

## Objective
<One sentence: what this plan achieves.>

## Context
- **Triggered by:** Needs_Action/{meta_name}
- **File type:** <type>
- **Handbook sections:** <list applicable sections>
- **Estimated steps:** <N>

## Steps

- [ ] Step 1: Read and summarise the file contents
- [ ] Step 2: <next specific action>
- [ ] Step N: Move metadata to /Done/

## Approval Required

<Yes / No — explain briefly if Yes>

## Completion Criteria

- [ ] All steps marked complete
- [ ] Metadata moved to /Done/ OR approval file created
- [ ] Dashboard.md updated
- [ ] Log entry written

## Notes

<Observations, flags, handbook references.>

---
*Generated by AI Employee | Skill: SKILL_Generate_Plan v1.0 | {now_str}*
---END_PLAN---

NEEDS_APPROVAL: <yes|no>
APPROVAL_REASON: <one sentence — why approval is needed, or "N/A">
SUMMARY: <one sentence activity log entry>
"""


def call_claude(client: anthropic.Anthropic,
                meta_path: Path, needs_action: Path, vault: Path) -> dict:
    """Send metadata + file to Claude and parse the structured response."""
    metadata     = meta_path.read_text(encoding="utf-8")
    file_content = read_dropped_file(meta_path, needs_action)
    handbook     = read_handbook(vault)
    now          = datetime.now()

    prompt = PROMPT_TEMPLATE.format(
        handbook     = handbook,
        metadata     = metadata,
        file_content = file_content,
        slug         = meta_path.stem.replace("FILE_", "").lower(),
        timestamp    = now.strftime("%Y%m%d_%H%M%S"),
        now_iso      = now.isoformat(),
        now_str      = now.strftime("%Y-%m-%d %H:%M:%S"),
        meta_name    = meta_path.name,
    )

    msg = client.messages.create(
        model      = MODEL,
        max_tokens = 2048,
        messages   = [{"role": "user", "content": prompt}],
    )
    return parse_response(msg.content[0].text, meta_path, now)


def parse_response(text: str, meta_path: Path, now: datetime) -> dict:
    """Extract plan content, approval flag, and summary from Claude's reply."""
    result = {
        "plan_content":    None,
        "needs_approval":  False,
        "approval_reason": "N/A",
        "summary":         f"Processed {meta_path.name}",
    }

    # Extract plan block
    if "---PLAN---" in text and "---END_PLAN---" in text:
        s = text.index("---PLAN---") + len("---PLAN---")
        e = text.index("---END_PLAN---")
        result["plan_content"] = text[s:e].strip()

    # Parse trailing fields
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("NEEDS_APPROVAL:"):
            result["needs_approval"] = "yes" in line.lower()
        elif line.startswith("APPROVAL_REASON:"):
            result["approval_reason"] = line.split(":", 1)[1].strip()
        elif line.startswith("SUMMARY:"):
            result["summary"] = line.split(":", 1)[1].strip()

    return result


# ─── File Processor ───────────────────────────────────────────────────────────

def process_one(meta_path: Path, vault: Path,
                client: anthropic.Anthropic, dry_run: bool) -> bool:
    """Process a single FILE_*.md. Returns True on success."""
    needs_action    = vault / "Needs_Action"
    plans_dir       = vault / "Plans"
    done_dir        = vault / "Done"
    pending_dir     = vault / "Pending_Approval"
    logs_dir        = vault / "Logs"

    plans_dir.mkdir(parents=True, exist_ok=True)
    done_dir.mkdir(parents=True, exist_ok=True)
    pending_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[PROCESSING] {meta_path.name}")

    try:
        result = call_claude(client, meta_path, needs_action, vault)
    except Exception as exc:
        print(f"  [ERROR] Claude API call failed: {exc}")
        write_audit_log(logs_dir, "file_drop_processed",
                        meta_path.name, f"error: {exc}")
        return False

    # Build plan filename
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem      = meta_path.stem.replace("FILE_", "")
    plan_name = f"PLAN_{stem}_{ts}.md"
    plan_path = plans_dir / plan_name

    if dry_run:
        print(f"  [DRY-RUN] Would write: Plans/{plan_name}")
        print(f"  [DRY-RUN] needs_approval={result['needs_approval']}")
        print(f"  [DRY-RUN] summary: {result['summary']}")
        return True

    # Write plan
    plan_content = result["plan_content"] or (
        f"# Plan: {stem}\n\n*Auto-generated — Claude response parsing failed.*\n"
    )
    plan_path.write_text(plan_content, encoding="utf-8")
    print(f"  [OK] Plan created : Plans/{plan_name}")

    if result["needs_approval"]:
        # Create approval request
        approval_name = f"APPROVAL_{stem}_{ts}.md"
        approval_path = pending_dir / approval_name
        approval_path.write_text(textwrap.dedent(f"""\
            ---
            type: approval_request
            file: {meta_path.name}
            plan: Plans/{plan_name}
            reason: {result["approval_reason"]}
            created: {datetime.now().isoformat()}
            expires: {datetime.now().isoformat()}
            status: pending
            ---

            # Approval Required: {stem}

            **File:** `{meta_path.name}`
            **Plan:** `Plans/{plan_name}`
            **Reason:** {result["approval_reason"]}

            ## To APPROVE
            Move this file to: `/Approved/`

            ## To REJECT
            Move this file to: `/Rejected/`
        """), encoding="utf-8")
        print(f"  [APPROVAL] Request created: Pending_Approval/{approval_name}")
        write_audit_log(logs_dir, "file_drop_processed",
                        meta_path.name, "approval_required")
        update_dashboard(vault, f"APPROVAL NEEDED — {stem}: {result['approval_reason']}")
    else:
        # Move metadata to Done
        done_path = done_dir / meta_path.name
        shutil.move(str(meta_path), str(done_path))
        print(f"  [OK] Moved to Done/: {meta_path.name}")
        write_audit_log(logs_dir, "file_drop_processed",
                        meta_path.name, "completed")
        update_dashboard(vault, result["summary"])

    print(f"  [OK] {result['summary']}")
    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process pending files in AI Employee Vault Needs_Action/"
    )
    parser.add_argument("--vault",   default=str(DEFAULT_VAULT),
                        help="Path to AI_Employee_Vault (default: ./AI_Employee_Vault)")
    parser.add_argument("--file",    default=None,
                        help="Process only this specific FILE_*.md (filename only)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would happen without making changes")
    args = parser.parse_args()

    vault        = Path(args.vault).resolve()
    needs_action = vault / "Needs_Action"

    if not vault.exists():
        print(f"[ERROR] Vault not found: {vault}")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY environment variable is not set.")
        print("        Set it with: set ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Discover pending files
    if args.file:
        pending = [needs_action / args.file]
        if not pending[0].exists():
            print(f"[ERROR] File not found: {pending[0]}")
            sys.exit(1)
    else:
        pending = sorted(needs_action.glob("FILE_*.md"))

    if not pending:
        print("[INFO] No pending FILE_*.md files found in Needs_Action/")
        print(f"       Vault: {vault}")
        return

    print(f"[INFO] Vault       : {vault}")
    print(f"[INFO] Pending     : {len(pending)} file(s)")
    if args.dry_run:
        print("[INFO] Mode        : DRY-RUN (no changes will be made)")

    ok = fail = 0
    for meta_path in pending:
        if process_one(meta_path, vault, client, args.dry_run):
            ok += 1
        else:
            fail += 1

    print(f"\n[DONE] Processed {ok} file(s) successfully, {fail} failed.")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
