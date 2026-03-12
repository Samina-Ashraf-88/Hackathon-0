---
type: system_error
component: "instagram_watcher"
error_category: "system"
failure_count: 5
timestamp: "2026-03-11T13:02:43.177744"
status: pending
priority: high
auto_alert: true
---

## Watchdog Alert — instagram_watcher

**Component:** instagram_watcher
**Message:** Process crashed 5 times in 1 hour
**Restarts in last hour:** 5

## Required Action
Execute SKILL_Error_Recovery_Graceful_Degradation for component: instagram_watcher

## What Watchdog Did
- Detected process not running
- Attempted restart (5 times in last hour)
- MAX RESTARTS REACHED — manual intervention required

## Human Action Required
Manual restart needed: check logs in AI_Employee_Vault/Logs/
