"""
instagram_watcher.py — Instagram Watcher for AI Employee Gold Tier

Polls the instagram-mcp server for new DMs and comments on
Samina Ashraf's Instagram account (@apple379tree) and creates
action files in /Needs_Action/ for Claude to process.

Account: https://www.instagram.com/apple379tree/

Run:
  python instagram_watcher.py

Environment:
  VAULT_PATH           — path to AI_Employee_Vault
  INSTAGRAM_MCP_URL    — http://localhost:3002
  MCP_SECRET           — shared bearer secret
  CHECK_INTERVAL       — seconds between polls (default 300)
  DRY_RUN              — "true" for safe mode
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
MCP_URL = os.getenv("INSTAGRAM_MCP_URL", "http://localhost:3002")
MCP_SECRET = os.getenv("MCP_SECRET", "dev-secret-change-me")
CHECK_INTERVAL = int(os.getenv("INSTAGRAM_CHECK_INTERVAL", "300"))
INSTAGRAM_USERNAME = "apple379tree"
INSTAGRAM_URL = f"https://www.instagram.com/{INSTAGRAM_USERNAME}/"

LEAD_KEYWORDS = [
    "price", "cost", "how much", "service", "help", "interested",
    "automate", "ai", "hire", "quote", "available", "collab",
    "work together", "dm me", "dm", "contact", "whatsapp"
]

HASHTAGS_FOR_AI_POSTS = (
    "#AIEmployee #BusinessAutomation #ClaudeAI #SmallBusiness "
    "#AI2026 #AITools #Productivity #Entrepreneur"
)


class InstagramWatcher(BaseWatcher):
    """
    Polls instagram-mcp for new DMs and comments.
    Creates /Needs_Action/INSTAGRAM_*.md files for Claude.
    """

    def __init__(self):
        super().__init__(vault_path=VAULT_PATH, check_interval=CHECK_INTERVAL)
        self.processed_ids: set = self._load_processed_ids()
        self.headers = {"Authorization": f"Bearer {MCP_SECRET}"}

    def _processed_ids_file(self) -> Path:
        return Path(__file__).parent / ".instagram_processed.json"

    def _load_processed_ids(self) -> set:
        f = self._processed_ids_file()
        if f.exists():
            try:
                return set(json.loads(f.read_text()))
            except Exception:
                return set()
        return set()

    def _save_processed_ids(self) -> None:
        ids = list(self.processed_ids)[-2000:]
        self._processed_ids_file().write_text(json.dumps(ids))

    def _mcp_get(self, endpoint: str) -> dict:
        try:
            resp = requests.get(f"{MCP_URL}{endpoint}", headers=self.headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            self.logger.warning(f"instagram-mcp not reachable at {MCP_URL}")
            return {}
        except Exception as e:
            self.logger.error(f"instagram-mcp GET {endpoint} failed: {e}")
            return {}

    def _classify(self, text: str) -> str:
        text_lower = text.lower()
        if any(kw in text_lower for kw in LEAD_KEYWORDS):
            return "lead"
        if any(kw in text_lower for kw in ["thank", "love", "amazing", "❤️", "🔥", "🙌"]):
            return "engagement"
        if any(kw in text_lower for kw in ["help", "issue", "not work", "broken", "error"]):
            return "support"
        return "general"

    def check_for_updates(self) -> list:
        items = []

        dms = self._mcp_get("/messages")
        for dm in dms.get("messages", []):
            dm_id = dm.get("id", f"ig_dm_{time.time_ns()}")
            if dm_id not in self.processed_ids:
                dm["_item_id"] = dm_id
                dm["_item_type"] = "dm"
                items.append(dm)

        comments = self._mcp_get("/comments")
        for cmt in comments.get("comments", []):
            cmt_id = cmt.get("id", f"ig_cmt_{time.time_ns()}")
            if cmt_id not in self.processed_ids:
                cmt["_item_id"] = cmt_id
                cmt["_item_type"] = "comment"
                items.append(cmt)

        return items

    def create_action_file(self, item: dict) -> Path:
        item_id = item.get("_item_id", f"unknown_{time.time_ns()}")
        item_type = item.get("_item_type", "dm")
        sender = item.get("from", item.get("username", "Unknown"))
        text = item.get("text", item.get("message", ""))
        media_id = item.get("media_id", "")
        timestamp = item.get("timestamp", datetime.now().isoformat())
        classification = self._classify(text)

        safe_sender = "".join(c if c.isalnum() else "_" for c in str(sender))[:30]
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"INSTAGRAM_{item_type.upper()}_{safe_sender}_{date_str}.md"
        filepath = self.needs_action / filename

        # Build hashtag suggestion for replies
        hashtag_suggestion = HASHTAGS_FOR_AI_POSTS if classification == "lead" else ""

        content = f"""---
type: instagram_{item_type}
platform: instagram
username: "{INSTAGRAM_USERNAME}"
from: "@{sender}"
item_id: "{item_id}"
media_id: "{media_id}"
account_url: "{INSTAGRAM_URL}"
received: "{timestamp}"
classification: "{classification}"
priority: {"high" if classification == "lead" else "normal"}
status: pending
---

## Instagram {item_type.upper()} from @{sender}

**From:** @{sender}
**Type:** {item_type}
**Classification:** {classification.upper()}
**Media ID:** {media_id or "N/A"}

### Message Content
{text}

## Suggested Reply (adapt before posting)
> Hi @{sender}! Thanks for reaching out. [Personalize here]. — Samina
> {hashtag_suggestion}

## Actions Required
- [ ] Classify and review
- [ ] Draft reply → create /Pending_Approval/SOCIAL_INSTAGRAM_{safe_sender}_{date_str}.md
- [ ] Log action via SKILL_Audit_Logging
- [ ] Move to /Done/

{"## 🔥 LEAD DETECTED\nCreate lead note: /Plans/LEAD_instagram_" + safe_sender + "_" + date_str + ".md" if classification == "lead" else ""}
"""

        filepath.write_text(content, encoding="utf-8")
        self.processed_ids.add(item_id)
        self._save_processed_ids()

        self.write_action_log({
            "action_type": "instagram_item_detected",
            "platform": "instagram",
            "item_type": item_type,
            "classification": classification,
            "from": sender,
            "file": filename
        })

        self.logger.info(f"Created: {filename} (type={item_type}, class={classification})")
        return filepath


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Instagram Watcher for AI Employee Gold Tier")
    parser.add_argument("--health", action="store_true", help="Check instagram-mcp health and exit")
    args = parser.parse_args()

    if args.health:
        try:
            resp = requests.get(f"{MCP_URL}/health", timeout=5)
            print(json.dumps(resp.json(), indent=2))
        except Exception as e:
            print(f"ERROR: instagram-mcp unreachable: {e}")
        return

    watcher = InstagramWatcher()
    watcher.run()


if __name__ == "__main__":
    main()
