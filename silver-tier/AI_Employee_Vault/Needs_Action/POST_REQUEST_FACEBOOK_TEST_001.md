---
type: post_request
platform: facebook
topic: "AI automation tip — how AI saves 10 hours per week"
requested_by: orchestrator_test
created_at: 2026-03-06
priority: normal
---

# Facebook Post Request — Test 001

## Request
Draft an engaging Facebook post about how AI automation saves 10 hours per week for
small business owners. Include a real-world example, a subtle call-to-action, and
max 2 emojis. Target audience: entrepreneurs and freelancers.

## Instructions for SKILL_Process_Social_Post
1. Draft the post content following the Social Media Voice & Tone guidelines in CLAUDE.md.
2. Keep it under 500 characters for optimal Facebook reach.
3. Save the draft to `/Pending_Approval/POST_FACEBOOK_{YYYY-MM-DD}.md` with front matter:
   ```yaml
   platform: facebook
   action: post_to_page
   message: "<full post text>"
   topic: "AI automation tip"
   ```
4. Create an approval request entry.
5. Log the action via SKILL_Audit_Logging.
