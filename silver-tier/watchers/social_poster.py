"""
social_poster.py — Posts approved social media content to Facebook, Instagram, or Twitter
via the local MCP HTTP servers (ports 3001/3002/3003).

Modeled after linkedin_poster.py. Reads an approved .md file, determines the platform,
calls the appropriate MCP endpoint, moves the file to /Done/, and writes an audit log entry.

Usage:
    python social_poster.py --platform facebook --file "AI_Employee_Vault/Approved/POST_FACEBOOK_*.md"
    python social_poster.py --platform instagram --file "..."
    python social_poster.py --platform twitter --file "..."
    python social_poster.py --scan-approved   # Process all approved social posts
    python social_poster.py --file "..." --dry-run
"""

import os
import sys
import re
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime

# Ensure UTF-8 output on Windows consoles (handles emoji in post content)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent

# Load .env so DRY_RUN and MCP_SECRET are available without manual export
_env_file = PROJECT_ROOT / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _, _v = _line.partition('=')
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
VAULT_PATH = PROJECT_ROOT / "AI_Employee_Vault"

# MCP server endpoints
MCP_ENDPOINTS = {
    "facebook":  "http://localhost:3001",
    "instagram": "http://localhost:3002",
    "twitter":   "http://localhost:3003",
}

# Action → endpoint path mapping per platform
PLATFORM_ROUTES = {
    "facebook": {
        "post_to_page": "/post",
        "reply":        "/reply",
        "default":      "/post",
    },
    "instagram": {
        "create_post":  "/post",
        "reply":        "/reply",
        "default":      "/post",
    },
    "twitter": {
        "create_tweet": "/post",
        "reply":        "/reply",
        "default":      "/post",
    },
}

# Front-matter field that holds the post content, per platform
CONTENT_FIELD = {
    "facebook":  "message",
    "instagram": "caption",
    "twitter":   "text",
}

# File prefixes scanned when using --scan-approved
APPROVED_PREFIXES = {
    "facebook":  ["FACEBOOK_POST_", "POST_FACEBOOK_", "POST_FB_"],
    "instagram": ["INSTAGRAM_POST_", "POST_INSTAGRAM_", "POST_IG_"],
    "twitter":   ["TWITTER_POST_", "POST_TWITTER_", "POST_TW_"],
}


def parse_approved_file(filepath: Path) -> dict:
    """Extract front matter and post body from an approved markdown file."""
    content = filepath.read_text(encoding="utf-8")

    frontmatter = {}
    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                frontmatter[key.strip()] = value.strip().strip('"')

    # Prefer explicit front-matter message fields
    platform = frontmatter.get("platform", "").lower()
    message = (
        frontmatter.get("message")
        or frontmatter.get("caption")
        or frontmatter.get("text")
        or frontmatter.get("content")
        or ""
    )

    # Fall back to ## Draft Post section
    if not message:
        post_match = re.search(r"## Draft Post\n(.*?)(?:\n## |$)", content, re.DOTALL)
        if post_match:
            message = post_match.group(1).strip()

    # Append hashtags if present and not already in body
    hashtag_match = re.search(r"## Suggested Hashtags\n(.*?)(?:\n## |$)", content, re.DOTALL)
    if hashtag_match:
        hashtags = hashtag_match.group(1).strip()
        if hashtags and hashtags not in message:
            message = f"{message}\n\n{hashtags}"

    return {
        "platform": platform,
        "action":   frontmatter.get("action", "default"),
        "message":  message,
        "topic":    frontmatter.get("topic", ""),
        "type":     frontmatter.get("type", ""),
        "raw_frontmatter": frontmatter,
    }


def post_to_mcp(platform: str, action: str, message: str,
                dry_run: bool = False, extra_params: dict = None) -> bool:
    """
    Send the post content to the MCP HTTP server for the given platform.
    Returns True on success, False on failure.
    """
    if not message:
        print("ERROR: Empty post content — nothing to send.")
        return False

    if dry_run:
        print(f"\n[DRY RUN] Would POST to {platform.upper()} MCP:")
        print(f"  Action : {action}")
        print(f"  Content: {message[:200]}{'...' if len(message) > 200 else ''}")
        return True

    base_url = MCP_ENDPOINTS.get(platform)
    if not base_url:
        print(f"ERROR: Unknown platform '{platform}'. Valid: facebook, instagram, twitter")
        return False

    routes = PLATFORM_ROUTES.get(platform, {})
    path = routes.get(action, routes.get("default", "/post"))
    url = f"{base_url}{path}"

    content_key = CONTENT_FIELD.get(platform, "message")
    params = {content_key: message}
    if extra_params:
        params.update(extra_params)
    payload = {"params": params}

    mcp_secret = os.getenv("MCP_SECRET", "")
    headers = {"Content-Type": "application/json"}
    if mcp_secret:
        headers["Authorization"] = f"Bearer {mcp_secret}"

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        print(f"  {platform.upper()} MCP responded {resp.status_code}: {resp.text[:120]}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot reach {platform.upper()} MCP at {base_url}. Is it running?")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: {platform.upper()} MCP HTTP error: {e} — {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"ERROR posting to {platform.upper()} MCP: {e}")
        return False


