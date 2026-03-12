"""
linkedin_watcher.py — Monitors LinkedIn for new messages and notifications
using Playwright browser automation (LinkedIn Web).

Profile: https://www.linkedin.com/in/samina-ashraf-8386453b3
Session is persisted locally for privacy. No credentials stored in plain text.

Setup:
    1. pip install playwright
    2. playwright install chromium
    3. Run once to establish session: python linkedin_watcher.py --login
    4. After session saved, run normally: python linkedin_watcher.py

Note: LinkedIn does not have a public automation-friendly API.
This uses Playwright against LinkedIn Web. Be aware that excessive
automation may violate LinkedIn's Terms of Service. Use responsibly
and sparingly (check_interval >= 300 recommended).
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from datetime import datetime

# Add parent directory for base_watcher import
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Playwright not installed. Run:")
    print("  pip install playwright && playwright install chromium")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH = PROJECT_ROOT / "AI_Employee_Vault"
SESSION_PATH = PROJECT_ROOT / ".linkedin_session"  # Persistent browser context
LINKEDIN_PROFILE = "https://www.linkedin.com/in/samina-ashraf-8386453b3"
LINKEDIN_BASE = "https://www.linkedin.com"

# Keywords that indicate a sales lead in messages
LEAD_KEYWORDS = [
    "interested", "services", "price", "pricing", "rates",
    "hire", "help me", "consultation", "consult", "quote",
    "how much", "automation", "ai agent", "looking for",
    "can you", "availability", "proposal",
]


class LinkedInWatcher(BaseWatcher):
    """
    Watches LinkedIn Web for new messages and notifications via Playwright.
    Uses a persistent browser context so login session is preserved between runs.
    """

    def __init__(
        self,
        vault_path: str = str(VAULT_PATH),
        session_path: str = str(SESSION_PATH),
        check_interval: int = 300,  # 5 minutes — be respectful to LinkedIn
    ):
        super().__init__(vault_path, check_interval)
        self.session_path = Path(session_path)
        self.session_path.mkdir(parents=True, exist_ok=True)
        self.processed_ids: set = self._load_processed_ids()

    def _load_processed_ids(self) -> set:
        state_file = self.vault_path / ".linkedin_processed.json"
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    return set(json.load(f))
            except Exception:
                return set()
        return set()

    def _save_processed_ids(self) -> None:
        state_file = self.vault_path / ".linkedin_processed.json"
        ids_list = list(self.processed_ids)[-500:]
        with open(state_file, "w") as f:
            json.dump(ids_list, f)

    def _is_logged_in(self, page) -> bool:
        """Check if current page shows logged-in state."""
        try:
            page.wait_for_selector(
                '[data-test-global-nav-me-photo], .global-nav__me-photo',
                timeout=5000
            )
            return True
        except PlaywrightTimeout:
            return False

    def login(self) -> bool:
        """
        Open a visible browser window for the user to log in manually.
        Session is saved to disk for future headless use.
        """
        self.logger.info("Opening browser for LinkedIn login...")
        self.logger.info("Please log in to LinkedIn in the browser window.")
        self.logger.info("The session will be saved automatically after login.")

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                str(self.session_path),
                headless=False,  # VISIBLE for manual login
                viewport={"width": 1280, "height": 800},
            )

            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto(f"{LINKEDIN_BASE}/login")

            self.logger.info("Waiting for manual login (up to 5 minutes)...")
            try:
                # Wait until user reaches the LinkedIn feed (fully logged in)
                page.wait_for_function(
                    """() => {
                        const url = window.location.href;
                        return url.includes('linkedin.com/feed') ||
                               url.includes('linkedin.com/in/') ||
                               url.includes('linkedin.com/mynetwork') ||
                               url.includes('linkedin.com/jobs') ||
                               url.includes('linkedin.com/messaging');
                    }""",
                    timeout=300_000,
                )
                self.logger.info(f"Login successful! Session saved. (URL: {page.url})")
                # Give LinkedIn a moment to fully establish the session
                page.wait_for_timeout(2000)
                browser.close()
                return True
            except PlaywrightTimeout:
                self.logger.error("Login timeout. Please try again.")
                browser.close()
                return False

    def _scrape_messages(self, page) -> list:
        """Scrape unread messages from LinkedIn messaging."""
        messages = []

        try:
            page.goto(f"{LINKEDIN_BASE}/messaging/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)  # Allow dynamic content to load

            # Find conversation items with unread indicators
            # LinkedIn's selectors can change — these are common patterns
            conversation_selectors = [
                '[data-control-name="overlay.click_to_view_messaging"]',
                '.msg-conversation-listitem',
                '.msg-conversations-container__conversations-list li',
            ]

            conversations = []
            for selector in conversation_selectors:
                try:
                    conversations = page.query_selector_all(selector)
                    if conversations:
                        break
                except Exception:
                    continue

            for conv in conversations[:10]:  # Check top 10 conversations
                try:
                    text = conv.inner_text()
                    # Look for unread indicator (bold text or unread badge)
                    has_unread = conv.query_selector(
                        '.msg-conversation-listitem__unread-count, '
                        '[data-test-count]'
                    )

                    if not has_unread:
                        continue

                    # Generate a stable ID from conversation text snippet
                    msg_id = f"li_msg_{abs(hash(text[:50]))}"

                    if msg_id not in self.processed_ids:
                        # Detect if it's a lead
                        text_lower = text.lower()
                        is_lead = any(kw in text_lower for kw in LEAD_KEYWORDS)

                        messages.append({
                            "id": msg_id,
                            "type": "message",
                            "text": text[:500],
                            "is_lead": is_lead,
                            "priority": "high" if is_lead else "normal",
                        })
                except Exception as e:
                    self.logger.debug(f"Error reading conversation: {e}")
                    continue

        except PlaywrightTimeout:
            self.logger.warning("Timeout loading LinkedIn messaging.")
        except Exception as e:
            self.logger.error(f"Error scraping messages: {e}")

        return messages

    def _scrape_notifications(self, page) -> list:
        """Scrape recent LinkedIn notifications."""
        notifications = []

        try:
            page.goto(
                f"{LINKEDIN_BASE}/notifications/",
                wait_until="domcontentloaded",
                timeout=30000
            )
            page.wait_for_timeout(2000)

            notif_selectors = [
                '.nt-card',
                '.notification-item',
                '[data-urn*="notification"]',
            ]

            notif_elements = []
            for selector in notif_selectors:
                try:
                    notif_elements = page.query_selector_all(selector)
                    if notif_elements:
                        break
                except Exception:
                    continue

            for notif in notif_elements[:15]:
                try:
                    text = notif.inner_text()
                    notif_id = f"li_notif_{abs(hash(text[:50]))}"

                    if notif_id not in self.processed_ids:
                        notif_type = "notification"
                        if "connection" in text.lower():
                            notif_type = "connection_request"
                        elif "commented" in text.lower():
                            notif_type = "comment"
                        elif "liked" in text.lower() or "reacted" in text.lower():
                            notif_type = "reaction"
                        elif "mentioned" in text.lower():
                            notif_type = "mention"

                        notifications.append({
                            "id": notif_id,
                            "type": notif_type,
                            "text": text[:400],
                            "is_lead": notif_type in ("connection_request", "mention"),
                            "priority": "normal",
                        })
                except Exception as e:
                    self.logger.debug(f"Error reading notification: {e}")
                    continue

        except PlaywrightTimeout:
            self.logger.warning("Timeout loading LinkedIn notifications.")
        except Exception as e:
            self.logger.error(f"Error scraping notifications: {e}")

        return notifications

    def check_for_updates(self) -> list:
        """Check LinkedIn for new messages and notifications."""
        if not self.session_path.exists() or not any(self.session_path.iterdir()):
            self.logger.error(
                "No LinkedIn session found. Run: python linkedin_watcher.py --login"
            )
            return []

        items = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch_persistent_context(
                    str(self.session_path),
                    headless=True,
                    viewport={"width": 1280, "height": 800},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )

                page = browser.pages[0] if browser.pages else browser.new_page()

                # Navigate to LinkedIn and check login state
                page.goto(LINKEDIN_BASE, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)

                if not self._is_logged_in(page):
                    self.logger.error("LinkedIn session expired. Re-run: python linkedin_watcher.py --login")
                    browser.close()
                    return []

                self.logger.info("LinkedIn session active. Checking for updates...")

                # Scrape messages and notifications
                messages = self._scrape_messages(page)
                notifications = self._scrape_notifications(page)

                items = messages + notifications
                self.logger.info(
                    f"Found {len(messages)} new message(s), "
                    f"{len(notifications)} new notification(s)"
                )

                browser.close()

        except Exception as e:
            self.logger.error(f"LinkedIn check failed: {e}")

        return items

    def create_action_file(self, item: dict) -> Path:
        """Create a structured .md action file for a LinkedIn item."""
        item_id = item["id"]
        item_type = item.get("type", "notification")
        text = item.get("text", "")
        priority = item.get("priority", "normal")
        is_lead = item.get("is_lead", False)

        # Sanitize ID for filename
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", item_id)

        content = f"""---
