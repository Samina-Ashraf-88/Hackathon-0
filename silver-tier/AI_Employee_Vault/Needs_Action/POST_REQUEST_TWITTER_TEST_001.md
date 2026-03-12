---
type: post_request
platform: twitter
topic: "AI automation tip in 280 characters — punchy and shareable"
requested_by: orchestrator_test
created_at: 2026-03-06
priority: normal
---

# Twitter/X Post Request — Test 001

## Request
Draft a punchy tweet about AI automation for small business owners. Must fit within
280 characters (including spaces). Should spark engagement — either a bold claim,
a surprising stat, or a question. No more than 1 emoji. Include 2 relevant hashtags.

## Instructions for SKILL_Process_Social_Post
1. Draft the tweet content following the Social Media Voice & Tone guidelines in CLAUDE.md.
2. Strict 280-character limit — count carefully.
3. Save the draft to `/Pending_Approval/POST_TWITTER_{YYYY-MM-DD}.md` with front matter:
   ```yaml
   platform: twitter
   action: create_tweet
   text: "<tweet text>"
   topic: "AI automation tip"
   ```
4. Log the action via SKILL_Audit_Logging.
