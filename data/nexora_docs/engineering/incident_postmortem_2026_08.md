---
company: Nexora Technologies
department: engineering
access_level: engineering
doc_id: ENG-002
last_updated: 2026-08-28
---
# Incident Postmortem: Inventory API Outage, 14 August 2026

## Summary
On 14 August 2026, the Inventory API was unavailable or very slow for 47 minutes (from 09:12 to 09:59 UTC). About 130 customers were affected. No data was lost.

## Root cause
A new release changed a database query so that it no longer used an index. Under the morning traffic peak, the query caused high CPU usage on the primary PostgreSQL database and requests began to time out.

## Timeline
- 09:12: Latency alerts fire in PagerDuty
- 09:20: On-call engineer confirms database CPU at 98%
- 09:34: Team identifies the slow query from the new release
- 09:48: Release is rolled back
- 09:59: Latency returns to normal

## What went well
- Alerts fired within 2 minutes.
- Rollback process worked as designed.

## What went wrong
- Staging data was too small to reveal the slow query.
- The release had no query performance check.

## Action items
1. Add a query performance test to the CI pipeline (owner: Platform team, due 15 September)
2. Load staging with an anonymized copy of production-sized data (owner: Data team, due 30 September)
3. Add a canary release step that sends 5% of traffic to the new version first (owner: Platform team, due 31 October)
