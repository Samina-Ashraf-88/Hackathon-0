---
type: system_error
component: "gmail_watcher"
error_category: "system"
failure_count: 5
timestamp: "2026-03-11T12:58:18.831658"
status: pending
priority: high
auto_alert: true
---

## Watchdog Alert — gmail_watcher

**Component:** gmail_watcher
**Message:** Process crashed 5 times in 1 hour
**Restarts in last hour:** 5

## Required Action
Execute SKILL_Error_Recovery_Graceful_Degradation for component: gmail_watcher

## What Watchdog Did
- Detected process not running
- Attempted restart (5 times in last hour)
- MAX RESTARTS REACHED — manual intervention required

## Human Action Required
Manual restart needed: check logs in AI_Employee_Vault/Logs/
