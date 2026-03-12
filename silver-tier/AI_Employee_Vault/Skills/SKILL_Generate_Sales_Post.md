# SKILL: Generate LinkedIn Sales Post

## Description
Drafts a LinkedIn post designed to generate business leads. Uses business data
from Business_Goals.md, Company_Handbook.md, and recent activity to craft
relevant, value-driven content. Always creates an approval file before any post
is scheduled or published.

## Trigger
- Manually: `claude --print "Execute SKILL_Generate_Sales_Post"`
- Scheduled: Orchestrator calls this on configured schedule (e.g., Mon/Wed/Fri 9AM)
- Event-based: After completing a notable task (e.g., delivered a project)

---

## Prompt Template

```
You are executing the Generate LinkedIn Sales Post skill.

STEP 1 — GATHER CONTEXT
Read the following files:
  - /Business_Goals.md → services to promote, content pillars
  - /Company_Handbook.md → tone, rules, LinkedIn guidelines
  - /Done/ → recent completed tasks (for content inspiration)
  - /Briefings/ → any recent CEO briefing for metrics to share

STEP 2 — SELECT CONTENT PILLAR
Choose the most relevant pillar from Business_Goals.md "LinkedIn Content Pillars":
  1. AI & Automation tips for business owners
  2. Case studies / results
  3. Industry trends
  4. Behind-the-scenes building
  5. Call-to-action / offer

Rotate pillars — check which was used most recently in /Plans/ or /Done/.

STEP 3 — DRAFT POST
Write a LinkedIn post following this structure:
  HOOK (1-2 lines): Attention-grabbing opening. Ask a question or share a bold stat.
  VALUE (3-5 lines): Deliver the promised insight. Be specific and actionable.
  PROOF (1-2 lines): Brief social proof or result (can be anonymized).
  CTA (1-2 lines): Soft call-to-action (comment, DM, link in comments).
  HASHTAGS: 3-5 relevant hashtags (#AIAutomation #BusinessGrowth #Consulting etc.)

Post length: 150-300 words. Use line breaks for readability.

STEP 4 — CREATE APPROVAL FILE
Save to: /Pending_Approval/LINKEDIN_POST_{YYYY-MM-DD}_{pillar}.md

Contents:
  ---
  type: linkedin_post_approval
  platform: LinkedIn
  account: https://www.linkedin.com/in/samina-ashraf-8386453b3
  pillar: {content_pillar}
  created: {timestamp}
  scheduled_for: {suggested date/time}
  status: pending
  ---
  ## Draft Post
  {full post text}
  ## Suggested Hashtags
  {hashtags}
  ## Post When Approved
  After approval, run: python linkedin_poster.py --file {this_file}
  ## To Approve: Move to /Approved/
  ## To Reject/Edit: Move to /Rejected/ and create a new version

STEP 5 — UPDATE DASHBOARD
Append to Dashboard.md:
  - [{timestamp}] LinkedIn post drafted: {pillar} — pending approval
```

---

## Post Templates by Pillar

### Template 1 — AI Automation Tip
```
Are you still doing [TASK] manually?

Here's how I automated it in [TIME] using Claude Code:

1. [Step 1 — specific and simple]
2. [Step 2]
3. [Step 3]

Result: [Time saved / cost saved / quality improved]

The best part? You don't need to be a developer to set this up.

If you're curious how this could work for YOUR business, drop a comment or DM me.

#AIAutomation #BusinessEfficiency #ClaudeAI #SmallBusiness
```

### Template 2 — Results / Case Study
```
A client came to me with [PROBLEM].

They were spending [X hours/dollars] per week on [task].

We built a simple AI agent that:
✅ [Outcome 1]
✅ [Outcome 2]
✅ [Outcome 3]

Total setup time: [X hours]. Cost saved monthly: [$X].

This is what AI automation looks like in practice — not sci-fi, just smart tools.

Want to see if something similar could work for you?
→ DM me "AUTOMATE" and I'll share how we did it.

#AIForBusiness #Automation #ROI
```

### Template 3 — Call to Action
```
I'm opening [X] spots this month for a FREE 30-minute AI Audit.

In 30 minutes, I'll show you:
→ Which tasks in your business can be automated TODAY
→ How much time/money you'd save
→ What tools you actually need (hint: not many)

No pitch. No fluff. Just actionable insights.

Comment "AUDIT" below or send me a DM.

[Only X spots remaining — first come, first served]

#FreeConsultation #AIStrategy #BusinessGrowth
```

---

## Example Usage

```bash
# Generate a new sales post
claude --print "Execute SKILL_Generate_Sales_Post per /Skills/SKILL_Generate_Sales_Post.md. Use content pillar 1." \
  --cwd /path/to/AI_Employee_Vault

# After approval, post it
python watchers/linkedin_poster.py --file "AI_Employee_Vault/Approved/LINKEDIN_POST_2026-02-25_automation_tips.md"
```
