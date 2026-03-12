"""
retry_handler.py — Gold Tier Error Recovery & Retry Utilities

Provides:
  - @with_retry decorator for exponential backoff
  - RetryHandler class for stateful retry tracking
  - Graceful degradation helpers (queue, alert, degrade)
  - Error categorization

Used by all watchers and orchestrator.
"""

import time
import logging
import json
import functools
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Callable, Optional, Any

logger = logging.getLogger("retry_handler")


class ErrorCategory(Enum):
    TRANSIENT = "transient"          # Network blip, rate limit → auto-retry
    AUTH = "auth"                    # Token expired → alert human, stop
    LOGIC = "logic"                  # Bad data / logic error → quarantine
    DATA = "data"                    # Corrupted file, missing field → quarantine
    MCP_DOWN = "mcp_down"            # MCP server unreachable → queue + restart
    SYSTEM = "system"                # Process crash → watchdog handles
    EXTERNAL_BLOCK = "external"      # Platform blocked → manual required
    ODOO = "odoo"                    # Odoo error → alert human for writes


class TransientError(Exception):
    """Errors that should be retried automatically."""
    pass


class AuthError(Exception):
    """Authentication failures — stop and alert human."""
    pass


class MCPDownError(Exception):
    """MCP server unreachable."""
    pass


def categorize_error(exception: Exception) -> ErrorCategory:
    """Classify an exception into an ErrorCategory."""
    msg = str(exception).lower()

    if any(kw in msg for kw in ["timeout", "rate limit", "too many requests", "503", "429"]):
        return ErrorCategory.TRANSIENT
    if any(kw in msg for kw in ["401", "403", "unauthorized", "token", "session", "cookie"]):
        return ErrorCategory.AUTH
    if any(kw in msg for kw in ["connection refused", "cannot connect", "mcp"]):
        return ErrorCategory.MCP_DOWN
    if any(kw in msg for kw in ["odoo", "json-rpc", "xmlrpc"]):
        return ErrorCategory.ODOO
    if any(kw in msg for kw in ["blocked", "suspended", "captcha"]):
        return ErrorCategory.EXTERNAL_BLOCK
    if any(kw in msg for kw in ["decode", "parse", "corrupt", "missing field"]):
        return ErrorCategory.DATA
    return ErrorCategory.TRANSIENT  # default: assume transient


def with_retry(max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 60.0,
               exceptions: tuple = (TransientError, Exception)):
    """
    Decorator: retry a function with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        exceptions: Exception types to retry on

    Usage:
        @with_retry(max_attempts=3, base_delay=2.0)
        def send_email(to, body):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except AuthError:
                    # Never retry auth errors
                    raise
                except exceptions as e:
                    last_exception = e
                    category = categorize_error(e)

                    if category == ErrorCategory.AUTH:
                        raise AuthError(str(e)) from e

                    if attempt < max_attempts:
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                        logger.warning(
                            f"[{func.__name__}] Attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"[{func.__name__}] All {max_attempts} attempts failed. Last error: {e}"
                        )
            raise last_exception
        return wrapper
    return decorator


class RetryHandler:
    """
    Stateful retry handler for tracking per-component failure counts
    and applying the Gold Tier error escalation matrix.
    """

    def __init__(self, vault_path: str, component: str):
        self.vault_path = Path(vault_path)
        self.component = component
        self.state_file = Path(__file__).parent / f".retry_state_{component}.json"
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except Exception:
                pass
        return {"failure_count": 0, "last_failure": None, "status": "healthy"}

    def _save_state(self) -> None:
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def record_failure(self, error: Exception, action: str = "") -> ErrorCategory:
        """Record a failure, increment counter, return category."""
        category = categorize_error(error)
        self.state["failure_count"] += 1
        self.state["last_failure"] = datetime.now().isoformat()
        self.state["last_error"] = str(error)[:200]
        self.state["last_action"] = action
        self.state["status"] = "degraded"
        self._save_state()

        logger.warning(
            f"[{self.component}] Failure #{self.state['failure_count']} "
            f"({category.value}): {str(error)[:100]}"
        )
        return category

    def record_success(self) -> None:
        """Reset failure counter on success."""
        if self.state["failure_count"] > 0:
            logger.info(f"[{self.component}] Recovered after {self.state['failure_count']} failures")
        self.state = {"failure_count": 0, "last_failure": None, "status": "healthy"}
        self._save_state()

    @property
    def failure_count(self) -> int:
        return self.state.get("failure_count", 0)

    @property
    def is_healthy(self) -> bool:
        return self.state.get("status") == "healthy"

    def should_escalate(self) -> bool:
        """Returns True if failures have crossed the escalation threshold (3+)."""
        return self.failure_count >= 3

    def create_system_error_file(self, error: Exception, action: str = "") -> Optional[Path]:
        """
        Write a SYSTEM_ERROR_*.md to /Needs_Action/ for Claude to process.
        Claude will invoke SKILL_Error_Recovery_Graceful_Degradation.
        """
        category = categorize_error(error)
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SYSTEM_ERROR_{self.component.upper()}_{date_str}.md"
        filepath = self.vault_path / "Needs_Action" / filename

        content = f"""---
type: system_error
component: "{self.component}"
error_category: "{category.value}"
failure_count: {self.failure_count}
action_attempted: "{action}"
timestamp: "{datetime.now().isoformat()}"
status: pending
priority: high
---

## System Error — {self.component}

**Category:** {category.value.upper()}
**Failures:** {self.failure_count}
**Last Action:** {action or "N/A"}
**Error:** {str(error)[:500]}

## Required Response (SKILL_Error_Recovery_Graceful_Degradation)
- **Transient/MCP_Down:** Queue work, attempt restart, alert if persistent
- **Auth:** STOP all operations for this component, alert human immediately
- **External_Block:** Mark platform as blocked, queue for manual posting
- **Odoo:** HALT all write operations, alert human

## Recovery Steps
1. Read error category: `{category.value}`
2. Apply recovery strategy from SKILL_Error_Recovery_Graceful_Degradation
3. Update Dashboard.md with component status
4. Log recovery action
"""

        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Created system error file: {filename}")
        return filepath

    def queue_action(self, action_type: str, params: dict) -> Path:
        """
        Queue a failed action to /Plans/QUEUED_ACTIONS.md for later retry.
        """
        queue_file = self.vault_path / "Plans" / "QUEUED_ACTIONS.md"
        queue_file.parent.mkdir(parents=True, exist_ok=True)

        entries = []
        if queue_file.exists():
            content = queue_file.read_text(encoding="utf-8")
            # Simple append approach
        else:
            content = "# Queued Actions\n\nActions queued due to MCP server unavailability.\n\n"

        entry = (
            f"\n## {action_type} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- **Component:** {self.component}\n"
            f"- **Action:** {action_type}\n"
            f"- **Params:** {json.dumps(params)}\n"
            f"- **Status:** queued\n"
        )
        queue_file.write_text(content + entry, encoding="utf-8")
        logger.info(f"Queued action: {action_type}")
        return queue_file
