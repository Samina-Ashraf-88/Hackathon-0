"""
gmail_watcher.py — Monitors Gmail (apple379tree@gmail.com) for new important emails
and creates action files in the AI Employee Vault.

Authentication: Google OAuth 2.0 via credentials.json (client secret file).
Token is cached locally in token.json after first auth.

Setup:
    1. Place your client_secret_*.json file in the project root.
    2. Run once interactively: python gmail_watcher.py --auth
    3. After auth, run normally: python gmail_watcher.py

Dependencies:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
"""

import os
import sys
import argparse
import json
import re
import base64
from pathlib import Path
from datetime import datetime

# Add parent directory for base_watcher import
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Missing Google API libraries. Run:")
    print("  pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    sys.exit(1)

# Gmail API scopes required
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",  # For marking as read
]

# Path to credentials and token files
PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "token.json"
VAULT_PATH = PROJECT_ROOT / "AI_Employee_Vault"

# Email address being monitored
MONITORED_EMAIL = "apple379tree@gmail.com"


class GmailWatcher(BaseWatcher):
    """
    Watches Gmail for new important/unread emails and writes
    structured .md action files to the vault's /Needs_Action/ folder.
    """

    def __init__(
        self,
        vault_path: str = str(VAULT_PATH),
        credentials_path: str = str(CREDENTIALS_PATH),
        token_path: str = str(TOKEN_PATH),
        check_interval: int = 120,
    ):
        super().__init__(vault_path, check_interval)
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.service = None
        self.processed_ids: set = self._load_processed_ids()

    def _load_processed_ids(self) -> set:
        """Load previously processed message IDs to avoid duplicates."""
        state_file = self.vault_path / ".gmail_processed.json"
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    return set(json.load(f))
            except Exception:
                return set()
        return set()

    def _save_processed_ids(self) -> None:
        state_file = self.vault_path / ".gmail_processed.json"
        # Keep only last 1000 IDs to avoid unbounded growth
        ids_list = list(self.processed_ids)[-1000:]
        with open(state_file, "w") as f:
            json.dump(ids_list, f)

    def authenticate(self) -> bool:
        """
        Authenticate with Google OAuth 2.0.
        On first run, opens browser for user consent.
        Subsequent runs use cached token.json.
        """
        creds = None

        # Load existing token
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(self.token_path), SCOPES
                )
            except Exception as e:
                self.logger.warning(f"Could not load token: {e}")

        # Refresh or re-authenticate if needed
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.logger.info("Token refreshed successfully.")
                except Exception as e:
                    self.logger.warning(f"Token refresh failed: {e}. Re-authenticating.")
                    creds = None

            if not creds:
                if not self.credentials_path.exists():
                    self.logger.error(
                        f"credentials.json not found at {self.credentials_path}. "
                        "Download it from Google Cloud Console."
                    )
                    return False

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
                self.logger.info("Authentication successful.")

            # Save token for future use
            with open(self.token_path, "w") as f:
                f.write(creds.to_json())
            self.logger.info(f"Token saved to {self.token_path}")

        try:
            self.service = build("gmail", "v1", credentials=creds)
            self.logger.info(f"Gmail service connected for {MONITORED_EMAIL}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to build Gmail service: {e}")
            return False

    def _get_email_body(self, payload: dict) -> str:
        """Recursively extract plain text body from Gmail message payload."""
        body = ""

        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                body = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        elif "parts" in payload:
            for part in payload["parts"]:
                body = self._get_email_body(part)
                if body:
                    break

        return body.strip()

    def _classify_priority(self, subject: str, body: str, labels: list) -> str:
        """Classify email priority based on content and labels."""
        subject_lower = subject.lower()
        body_lower = body.lower()

        if "IMPORTANT" in labels or "STARRED" in labels:
            return "high"

        high_keywords = [
            "urgent", "asap", "immediately", "invoice", "payment",
            "deadline", "critical", "action required", "contract",
        ]
        if any(kw in subject_lower or kw in body_lower for kw in high_keywords):
            return "high"

        low_keywords = ["unsubscribe", "newsletter", "noreply", "no-reply", "promotion"]
        if any(kw in subject_lower or kw in body_lower for kw in low_keywords):
            return "low"

        return "normal"

    def check_for_updates(self) -> list:
        """Fetch unread important emails not yet processed."""
        if not self.service:
            if not self.authenticate():
                return []

        try:
            # Query: unread emails in inbox or important
            results = self.service.users().messages().list(
                userId="me",
                q="is:unread (is:important OR label:inbox)",
                maxResults=20,
            ).execute()

            messages = results.get("messages", [])
            new_messages = [m for m in messages if m["id"] not in self.processed_ids]
            return new_messages

        except HttpError as e:
            self.logger.error(f"Gmail API error: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching emails: {e}")
            return []

    def create_action_file(self, message: dict) -> Path:
        """Fetch full email and write a structured .md action file."""
        msg_id = message["id"]

        try:
            msg = self.service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except HttpError as e:
            self.logger.error(f"Failed to fetch message {msg_id}: {e}")
            raise

        # Extract headers
        headers = {
            h["name"]: h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }

        sender = headers.get("From", "Unknown Sender")
        subject = headers.get("Subject", "No Subject")
        date_str = headers.get("Date", datetime.now().isoformat())
        labels = msg.get("labelIds", [])

        # Extract body
        body = self._get_email_body(msg.get("payload", {}))
        snippet = msg.get("snippet", "")

        # Use body if available, otherwise snippet (truncated to 500 chars)
        email_content = body[:1000] if body else snippet[:500]

        # Sanitize for filename
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", msg_id)
        priority = self._classify_priority(subject, email_content, labels)

        content = f"""---
type: email
message_id: {msg_id}
from: {sender}
subject: {subject}
received: {datetime.now().isoformat()}
date_header: {date_str}
priority: {priority}
status: pending
labels: {', '.join(labels)}
---

## Email Content

{email_content}

## Suggested Actions
- [ ] Review email content
- [ ] Draft reply if needed
- [ ] Execute SKILL_Process_Gmail for full processing
"""

        filepath = self.needs_action / f"EMAIL_{safe_id}.md"
        filepath.write_text(content, encoding="utf-8")

        # Mark as processed (do NOT mark as read yet — human should confirm)
        self.processed_ids.add(msg_id)
        self._save_processed_ids()

        self.write_action_log({
            "action_type": "email_detected",
            "from": sender,
            "subject": subject,
            "priority": priority,
            "file": filepath.name,
        })

        return filepath


