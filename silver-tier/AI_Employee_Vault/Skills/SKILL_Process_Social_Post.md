# SKILL: Process Social Post

## Description
Processes incoming social media notifications (Facebook, Instagram, Twitter/X) from
`/Needs_Action/`, drafts responses or acknowledgements, creates approval files for any
outbound posts, and logs all activity. This is the unified social media processing skill.

## Trigger
- Files in `/Needs_Action/` with `type: facebook_message`, `type: instagram_comment`,
  `type: twitter_mention`, `type: twitter_dm`, `type: instagram_dm`, or `type: facebook_comment`.
- Can also be triggered manually with: "Execute SKILL_Process_Social_Post"

## Step-by-Step Procedure

### Step 1 — Read Context
```
Read Dashboard.md
Read Company_Handbook.md
Read Business_Goals.md
List all files in /Needs_Action/ matching FACEBOOK_*, INSTAGRAM_*, TWITTER_*
```

### Step 2 — Classify Each Item
For each social media file in /Needs_Action/:
1. Read the file front matter (`type`, `platform`, `from`, `content`)
2. Classify as one of:
   - **Reply needed**: direct message or mention requiring a response
   - **Engagement**: comment or reaction to log and optionally engage with
   - **Lead**: message indicating buying intent → also trigger SKILL_Reasoning_Loop
   - **Spam/Noise**: irrelevant; move directly to /Done/ with log entry

### Step 3 — Draft Response (if Reply needed or Engagement)
Draft a response following these rules from Company_Handbook.md:
- Professional, warm, concise (under 280 chars for Twitter, 500 chars for Facebook/Instagram)
- Never reveal sensitive business information
- Always include a soft CTA if the person shows interest
- Sign off with "— Samina" (not "AI" or "bot")

Create the file: `/Pending_Approval/SOCIAL_{PLATFORM}_{ID}_{YYYYMMDD}.md`

```markdown
---
type: approval_request
action: social_post_reply
platform: {PLATFORM}
target_user: {from_username}
original_message: "{original_content}"
drafted_reply: "{your_draft}"
mcp_server: {platform}-mcp
created: {ISO_TIMESTAMP}
expires: {ISO_TIMESTAMP + 24h}
status: pending
---

## Drafted Reply
**Platform:** {PLATFORM}
**To:** @{target_user}
**Message:** {drafted_reply}

## To Approve
Move this file to /Approved/

## To Reject
Move this file to /Rejected/
```

### Step 4 — Handle New Post Requests
If any file in /Needs_Action/ has `type: post_request`:
1. Read the post brief
2. Draft content tailored for the platform
3. Create approval file at `/Pending_Approval/POST_{PLATFORM}_{ID}.md`
4. Include hashtags relevant to AI, automation, business (max 10 for Instagram, 3 for Twitter)

### Step 5 — Log and Move
For each processed file:
1. Call SKILL_Audit_Logging to write a JSON log entry
2. Move the source file from /Needs_Action/ → /Done/
3. Update Dashboard.md "Recent Activity" section

### Step 6 — Completion Check
If /Needs_Action/ has no more social media files:
- Output: `<promise>TASK_COMPLETE</promise>`
- Else: continue processing remaining files

## MCP Server Calls

### Post to Facebook (after approval)
```
MCP Server: facebook-mcp (http://localhost:3001)
Tool: post_to_page
Params: { "message": "...", "page_id": "61586406776621" }
```

### Post to Instagram (after approval)
```
MCP Server: instagram-mcp (http://localhost:3002)
Tool: create_post
Params: { "caption": "...", "username": "apple379tree" }
```

### Post to Twitter/X (after approval)
```
MCP Server: twitter-mcp (http://localhost:3003)
Tool: create_tweet
Params: { "text": "...", "username": "SaminaAshr24675" }
```

### Reply to a social comment (after approval)
```
MCP Server: {platform}-mcp
Tool: reply_to_comment
Params: { "comment_id": "...", "reply_text": "..." }
```

## Example Usage

**Scenario:** Instagram DM from @tech_buyer says "How much does your AI setup service cost?"

**Claude's Actions:**
1. Reads `INSTAGRAM_DM_techbuyer_20260107.md` from /Needs_Action/
2. Classifies as: **Lead** (buying intent detected)
3. Drafts reply: "Hi! Thanks for reaching out. Our AI automation setup starts at $500 — I'd love to learn more about your needs. Want to schedule a quick 15-min call? — Samina"
4. Creates `/Pending_Approval/SOCIAL_INSTAGRAM_DM_techbuyer_20260107.md`
5. Also creates a lead note in `/Plans/LEAD_techbuyer_20260107.md`
6. Logs the action
7. Moves original to /Done/
8. Outputs `<promise>TASK_COMPLETE</promise>` if /Needs_Action/ is clear

## Error Handling
- If MCP server unavailable: Write error to `/Logs/`, keep file in /Needs_Action/, output human alert
- If platform blocks automation: Log warning, set `status: manual_required` in approval file
- Always invoke SKILL_Error_Recovery_Graceful_Degradation on repeated failures
