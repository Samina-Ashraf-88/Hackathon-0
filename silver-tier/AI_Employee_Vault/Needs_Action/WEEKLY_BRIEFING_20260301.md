---
type: weekly_briefing
skill: SKILL_Weekly_CEO_Briefing
created: "2026-03-01T16:07:20.840966"
period_start: "2026-02-23"
period_end: "2026-03-01"
month_start: "2026-03-01"
month_end: "2026-03-01"
next_briefing: "2026-03-02"
status: pending
priority: high
---

# Weekly CEO Briefing Request

**Period:** 2026-02-23 to 2026-03-01
**Generated:** Sunday, March 01, 2026 at 04:07 PM
**Next Briefing:** Monday, March 02, 2026

## Instructions for Claude
Execute **SKILL_Weekly_CEO_Briefing** completely:

1. Pull Odoo accounting data via odoo-mcp
   - Revenue: `GET http://localhost:3004/revenue?date_from=2026-03-01&date_to=2026-03-01`
   - Unpaid invoices: `GET http://localhost:3004/invoices?state=open`
   - Expenses: `GET http://localhost:3004/expenses?date_from=2026-03-01&date_to=2026-03-01`

2. Analyze `/Done/` folder for tasks completed this week (2026-02-23 to 2026-03-01)

3. Read all `/Logs/*.json` for this week and aggregate metrics

4. Analyze social media activity (Facebook, Instagram, Twitter) from logs

5. Compare against `Business_Goals.md` targets

6. Run subscription audit

7. Generate proactive suggestions (3-5 actionable items)

8. Write briefing to: `/Briefings/20260302_Monday_CEO_Briefing.md`

9. Create approval files for any suggested actions requiring human sign-off

10. Update `Dashboard.md`

11. Log completion: action_type=ceo_briefing

12. Move THIS FILE to /Done/

13. Output: `<promise>TASK_COMPLETE</promise>`

## Data Collection Checklist
- [ ] Odoo revenue data fetched
- [ ] Odoo unpaid invoices fetched
- [ ] Odoo expenses fetched
- [ ] Task completion analysis done
- [ ] Log aggregation done
- [ ] Social media summary compiled
- [ ] Goals comparison done
- [ ] Subscription audit done
- [ ] Briefing file written
- [ ] Dashboard updated
- [ ] Completion logged