type: linkedin_{item_type}
notification_type: {item_type}
source: LinkedIn
profile: {LINKEDIN_PROFILE}
received: {datetime.now().isoformat()}
priority: {"high" if is_lead else priority}
is_lead: {str(is_lead).lower()}
status: pending
---

## LinkedIn {item_type.replace('_', ' ').title()} Content

{text}

## Suggested Actions
- [ ] Review content
- [ ] Execute SKILL_Process_LinkedIn for full processing
{"- [ ] HIGH PRIORITY: Potential sales lead detected" if is_lead else ""}
"""

        filepath = self.needs_action / f"LINKEDIN_{item_type.upper()}_{safe_id}.md"
        filepath.write_text(content, encoding="utf-8")

        self.processed_ids.add(item_id)
        self._save_processed_ids()

        self.write_action_log({
            "action_type": f"linkedin_{item_type}_detected",
            "is_lead": is_lead,
            "priority": priority,
            "file": filepath.name,
        })

        return filepath


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Watcher for AI Employee")
    parser.add_argument(
        "--login", action="store_true",
        help="Open browser for manual LinkedIn login (saves session)"
    )
    parser.add_argument(
        "--vault", default=str(VAULT_PATH),
        help="Path to Obsidian vault"
    )
    parser.add_argument(
        "--interval", type=int, default=300,
        help="Check interval in seconds (default: 300 / 5 min)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run check once and exit (for testing)"
    )
    args = parser.parse_args()

    watcher = LinkedInWatcher(
        vault_path=args.vault,
        check_interval=args.interval,
    )

    if args.login:
        success = watcher.login()
        sys.exit(0 if success else 1)

    if args.once:
        items = watcher.check_for_updates()
        print(f"Found {len(items)} item(s)")
        for item in items:
            path = watcher.create_action_file(item)
            print(f"  Created: {path}")
        sys.exit(0)

    watcher.run()


if __name__ == "__main__":
    main()
