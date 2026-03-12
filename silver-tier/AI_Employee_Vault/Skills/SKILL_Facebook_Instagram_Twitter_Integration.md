# SKILL: Facebook, Instagram & Twitter/X Integration

## Description
Manages all interactions with Samina Ashraf's social media accounts. Handles both
inbound (monitoring messages, comments, mentions) and outbound (posting content,
replying) across all three platforms using dedicated MCP servers backed by Playwright
browser automation. All posts and replies require human approval.

## Accounts
| Platform | Account | MCP Server | Port |
|----------|---------|------------|------|
| Facebook | https://www.facebook.com/profile.php?id=61586406776621 | facebook-mcp | 3001 |
| Instagram | https://www.instagram.com/apple379tree/ | instagram-mcp | 3002 |
| Twitter/X | https://x.com/SaminaAshr24675 | twitter-mcp | 3003 |

## Trigger
- Watcher files: `FACEBOOK_*.md`, `INSTAGRAM_*.md`, `TWITTER_*.md` in /Needs_Action/
- Scheduled post requests in /Needs_Action/ with `type: social_post_request`
- Called by: SKILL_Weekly_CEO_Briefing (for social summary data)
- Manual: "Execute SKILL_Facebook_Instagram_Twitter_Integration"

## Inbound Processing

### Facebook Messages & Comments
When `FACEBOOK_MESSAGE_*.md` or `FACEBOOK_COMMENT_*.md` appears in /Needs_Action/:
1. Read: sender, content, timestamp, post_id
2. Classify: lead / support / spam / engagement
3. If lead or support → draft reply → create `/Pending_Approval/SOCIAL_FB_*.md`
4. If spam → log and move to /Done/
5. If engagement (like/share) → log and optionally acknowledge

### Instagram DMs & Comments
When `INSTAGRAM_DM_*.md` or `INSTAGRAM_COMMENT_*.md` appears in /Needs_Action/:
1. Read: username, message, timestamp, media_id
2. Classify and draft response (max 500 chars)
3. Add relevant hashtags if it's a comment response:
   `#AIEmployee #Automation #SmallBusiness #Claude #AITools`
4. Create approval file

### Twitter/X Mentions & DMs
When `TWITTER_MENTION_*.md` or `TWITTER_DM_*.md` appears in /Needs_Action/:
1. Read: username, tweet_text, tweet_id, timestamp
2. Classify
3. Draft reply (max 280 chars including @mention)
4. Create approval file
5. For retweet opportunities: create `/Pending_Approval/TWITTER_RETWEET_*.md`

## Outbound Actions (ALL require /Approved/ file)

### Post to Facebook Page
```
MCP: facebook-mcp → POST http://localhost:3001/post
Body: {
  "action": "post_to_page",
  "message": "Full post text here...",
  "page_id": "61586406776621"
}
Expected: { "success": true, "post_id": "..." }
```

### Post to Instagram
```
MCP: instagram-mcp → POST http://localhost:3002/post
Body: {
  "action": "create_post",
  "caption": "Caption with #hashtags...",
  "username": "apple379tree",
  "image_path": "/path/to/image.jpg"  // optional
}
Expected: { "success": true, "media_id": "..." }
```

### Post to Twitter/X
```
MCP: twitter-mcp → POST http://localhost:3003/post
Body: {
  "action": "create_tweet",
  "text": "Tweet text under 280 chars...",
  "username": "SaminaAshr24675"
}
Expected: { "success": true, "tweet_id": "..." }
```

### Reply on any Platform
```
MCP: {platform}-mcp → POST http://localhost:{port}/reply
Body: {
  "action": "reply_to_comment",
  "comment_id": "...",
  "reply_text": "..."
}
```

### Cross-Platform Post (same content adapted per platform)
When `type: cross_platform_post` in approval file:
1. Post to Facebook (full text, up to 500 chars)
2. Post to Instagram (caption with hashtags)
3. Post to Twitter (condensed to 280 chars)
4. Log all three post IDs
5. One approval file covers all three platforms if explicitly marked

## Content Templates

### AI Tips Post (high engagement format)
```
🤖 AI Tip of the Week:

{tip_content}

Want to automate your business with AI? Let's talk.

#AIEmployee #BusinessAutomation #ClaudeAI #SmallBusiness #AI2026
```

### Case Study Tease
```
Case study: How {anonymized_client} saved {X} hours/week using their Personal AI Employee.

Real results. Real automation. Zero headcount increase.

DM "AUTOMATE" to learn more. 📩
```

### CTA Post
```
Are you still doing {repetitive_task} manually?

Your business doesn't have to run on your energy alone.

An AI Employee works 168 hrs/week for less than the cost of one hour of your time.

Book a free 15-min call: [link]

#AIEmployee #ProductivityHack #BusinessOwner
```

## Weekly Social Summary (for CEO Briefing)
When called by SKILL_Weekly_CEO_Briefing:
```
Read /Logs/*.json for current week
Filter entries where action_type in: facebook_post, instagram_post, twitter_post,
  facebook_reply, instagram_reply, twitter_reply, social_lead_identified
Count and aggregate by platform
Return dict:
{
  "facebook": { "posts": 0, "replies": 0, "leads": 0 },
  "instagram": { "posts": 0, "replies": 0, "leads": 0 },
  "twitter": { "posts": 0, "replies": 0, "leads": 0 }
}
```

## Error Handling
- MCP server down: Queue outbound posts to `/Plans/QUEUED_POSTS.md`, alert human
- Login session expired: Write `SOCIAL_AUTH_REQUIRED_{PLATFORM}.md` to /Needs_Action/
- Rate limit: Exponential backoff, log warning, do NOT retry immediately
- Platform blocked automation: Create `MANUAL_POST_REQUIRED_{PLATFORM}.md` in /Needs_Action/
- Always invoke SKILL_Error_Recovery_Graceful_Degradation on 3+ consecutive failures