def main():
    parser = argparse.ArgumentParser(description="Gmail Watcher for AI Employee")
    parser.add_argument(
        "--auth", action="store_true",
        help="Run OAuth authentication flow interactively"
    )
    parser.add_argument(
        "--vault", default=str(VAULT_PATH),
        help="Path to Obsidian vault"
    )
    parser.add_argument(
        "--interval", type=int, default=120,
        help="Check interval in seconds (default: 120)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run check once and exit (for testing)"
    )
    args = parser.parse_args()

    watcher = GmailWatcher(
        vault_path=args.vault,
        check_interval=args.interval,
    )

    if args.auth:
        print("Starting Gmail OAuth authentication...")
        success = watcher.authenticate()
        if success:
            print("Authentication successful! token.json saved.")
        else:
            print("Authentication failed. Check credentials.json path.")
        sys.exit(0 if success else 1)

    # Authenticate before starting
    if not watcher.authenticate():
        print("Authentication failed. Run: python gmail_watcher.py --auth")
        sys.exit(1)

    if args.once:
        items = watcher.check_for_updates()
        print(f"Found {len(items)} new email(s)")
        for item in items:
            path = watcher.create_action_file(item)
            print(f"  Created: {path}")
        sys.exit(0)

    # Run the continuous loop
    watcher.run()


if __name__ == "__main__":
    main()
