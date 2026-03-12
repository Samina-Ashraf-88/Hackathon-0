"""
audit_logger.py — Gold Tier Centralized Audit Logger

Standalone module used by all watchers and MCP callers to write
standardized JSON audit log entries to /Vault/Logs/YYYY-MM-DD.json.

Also provides log rotation and weekly summary helpers.

Usage:
    from audit_logger import AuditLogger
    log = AuditLogger(vault_path)
    log.write(action_type="email_send", component="email-mcp", target="client@example.com",
              result="success", approval_status="approved")
"""

import json
import uuid
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


class AuditLogger:
    """
    Writes structured JSON audit entries to /Logs/YYYY-MM-DD.json.

    Log retention: 90 days on disk, older files moved to /Logs/Archive/.
    """

    SCHEMA_VERSION = "1.0"
    RETENTION_DAYS = 90

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.logs_dir = self.vault_path / "Logs"
        self.archive_dir = self.logs_dir / "Archive"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    @property
    def _today_log(self) -> Path:
        return self.logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"

    def write(
        self,
        action_type: str,
        component: str = "vault",
        skill_invoked: str = "",
        target: str = "",
        parameters: Optional[dict] = None,
        approval_status: str = "not_required",
        approved_by: Optional[str] = None,
        result: str = "success",
        error_details: Optional[str] = None,
        source_file: str = "",
        output_file: str = "",
        actor: str = "claude_code",
        **extra
    ) -> str:
        """
        Write a log entry. Returns the log_id for cross-referencing.

        Args:
            action_type:       What type of action (see SKILL_Audit_Logging.md)
            component:         Which server/component performed the action
            skill_invoked:     Name of the SKILL_*.md that triggered this
            target:            Sanitized target (email domain, username, invoice_id)
            parameters:        Key params (NO secrets, NO tokens)
            approval_status:   auto | pending | approved | rejected | not_required
            approved_by:       "human" | "system_alert" | None
            result:            success | failure | queued | skipped
            error_details:     Error message if result=failure
            source_file:       Triggering /Needs_Action/ file
            output_file:       Resulting /Done/ or /Pending_Approval/ file
            actor:             Who performed the action
        """
        log_id = str(uuid.uuid4())

        entry = {
            "schema_version": self.SCHEMA_VERSION,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "log_id": log_id,
            "action_type": action_type,
            "actor": actor,
            "component": component,
            "skill_invoked": skill_invoked,
            "target": self._sanitize_target(target),
            "parameters": self._sanitize_params(parameters or {}),
            "approval_status": approval_status,
            "approved_by": approved_by,
            "result": result,
            "error_details": error_details[:500] if error_details else None,
            "dry_run": self.dry_run,
            "source_file": source_file,
            "output_file": output_file,
            **extra
        }

        if not self.dry_run:
            self._append_entry(entry)
        else:
            # Still write in dry run — logging is always on
            entry["_dry_run_note"] = "Action not executed, only logged"
            self._append_entry(entry)

        return log_id

    def _append_entry(self, entry: dict) -> None:
        """Append entry to today's log file (thread-safe-ish via read-modify-write)."""
        log_file = self._today_log
        entries = []

        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    entries = json.load(f)
            except (json.JSONDecodeError, IOError):
                entries = []

        entries.append(entry)

        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

    def _sanitize_target(self, target: str) -> str:
        """Sanitize sensitive targets for logging."""
        if not target:
            return ""
        # If it looks like an email address, log domain only for privacy
        if "@" in target and "." in target.split("@")[-1]:
            parts = target.split("@")
            return f"...@{parts[-1]}"
        return str(target)[:100]

    def _sanitize_params(self, params: dict) -> dict:
        """Remove sensitive keys from parameters before logging."""
        SENSITIVE_KEYS = {
            "password", "token", "secret", "api_key", "credential",
            "cookie", "session", "auth", "key", "access_token", "refresh_token"
        }
        safe = {}
        for k, v in params.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                safe[k] = "[REDACTED]"
            elif isinstance(v, str) and len(v) > 200:
                safe[k] = v[:200] + "...[truncated]"
            else:
                safe[k] = v
        return safe

    def get_week_summary(self, days_back: int = 7) -> dict:
        """
        Aggregate log entries for the last N days.
        Returns dict with counts by action_type.
        Used by SKILL_Weekly_CEO_Briefing.
        """
        summary = {
            "emails_sent": 0,
            "social_posts": 0,
            "social_replies": 0,
            "social_leads": 0,
            "tasks_completed": 0,
            "approvals_granted": 0,
            "approvals_rejected": 0,
            "errors": 0,
            "odoo_reads": 0,
            "odoo_writes": 0,
            "system_events": 0,
            "by_platform": {"facebook": 0, "instagram": 0, "twitter": 0},
            "period_days": days_back
        }

        for i in range(days_back):
            day = datetime.now() - timedelta(days=i)
            log_file = self.logs_dir / f"{day.strftime('%Y-%m-%d')}.json"
            if not log_file.exists():
                continue

            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    entries = json.load(f)
            except Exception:
                continue

            for entry in entries:
                atype = entry.get("action_type", "")
                result = entry.get("result", "success")

                if atype == "email_send":
                    summary["emails_sent"] += 1
                elif atype == "social_post":
                    summary["social_posts"] += 1
                    comp = entry.get("component", "")
                    for platform in ["facebook", "instagram", "twitter"]:
                        if platform in comp:
                            summary["by_platform"][platform] += 1
                elif atype in ("social_reply", "social_dm"):
                    summary["social_replies"] += 1
                elif atype == "social_lead_identified":
                    summary["social_leads"] += 1
                elif atype == "task_completed":
                    summary["tasks_completed"] += 1
                elif atype == "approval_granted":
                    summary["approvals_granted"] += 1
                elif atype == "approval_rejected":
                    summary["approvals_rejected"] += 1
                elif atype == "error" or result == "failure":
                    summary["errors"] += 1
                elif atype == "odoo_read":
                    summary["odoo_reads"] += 1
                elif atype in ("odoo_create", "odoo_payment"):
                    summary["odoo_writes"] += 1
                elif atype == "system_event":
                    summary["system_events"] += 1

        return summary

    def rotate_old_logs(self) -> None:
        """Move logs older than RETENTION_DAYS to Archive folder."""
        cutoff = datetime.now() - timedelta(days=self.RETENTION_DAYS)

        for log_file in self.logs_dir.glob("*.json"):
            try:
                # Parse date from filename YYYY-MM-DD.json
                date_str = log_file.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    month_dir = self.archive_dir / file_date.strftime("%Y-%m")
                    month_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(log_file), str(month_dir / log_file.name))
            except (ValueError, Exception):
                continue  # Skip non-date files


# ── Convenience function ───────────────────────────────────────────────────────
def get_logger(vault_path: str) -> AuditLogger:
    """Get an AuditLogger instance."""
    return AuditLogger(vault_path)
