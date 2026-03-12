"""
social_login.py — Interactive browser login for Facebook, Instagram, and Twitter.

Opens a VISIBLE (non-headless) Chromium browser so you can log in manually.
After you log in, press ENTER in this terminal — the session is saved automatically
and future MCP server calls will reuse it without needing to log in again.

Usage:
    python watchers/social_login.py --platform facebook
    python watchers/social_login.py --platform instagram
    python watchers/social_login.py --platform twitter
    python watchers/social_login.py --all   # Login to all three in sequence
"""

import os
import sys
import argparse
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent

PLATFORMS = {
    "facebook": {
        "url": "https://www.facebook.com/login",
        "session_env": "FACEBOOK_SESSION_PATH",
        "session_default": str(PROJECT_ROOT / ".sessions" / "facebook"),
        "ready_url_prefix": "https://www.facebook.com",
        "done_hint": "your Facebook feed or profile",
    },
    "instagram": {
        "url": "https://www.instagram.com/accounts/login/",
        "session_env": "INSTAGRAM_SESSION_PATH",
        "session_default": str(PROJECT_ROOT / ".sessions" / "instagram"),
        "ready_url_prefix": "https://www.instagram.com",
        "done_hint": "your Instagram home feed",
    },
    "twitter": {
        "url": "https://x.com/i/flow/login",
        "session_env": "TWITTER_SESSION_PATH",
        "session_default": str(PROJECT_ROOT / ".sessions" / "twitter"),
        "ready_url_prefix": "https://x.com",
        "done_hint": "your Twitter/X home feed",
    },
}


def login_platform(platform: str) -> bool:
    cfg = PLATFORMS[platform]

    # Load .env for session path override
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    session_path = os.getenv(cfg["session_env"], cfg["session_default"])
    Path(session_path).mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Logging into {platform.upper()}")
    print(f"  Session will be saved to: {session_path}")
    print(f"{'='*60}")
    print(f"  A browser window will open. Log in manually.")
    print(f"  Once you can see {cfg['done_hint']},")
    print(f"  come back here and press ENTER to save the session.")
    print(f"{'='*60}\n")

    with sync_playwright() as p:
        # launch_persistent_context returns a BrowserContext, not a Browser
        context = p.chromium.launch_persistent_context(
            session_path,
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
            ignore_https_errors=True,
        )

        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(cfg["url"], wait_until="domcontentloaded", timeout=30000)

            input(f"  >> Press ENTER after you've logged in to {platform.title()}... ")

            # Verify login by checking current URL
            current_url = page.url
            if cfg["ready_url_prefix"] in current_url and "login" not in current_url.lower():
                print(f"  Login confirmed. Session saved to: {session_path}")
                success = True
            else:
                print(f"  WARNING: Current URL is {current_url}")
                print(f"  It doesn't look like you're fully logged in, but the session was saved anyway.")
                success = False

        except Exception as e:
            print(f"  ERROR during login: {e}")
            success = False

        finally:
            try:
                context.close()
            except Exception:
                pass  # already closed — safe to ignore

    return success


def main():
    parser = argparse.ArgumentParser(description="Social Media Browser Login Helper")
    parser.add_argument("--platform", choices=["facebook", "instagram", "twitter"],
                        help="Platform to log into")
    parser.add_argument("--all", action="store_true",
                        help="Log into all three platforms in sequence")
    args = parser.parse_args()

    if args.all:
        for platform in ["facebook", "instagram", "twitter"]:
            login_platform(platform)
        print("\nAll sessions saved. MCP servers will now use these sessions.")
    elif args.platform:
        login_platform(args.platform)
        print(f"\n{args.platform.title()} session saved. Restart mcp-{args.platform} if it's already running.")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
