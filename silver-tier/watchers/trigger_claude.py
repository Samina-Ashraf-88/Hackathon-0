"""
trigger_claude.py — Helper script to manually trigger Claude CLI with a skill.

Usage:
    python trigger_claude.py                          # Run reasoning loop
    python trigger_claude.py --skill SKILL_Generate_Sales_Post
    python trigger_claude.py --skill SKILL_Approval_Workflow --context "Part B"
    python trigger_claude.py --list-skills
"""

import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH = PROJECT_ROOT / "AI_Employee_Vault"
SKILLS_PATH = VAULT_PATH / "Skills"


def list_skills():
    skills = list(SKILLS_PATH.glob("SKILL_*.md"))
    if not skills:
        print("No skill files found in", SKILLS_PATH)
        return
    print(f"\nAvailable Skills ({len(skills)}):")
    print("-" * 50)
    for s in sorted(skills):
        print(f"  • {s.stem}")
    print()


def trigger(skill_name: str, context: str = "", vault: Path = VAULT_PATH):
    skill_file = SKILLS_PATH / f"{skill_name}.md"

    if not skill_file.exists():
        print(f"ERROR: Skill file not found: {skill_file}")
        print("Run with --list-skills to see available skills.")
        sys.exit(1)

    prompt = (
        f"Execute {skill_name} as defined in {skill_file}. "
        f"Vault path: {vault}. "
        f"{context}"
    )

    print(f"\nTriggering Claude with skill: {skill_name}")
    print(f"Vault: {vault}")
    if context:
        print(f"Context: {context}")
    print("-" * 50)

    # Resolve claude binary — on Windows npm installs .cmd wrappers
    claude_bin = shutil.which("claude") or shutil.which("claude.cmd")
    if not claude_bin:
        npm_global = Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd"
        if npm_global.exists():
            claude_bin = str(npm_global)

    cmd = [
        claude_bin or "claude",
        "--print",
        prompt,
        "--cwd", str(vault),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
            shell=(sys.platform == "win32"),
        )
        sys.exit(result.returncode)
    except FileNotFoundError:
        print("\nERROR: Claude CLI not found.")
        print("Install with: npm install -g @anthropic/claude-code")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Trigger Claude CLI with an AI Employee skill"
    )
    parser.add_argument(
        "--skill", default="SKILL_Reasoning_Loop",
        help="Skill name (without .md extension)"
    )
    parser.add_argument(
        "--context", default="",
        help="Additional context to pass to Claude"
    )
    parser.add_argument(
        "--vault", default=str(VAULT_PATH),
        help="Path to Obsidian vault"
    )
    parser.add_argument(
        "--list-skills", action="store_true",
        help="List all available skill files"
    )
    args = parser.parse_args()

    if args.list_skills:
        list_skills()
        return

    trigger(args.skill, args.context, Path(args.vault))


if __name__ == "__main__":
    main()
