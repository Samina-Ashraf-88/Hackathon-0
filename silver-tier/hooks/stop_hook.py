"""
stop_hook.py — Ralph Wiggum Stop Hook for Claude Code

This script is registered as a Claude Code Stop hook in .claude/settings.json.
It intercepts Claude's exit attempt and:
  1. Checks if the completion promise was output: <promise>TASK_COMPLETE</promise>
  2. Checks if /Needs_Action/ is empty (file-movement completion strategy)
  3. If NOT complete → blocks exit and re-injects the reasoning loop prompt
  4. If complete → allows exit cleanly
  5. Enforces a maximum iteration limit to prevent infinite loops

Hook input (from Claude Code via stdin):
    JSON object with fields:
      - transcript_path: path to current session transcript
      - session_id: current session ID
      - stop_hook_active: bool

Hook output (to stdout):
    JSON object:
      - action: "block" | "continue"
      - reason: human-readable explanation
      - new_message: (if action=block) prompt to re-inject

Configuration:
    Register in .claude/settings.json:
    {
      "hooks": {
        "Stop": [{
          "matcher": "",
          "hooks": [{
            "type": "command",
            "command": "python E:/hackathon-0/silver-tier/hooks/stop_hook.py"
          }]
        }]
      }
    }
"""

import sys
import json
import os
from pathlib import Path

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
VAULT_PATH = PROJECT_ROOT / "AI_Employee_Vault"
NEEDS_ACTION_DIR = VAULT_PATH / "Needs_Action"
SKILLS_DIR = VAULT_PATH / "Skills"

MAX_ITERATIONS = int(os.getenv("RALPH_MAX_ITERATIONS", "10"))
ITERATION_STATE_FILE = PROJECT_ROOT / ".ralph_iterations.json"

COMPLETION_PROMISE = "<promise>TASK_COMPLETE</promise>"


def load_iteration_state() -> dict:
    if ITERATION_STATE_FILE.exists():
        try:
            with open(ITERATION_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"count": 0, "session_id": None}


def save_iteration_state(state: dict) -> None:
    with open(ITERATION_STATE_FILE, "w") as f:
        json.dump(state, f)


def reset_iteration_state() -> None:
    if ITERATION_STATE_FILE.exists():
        ITERATION_STATE_FILE.unlink()


def read_transcript(transcript_path: str) -> str:
    """Read the last portion of the session transcript."""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Look at the last 5000 characters for the completion promise
        return content[-5000:]
    except Exception:
        return ""


def has_completion_promise(transcript_path: str) -> bool:
    """Check if Claude output the completion promise."""
    transcript = read_transcript(transcript_path)
    return COMPLETION_PROMISE in transcript


def needs_action_is_empty() -> bool:
    """Check if /Needs_Action/ has no .md files remaining."""
    if not NEEDS_ACTION_DIR.exists():
        return True
    md_files = list(NEEDS_ACTION_DIR.glob("*.md"))
    return len(md_files) == 0


def build_reinject_prompt() -> str:
    """Build the prompt to re-inject into Claude when task is not complete."""
    remaining = []
    if NEEDS_ACTION_DIR.exists():
        remaining = [f.name for f in NEEDS_ACTION_DIR.glob("*.md")]

    skill_path = SKILLS_DIR / "SKILL_Reasoning_Loop.md"
    vault_str = str(VAULT_PATH)

    prompt = (
        f"The task is NOT yet complete. "
        f"There are still {len(remaining)} item(s) in /Needs_Action/: "
        f"{', '.join(remaining[:5])}{'...' if len(remaining) > 5 else ''}. "
        f"\n\nContinue executing SKILL_Reasoning_Loop as defined in {skill_path}. "
        f"Vault path: {vault_str}. "
        f"When ALL items in /Needs_Action/ are processed and moved to /Done/, "
        f"output exactly: {COMPLETION_PROMISE}"
    )
    return prompt


def main():
    # Read hook input from stdin
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        # If no valid input, allow exit
        print(json.dumps({"action": "continue", "reason": "No hook input — allowing exit"}))
        sys.exit(0)

    transcript_path = hook_input.get("transcript_path", "")
    session_id = hook_input.get("session_id", "")

    # Load iteration state
    state = load_iteration_state()

    # Reset counter if this is a new session
    if state.get("session_id") != session_id:
        state = {"count": 0, "session_id": session_id}

    state["count"] += 1
    save_iteration_state(state)

    iteration = state["count"]

    # Safety: enforce max iterations
    if iteration > MAX_ITERATIONS:
        reset_iteration_state()
        print(json.dumps({
            "action": "continue",
            "reason": f"Max iterations ({MAX_ITERATIONS}) reached. Allowing exit for safety."
        }))
        sys.exit(0)

    # Check completion via promise
    if transcript_path and has_completion_promise(transcript_path):
        reset_iteration_state()
        print(json.dumps({
            "action": "continue",
            "reason": f"Task complete! Promise detected after {iteration} iteration(s)."
        }))
        sys.exit(0)

    # Check completion via file movement
    if needs_action_is_empty():
        reset_iteration_state()
        print(json.dumps({
            "action": "continue",
            "reason": f"/Needs_Action/ is empty after {iteration} iteration(s). Task complete."
        }))
        sys.exit(0)

    # Task not complete — re-inject prompt
    reinject_prompt = build_reinject_prompt()

    print(json.dumps({
        "action": "block",
        "reason": f"Task not complete (iteration {iteration}/{MAX_ITERATIONS}). Re-injecting prompt.",
        "new_message": reinject_prompt,
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