def write_action_log(vault_path: Path, entry: dict) -> None:
    """Append an audit log entry to /Logs/YYYY-MM-DD.json."""
    log_dir = vault_path / "Logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"

    entries = []
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except Exception:
            entries = []

    entry["timestamp"] = datetime.now().isoformat()
    entry["actor"] = "social_poster"
    entries.append(entry)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def process_single_file(filepath: Path, vault_path: Path,
                         platform_override: str = "", dry_run: bool = False) -> bool:
    """Post a single approved file and move it to /Done/ on success."""
    print(f"\nProcessing: {filepath.name}")

    data = parse_approved_file(filepath)
    platform = platform_override or data["platform"]
    if not platform:
        print(f"  ERROR: Cannot determine platform from file {filepath.name}")
        return False

    platform = platform.lower()
    if platform not in MCP_ENDPOINTS:
        print(f"  ERROR: Unsupported platform '{platform}'")
        return False

    if not data["message"]:
        print(f"  WARNING: No post content found in {filepath.name}")
        return False

    action = data["action"] if data["action"] != "default" else "default"

    # Extra params: Instagram needs image_path for feed posts
    extra_params = {}
    if platform == "instagram":
        img = data["raw_frontmatter"].get("image_path", "")
        if img:
            extra_params["image_path"] = img

    success = post_to_mcp(platform, action, data["message"], dry_run=dry_run,
                          extra_params=extra_params or None)

    write_action_log(vault_path, {
        "action_type": f"{platform}_post",
        "file": filepath.name,
        "platform": platform,
        "action": action,
        "result": "success" if success else "failure",
        "dry_run": dry_run,
    })

    if success:
        done_dir = vault_path / "Done"
        done_dir.mkdir(exist_ok=True)
        dest = done_dir / filepath.name
        filepath.rename(dest)
        print(f"  Moved to /Done/{filepath.name}")

    return success


def scan_approved_posts(vault_path: Path, platform_filter: str = "", dry_run: bool = False) -> None:
    """Scan /Approved/ for social post files and process them."""
    approved_dir = vault_path / "Approved"
    if not approved_dir.exists():
        print("No /Approved/ directory found.")
        return

    platforms_to_check = (
        [platform_filter.lower()] if platform_filter else list(MCP_ENDPOINTS.keys())
    )

    found_any = False
    for platform in platforms_to_check:
        prefixes = APPROVED_PREFIXES.get(platform, [])
        for prefix in prefixes:
            for post_file in approved_dir.glob(f"{prefix}*.md"):
                found_any = True
                process_single_file(post_file, vault_path, platform_override=platform,
                                    dry_run=dry_run)

    if not found_any:
        print(f"No approved social posts found in {approved_dir}")


def main():
    parser = argparse.ArgumentParser(description="Social Media Poster (FB/IG/TW) for AI Employee")
    parser.add_argument("--platform", choices=["facebook", "instagram", "twitter"],
                        help="Target platform (required unless using --scan-approved)")
    parser.add_argument("--file", help="Path to approved social post .md file")
    parser.add_argument("--scan-approved", action="store_true",
                        help="Scan /Approved/ and post all approved social posts")
    parser.add_argument("--vault", default=str(VAULT_PATH),
                        help="Path to Obsidian vault (default: AI_Employee_Vault)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview post without actually sending to MCP")
    args = parser.parse_args()

    vault = Path(args.vault)
    dry_run = args.dry_run or os.getenv("DRY_RUN", "true").lower() == "true"

    if dry_run:
        print("[DRY RUN MODE] No actual posts will be sent to MCP servers.")

    if args.scan_approved:
        scan_approved_posts(vault, platform_filter=args.platform or "", dry_run=dry_run)

    elif args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"File not found: {filepath}")
            sys.exit(1)

        success = process_single_file(
            filepath, vault,
            platform_override=args.platform or "",
            dry_run=dry_run
        )
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
