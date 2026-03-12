"""
facebook_watcher.py — Facebook Watcher for AI Employee Gold Tier

Polls the facebook-mcp server for new messages and comments on
Samina Ashraf's Facebook profile/page and creates action files in
/Needs_Action/ for Claude to process.

Accounts:
  Profile: https://www.facebook.com/profile.php?id=61586406776621

Run:
  python facebook_watcher.py

Environment:
  VAULT_PATH          — path to AI_Employee_Vault
  FACEBOOK_MCP_URL    — http://localhost:3001
  MCP_SECRET          — shared bearer secret
  CHECK_INTERVAL      — seconds between polls (default 300)
  DRY_RUN             — "true" for safe mode
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

VAULT_PATH = os.getenv("VAULT_PATH", str(Path(__file__).parent.parent / "AI_Employee_Vault"))
MCP_URL = os.getenv("FACEBOOK_MCP_URL", "http://localhost:3001")
MCP_SECRET = os.getenv("MCP_SECRET", "dev-secret-change-me")
CHECK_INTERVAL = int(os.getenv("FACEBOOK_CHECK_INTERVAL", "300"))
PROFILE_URL = "https://www.facebook.com/profile.php?id=61586406776621"

LEAD_KEYWORDS = [
    "price", "cost", "how much", "services", "help", "interested",
    "automate", "ai", "consulting", "hire", "quote", "available",
    "package", "offer", "discount", "demo", "schedule", "call"
]


class FacebookWatcher(BaseWatcher):
    """
    Polls facebook-mcp for new messages and comments.
    Creates /Needs_Action/FACEBOOK_*.md files for Claude.
    """

    def __init__(self):
        super().__init__(vault_path=VAULT_PATH, check_interval=CHECK_INTERVAL)
        self.processed_ids: set = self._load_processed_ids()
        self.headers = {"Authorization": f"Bearer {MCP_SECRET}"}

    def _processed_ids_file(self) -> Path:
        return Path(__file__).parent / ".facebook_processed.json"

    def _load_processed_ids(self) -> set:
        f = self._processed_ids_file()
        if f.exists():
            try:
                return set(json.loads(f.read_text()))
            except Exception:
                return set()
        return set()

    def _save_processed_ids(self) -> None:
        ids = list(self.processed_ids)[-2000:]  # keep last 2000
        self._processed_ids_file().write_text(json.dumps(ids))

    def _mcp_get(self, endpoint: str) -> dict:
        """Call GET on facebook-mcp."""
        try:
            resp = requests.get(f"{MCP_URL}{endpoint}", headers=self.headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            self.logger.warning(f"facebook-mcp not reachable at {MCP_URL}")
            return {}
        except Exception as e:
            self.logger.error(f"facebook-mcp GET {endpoint} failed: {e}")
            return {}

    def _classify(self, text: str) -> str:
        """Classify message/comment as lead, support, spam, or engagement."""
        text_lower = text.lower()
        if any(kw in text_lower for kw in LEAD_KEYWORDS):
            return "lead"
        if any(kw in text_lower for kw in ["help", "issue", "problem", "not working", "broken"]):
            return "support"
        if len(text) < 5 or text_lower in ["ok", "nice", "great", "wow", "😊", "👍"]:
            return "engagement"
        return "general"

    def check_for_updates(self) -> list:
        """Check facebook-mcp for new messages and comments."""
        items = []

        # Fetch messages
        msg_data = self._mcp_get("/messages")
        for msg in msg_data.get("messages", []):
            msg_id = msg.get("id", f"fb_msg_{time.time_ns()}")
            if msg_id not in self.processed_ids:
                msg["_item_id"] = msg_id
                msg["_item_type"] = "message"
                items.append(msg)

        # Fetch comments
        cmt_data = self._mcp_get("/comments")
        for cmt in cmt_data.get("comments", []):
            cmt_id = cmt.get("id", f"fb_cmt_{time.time_ns()}")
            if cmt_id not in self.processed_ids:
                cmt["_item_id"] = cmt_id
                cmt["_item_type"] = "comment"
                items.append(cmt)

        return items

    def create_action_file(self, item: dict) -> Path:
        """Create a /Needs_Action/FACEBOOK_*.md file."""
        item_id = item.get("_item_id", f"unknown_{time.time_ns()}")
        item_type = item.get("_item_type", "message")
        sender = item.get("from", item.get("sender", {}).get("name", "Unknown"))
        text = item.get("message", item.get("text", ""))
        post_id = item.get("post_id", "")
        timestamp = item.get("created_time", datetime.now().isoformat())
        classification = self._classify(text)

        safe_sender = "".join(c if c.isalnum() else "_" for c in str(sender))[:30]
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"FACEBOOK_{item_type.upper()}_{safe_sender}_{date_str}.md"
        filepath = self.needs_action / filename

        content = f"""---
type: facebook_{item_type}
platform: facebook
from: "{sender}"
item_id: "{item_id}"
post_id: "{post_id}"
profile_url: "{PROFILE_URL}"
received: "{timestamp}"
classification: "{classification}"
priority: {"high" if classification == "lead" else "normal"}
status: pending
---

## Facebook {item_type.title()} from {sender}

**From:** {sender}
**Classification:** {classification.upper()}
**Original Post ID:** {post_id or "N/A"}

### Content
{text}

## Suggested Actions
- [ ] Review and classify
- [ ] Draft reply if needed (create /Pending_Approval/ file)
- [ ] Log action
- [ ] Move to /Done/

{"## LEAD ALERT\nThis message contains buying signals. Create a lead note in /Plans/" if classification == "lead" else ""}
"""

        filepath.write_text(content, encoding="utf-8")
        self.processed_ids.add(item_id)
        self._save_processed_ids()

        self.write_action_log({
            "action_type": "facebook_item_detected",
            "platform": "facebook",
            "item_type": item_type,
            "classification": classification,
            "from": sender,
            "file": filename
        })

        self.logger.info(f"Created: {filename} (type={item_type}, class={classification})")
        return filepath


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Facebook Watcher for AI Employee Gold Tier")
    parser.add_argument("--health", action="store_true", help="Check facebook-mcp health and exit")
    args = parser.parse_args()

    if args.health:
        try:
            resp = requests.get(f"{MCP_URL}/health", timeout=5)
            print(json.dumps(resp.json(), indent=2))
        except Exception as e:
            print(f"ERROR: facebook-mcp unreachable: {e}")
        return

    watcher = FacebookWatcher()
    watcher.run()


if __name__ == "__main__":
    main()
