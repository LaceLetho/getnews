# Railway Phase 1 Database Verification Evidence

**Verification Date:** 2026-04-03 UTC
**Database URL:** postgresql://ballast.proxy.rlwy.net:50919/railway
**Verification Method:** Direct PostgreSQL connection via psycopg

## Results Summary

✅ **ALL TABLES VERIFIED SUCCESSFULLY**

### Table: analysis_jobs

| Property | Value |
|----------|-------|
| Exists | ✅ YES |
| Row Count | 1 |
| Status Breakdown | completed: 1 |

**Recent Sample:**
- ID: `analyze_job_5027ac458f594f1789f8bf2206f23d0f`
- Recipient Key: `api:atlas_probe`
- Time Window: 1 hour
- Created At: 2026-04-03 03:46:08.096722+00:00
- Status: **completed**

### Table: ingestion_jobs

| Property | Value |
|----------|-------|
| Exists | ✅ YES |
| Row Count | 13 |
| Status Breakdown | failed: 13 |

**Recent Samples:**
- ID: `0a4f6c2b-1d8e-47e5-aa55-f1344e3b1307`
  - Source: scheduler/crawl_only
  - Scheduled: 2026-04-03 03:26:18.927774+00:00
  - Status: **failed**
  
- ID: `910937fe-6ff8-497c-b72c-4244b5dfd215`
  - Source: scheduler/crawl_only
  - Scheduled: 2026-04-03 02:27:58.932136+00:00
  - Status: **failed**

## Notes

- The `analysis_jobs` table is working correctly with successful job completion
- The `ingestion_jobs` table exists and records jobs, but all 13 jobs have failed status
- Ingestion job failures are related to the known "LLM API密钥不能为空" issue (separate from Phase 1 validation)
- Database connectivity and schema are confirmed functional

## Verification Script

```bash
# Script used: verify_db_tables.py
.venv/bin/python verify_db_tables.py
```
