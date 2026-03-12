---
type: system_error
component: "orchestrator"
error_category: "system"
failure_count: 5
timestamp: "2026-03-11T12:58:18.472739"
status: pending
priority: high
auto_alert: true
---

## Watchdog Alert — orchestrator

**Component:** orchestrator
**Message:** Process crashed 5 times in 1 hour
**Restarts in last hour:** 5

## Required Action
Execute SKILL_Error_Recovery_Graceful_Degradation for component: orchestrator

## What Watchdog Did
- Detected process not running
- Attempted restart (5 times in last hour)
- MAX RESTARTS REACHED — manual intervention required

## Human Action Required
Manual restart needed: check logs in AI_Employee_Vault/Logs/
