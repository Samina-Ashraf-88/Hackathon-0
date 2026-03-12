"""
twitter_watcher.py — Twitter/X Watcher for AI Employee Gold Tier

Polls the twitter-mcp server for new @mentions and DMs for
Samina Ashraf's Twitter/X account (@SaminaAshr24675) and creates
action files in /Needs_Action/ for Claude to process.

Account: https://x.com/SaminaAshr24675

Run:
  python twitter_watcher.py

Environment:
  VAULT_PATH          — path to AI_Employee_Vault
  TWITTER_MCP_URL     — http://localhost:3003
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
MCP_URL = os.getenv("TWITTER_MCP_URL", "http://localhost:3003")
MCP_SECRET = os.getenv("MCP_SECRET", "dev-secret-change-me")
CHECK_INTERVAL = int(os.getenv("TWITTER_CHECK_INTERVAL", "300"))
TWITTER_USERNAME = "SaminaAshr24675"
TWITTER_PROFILE_URL = f"https://x.com/{TWITTER_USERNAME}"

LEAD_KEYWORDS = [
    "price", "cost", "how much", "services", "interested", "hire",
    "quote", "available", "dm", "contact", "automate", "ai employee",
    "consulting", "help my business", "work with you"
]


class TwitterWatcher(BaseWatcher):
    """
    Polls twitter-mcp for new mentions and DMs.
    Creates /Needs_Action/TWITTER_*.md files for Claude.
    """

    def __init__(self):
        super().__init__(vault_path=VAULT_PATH, check_interval=CHECK_INTERVAL)
        self.processed_ids: set = self._load_processed_ids()
        self.headers = {"Authorization": f"Bearer {MCP_SECRET}"}

    def _processed_ids_file(self) -> Path:
        return Path(__file__).parent / ".twitter_processed.json"

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
            self.logger.warning(f"twitter-mcp not reachable at {MCP_URL}")
            return {}
        except Exception as e:
            self.logger.error(f"twitter-mcp GET {endpoint} failed: {e}")
            return {}

    def _classify(self, text: str) -> str:
        text_lower = text.lower()
        if any(kw in text_lower for kw in LEAD_KEYWORDS):
            return "lead"
        if any(kw in text_lower for kw in ["question", "how", "why", "what", "?"]):
            return "question"
        if any(kw in text_lower for kw in ["great", "love", "amazing", "follow", "retweet"]):
            return "engagement"
        return "mention"

    def _shorten_for_reply(self, text: str) -> str:
        """Ensure reply fits within 280 chars including @mention."""
        mention = f"@{TWITTER_USERNAME} "
        max_len = 280 - len(mention) - 10  # leave buffer
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."

    def check_for_updates(self) -> list:
        items = []

        mentions = self._mcp_get("/mentions")
        for mention in mentions.get("mentions", []):
            tweet_id = mention.get("id", f"tw_mention_{time.time_ns()}")
            if tweet_id not in self.processed_ids:
                mention["_item_id"] = tweet_id
                mention["_item_type"] = "mention"
                items.append(mention)

        dms = self._mcp_get("/messages")
        for dm in dms.get("messages", []):
            dm_id = dm.get("id", f"tw_dm_{time.time_ns()}")
            if dm_id not in self.processed_ids:
                dm["_item_id"] = dm_id
                dm["_item_type"] = "dm"
                items.append(dm)

        return items

    def create_action_file(self, item: dict) -> Path:
        item_id = item.get("_item_id", f"unknown_{time.time_ns()}")
        item_type = item.get("_item_type", "mention")
        sender = item.get("username", item.get("from_username", "Unknown"))
        text = item.get("text", item.get("message", ""))
        tweet_url = item.get("url", item.get("tweet_url", ""))
        timestamp = item.get("created_at", datetime.now().isoformat())
        classification = self._classify(text)

        safe_sender = "".join(c if c.isalnum() else "_" for c in str(sender))[:30]
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"TWITTER_{item_type.upper()}_{safe_sender}_{date_str}.md"
        filepath = self.needs_action / filename

        # Draft a reply template (<=280 chars)
        draft_reply = self._shorten_for_reply(f"Hi @{sender}! Thanks for the mention. [Personalize]. — Samina")

        content = f"""---
type: twitter_{item_type}
platform: twitter
account: "@{TWITTER_USERNAME}"
from: "@{sender}"
item_id: "{item_id}"
tweet_url: "{tweet_url}"
profile_url: "{TWITTER_PROFILE_URL}"
received: "{timestamp}"
classification: "{classification}"
char_count: {len(text)}
priority: {"high" if classification == "lead" else "normal"}
status: pending
---

## Twitter/X {item_type.title()} from @{sender}

**From:** @{sender}
**Type:** {item_type}
**Classification:** {classification.upper()}
**Tweet URL:** {tweet_url or "N/A"}

### Content ({len(text)} chars)
{text}

## Draft Reply ({len(draft_reply)} chars — max 280)
> {draft_reply}

## Actions Required
- [ ] Review and classify
- [ ] Adapt reply if needed
- [ ] Create /Pending_Approval/SOCIAL_TWITTER_{safe_sender}_{date_str}.md
- [ ] Log action via SKILL_Audit_Logging
- [ ] Move to /Done/

{"## 💰 LEAD DETECTED\nCreate lead: /Plans/LEAD_twitter_" + safe_sender + "_" + date_str + ".md" if classification == "lead" else ""}
"""

        filepath.write_text(content, encoding="utf-8")
        self.processed_ids.add(item_id)
        self._save_processed_ids()

        self.write_action_log({
            "action_type": "twitter_item_detected",
            "platform": "twitter",
            "item_type": item_type,
            "classification": classification,
            "from": sender,
            "file": filename
        })

        self.logger.info(f"Created: {filename} (type={item_type}, class={classification})")
        return filepath


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Twitter/X Watcher for AI Employee Gold Tier")
    parser.add_argument("--health", action="store_true", help="Check twitter-mcp health and exit")
    args = parser.parse_args()

    if args.health:
        try:
            resp = requests.get(f"{MCP_URL}/health", timeout=5)
            print(json.dumps(resp.json(), indent=2))
        except Exception as e:
            print(f"ERROR: twitter-mcp unreachable: {e}")
        return

    watcher = TwitterWatcher()
    watcher.run()


if __name__ == "__main__":
    main()
