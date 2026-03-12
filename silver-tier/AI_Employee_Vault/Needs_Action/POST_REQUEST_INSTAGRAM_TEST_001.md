---
type: post_request
platform: instagram
topic: "AI automation tip with hashtags — visual storytelling angle"
requested_by: orchestrator_test
created_at: 2026-03-06
priority: normal
---

# Instagram Post Request — Test 001

## Request
Draft an Instagram caption about AI automation making business owners more productive.
Use a visual storytelling hook in the first line (people scroll fast). Include 8–12
relevant hashtags at the end. Max 2 emojis. Professional yet warm tone.

## Instructions for SKILL_Process_Social_Post
1. Draft the caption following the Social Media Voice & Tone guidelines in CLAUDE.md.
2. First line must be a strong hook (≤ 125 characters — visible before "more").
3. Total caption + hashtags should be under 2200 characters.
4. Save the draft to `/Pending_Approval/POST_INSTAGRAM_{YYYY-MM-DD}.md` with front matter:
   ```yaml
   platform: instagram
   action: create_post
   caption: "<full caption with hashtags>"
   topic: "AI automation productivity"
   ```
5. Log the action via SKILL_Audit_Logging.
