"""
linkedin_poster.py — Posts approved LinkedIn content using Playwright.
Reads an approved file from /Approved/ and posts it to LinkedIn.

Usage:
    python linkedin_poster.py --file "path/to/LINKEDIN_POST_2026-02-25.md"
    python linkedin_poster.py --file "..." --dry-run
    python linkedin_poster.py --scan-approved   # Process all approved LinkedIn posts
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH = PROJECT_ROOT / "AI_Employee_Vault"
SESSION_PATH = PROJECT_ROOT / ".linkedin_session"
LINKEDIN_BASE = "https://www.linkedin.com"


def parse_approved_post(filepath: Path) -> dict:
    """Extract post content and metadata from an approved markdown file."""
    content = filepath.read_text(encoding="utf-8")

    # Extract frontmatter
    frontmatter = {}
    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                frontmatter[key.strip()] = value.strip()

    # Extract post body (after "## Draft Post")
    post_match = re.search(r"## Draft Post\n(.*?)(?:\n## |$)", content, re.DOTALL)
    post_body = post_match.group(1).strip() if post_match else ""

    # Extract hashtags section if separate
    hashtag_match = re.search(r"## Suggested Hashtags\n(.*?)(?:\n## |$)", content, re.DOTALL)
    hashtags = hashtag_match.group(1).strip() if hashtag_match else ""

    # Combine post body with hashtags if not already included
    full_post = post_body
    if hashtags and hashtags not in post_body:
        full_post = f"{post_body}\n\n{hashtags}"

    return {
        "post_text": full_post,
        "platform": frontmatter.get("platform", "LinkedIn"),
        "account": frontmatter.get("account", ""),
        "pillar": frontmatter.get("pillar", ""),
        "scheduled_for": frontmatter.get("scheduled_for", ""),
        "type": frontmatter.get("type", ""),
    }


def post_to_linkedin(post_text: str, session_path: Path, dry_run: bool = False) -> bool:
    """
    Use Playwright to post content to LinkedIn.
    Returns True on success, False on failure.
    """
    if dry_run:
        print(f"\n[DRY RUN] Would post to LinkedIn:\n{'='*50}")
        print(post_text[:300] + ("..." if len(post_text) > 300 else ""))
        print('='*50)
        return True

    if not session_path.exists():
        print("ERROR: No LinkedIn session. Run: python linkedin_watcher.py --login")
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                str(session_path),
                headless=True,
                viewport={"width": 1280, "height": 800},
            )

            page = browser.pages[0] if browser.pages else browser.new_page()

            # Navigate to LinkedIn feed to start a post
            page.goto(f"{LINKEDIN_BASE}/feed/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            # Click "Start a post" button
            post_button_selectors = [
                'button.share-box-feed-entry__trigger',
                '[data-control-name="share.share_box_feed_create_update"]',
                '.share-box-feed-entry__trigger',
                'button[aria-label*="Start a post"]',
                'button[aria-label*="Create a post"]',
                'div.share-box-feed-entry__top-bar button',
                '.artdeco-button--muted.share-box-feed-entry__trigger',
                'div[data-view-name="share-box"] button',
                'button[aria-label*="post"]',
                '.editor-content',
            ]

            clicked = False
            for selector in post_button_selectors:
                try:
                    button = page.wait_for_selector(selector, timeout=4000)
                    if button and button.is_visible():
                        button.click()
                        clicked = True
                        print(f"  Clicked post button: {selector}")
                        break
                except PlaywrightTimeout:
                    continue

            if not clicked:
                # Last resort: look for any button with post-related text
                try:
                    button = page.get_by_role("button", name="Start a post")
                    button.click(timeout=5000)
                    clicked = True
                    print("  Clicked via role: Start a post")
                except Exception:
                    pass

            if not clicked:
                # Dump page HTML snippet for debugging
                title = page.title()
                print(f"  Page title: {title}")
                print("ERROR: Could not find 'Start a post' button. LinkedIn UI may have changed.")
                browser.close()
                return False

            page.wait_for_timeout(2000)

            # Find the text editor in the post modal
            editor_selectors = [
                'div.ql-editor[contenteditable="true"]',
                '.ql-editor',
                '[data-placeholder="What do you want to talk about?"]',
                'div[aria-label="Text editor for creating content"]',
                'div[role="textbox"]',
                '.editor-content[contenteditable="true"]',
                'div[contenteditable="true"]',
            ]

            editor = None
            for selector in editor_selectors:
                try:
                    editor = page.wait_for_selector(selector, timeout=5000)
                    if editor and editor.is_visible():
                        print(f"  Found editor: {selector}")
                        break
                except PlaywrightTimeout:
                    continue

            if not editor:
                # Try role-based
                try:
                    editor = page.get_by_role("textbox").first
                    editor.wait_for(timeout=5000)
                    print("  Found editor via role: textbox")
                except Exception:
                    pass

            if not editor:
                print("ERROR: Could not find post editor. LinkedIn UI may have changed.")
                browser.close()
                return False

            # Type the post content
            editor.click()
            page.wait_for_timeout(500)
            page.keyboard.type(post_text, delay=20)  # Small delay mimics human typing
            page.wait_for_timeout(1000)

            # Find and click the "Post" submit button
            submit_selectors = [
                'button.share-actions__primary-action',
                'button[data-control-name="share.post"]',
                'button[aria-label="Post"]',
                'button.artdeco-button--primary[aria-label*="Post"]',
                '.share-actions__primary-action',
            ]

            submitted = False
            for selector in submit_selectors:
                try:
                    submit_btn = page.wait_for_selector(selector, timeout=5000)
                    if submit_btn and submit_btn.is_enabled():
                        submit_btn.click()
                        submitted = True
                        print(f"  Clicked submit: {selector}")
                        break
                except PlaywrightTimeout:
                    continue

            if not submitted:
                # Try role-based
                try:
                    submit_btn = page.get_by_role("button", name="Post")
                    if submit_btn.is_enabled():
                        submit_btn.click(timeout=5000)
                        submitted = True
                        print("  Clicked submit via role: Post")
                except Exception:
                    pass

            if not submitted:
                print("ERROR: Could not find Post submit button.")
                browser.close()
                return False

            # Wait for post to complete
            page.wait_for_timeout(3000)
            print("LinkedIn post submitted successfully.")
            browser.close()
            return True

    except Exception as e:
        print(f"ERROR posting to LinkedIn: {e}")
        return False


def log_post_action(vault_path: Path, result: dict) -> None:
    """Log the posting action to vault logs."""
    log_dir = vault_path / "Logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"

    entries = []
    if log_file.exists():
        try:
            with open(log_file, "r") as f:
                entries = json.load(f)
        except Exception:
            entries = []

    result["timestamp"] = datetime.now().isoformat()
    result["actor"] = "linkedin_poster"
    entries.append(result)

    with open(log_file, "w") as f:
        json.dump(entries, f, indent=2)


def process_approved_posts(vault_path: Path, dry_run: bool = False) -> None:
    """Scan /Approved/ for LinkedIn post files and post them."""
    approved_dir = vault_path / "Approved"
    done_dir = vault_path / "Done"
    done_dir.mkdir(exist_ok=True)

    post_files = list(approved_dir.glob("LINKEDIN_POST_*.md"))

    if not post_files:
        print("No approved LinkedIn posts found.")
        return

    for post_file in post_files:
        print(f"\nProcessing: {post_file.name}")
        try:
            data = parse_approved_post(post_file)

            if not data["post_text"]:
                print(f"  WARNING: Empty post content in {post_file.name}")
                continue

            success = post_to_linkedin(
                data["post_text"],
                SESSION_PATH,
                dry_run=dry_run
            )

            log_post_action(vault_path, {
                "action_type": "linkedin_post",
                "file": post_file.name,
                "pillar": data["pillar"],
                "result": "success" if success else "failure",
                "dry_run": dry_run,
            })

            if success:
                # Move to Done
                dest = done_dir / post_file.name
                post_file.rename(dest)
                print(f"  Moved to /Done/{post_file.name}")

                # Update Dashboard
                dashboard = vault_path / "Dashboard.md"
                if dashboard.exists():
                    content = dashboard.read_text(encoding="utf-8")
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                    entry = f"- [{ts}] LinkedIn post published: {data['pillar']}\n"
                    content = content.replace(
                        "## Recent Activity\n",
                        f"## Recent Activity\n{entry}"
                    )
                    dashboard.write_text(content, encoding="utf-8")
            else:
                print(f"  FAILED: {post_file.name} — check logs")

        except Exception as e:
            print(f"  ERROR processing {post_file.name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Poster for AI Employee")
    parser.add_argument("--file", help="Path to approved LINKEDIN_POST_*.md file")
    parser.add_argument("--scan-approved", action="store_true",
                        help="Scan /Approved/ and post all approved LinkedIn posts")
    parser.add_argument("--vault", default=str(VAULT_PATH), help="Path to Obsidian vault")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview post without actually posting")
    args = parser.parse_args()

    vault = Path(args.vault)
    dry_run = args.dry_run or os.getenv("DRY_RUN", "true").lower() == "true"

    if dry_run:
        print("[DRY RUN MODE] No actual posts will be made.")

    if args.scan_approved:
        process_approved_posts(vault, dry_run=dry_run)
    elif args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"File not found: {filepath}")
            sys.exit(1)

        data = parse_approved_post(filepath)
        if not data["post_text"]:
            print("ERROR: Empty post content.")
            sys.exit(1)

        print(f"Posting from: {filepath.name}")
        success = post_to_linkedin(data["post_text"], SESSION_PATH, dry_run=dry_run)

        log_post_action(vault, {
            "action_type": "linkedin_post",
            "file": filepath.name,
            "result": "success" if success else "failure",
            "dry_run": dry_run,
        })

        if success and not dry_run:
            done_dir = vault / "Done"
            done_dir.mkdir(exist_ok=True)
            filepath.rename(done_dir / filepath.name)
            print(f"Moved to /Done/")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
