# Draft: Railway Service Split

## Requirements (confirmed)
- "拆分到 Railway 双服务 + 共享 PostgreSQL"
- "Phase 1 以 4/4 reviewer 全通过为完成标准"
- 用户担心长任务缺少状态文件，已补 `.sisyphus/boulder.json`
- 用户关注 Railway dashboard 上实际需要创建哪些服务
- "先把 Phase 1 完成，再说明 Railway 上需要做什么"

## Technical Decisions
- Phase 1 only: `analysis-service` + `ingestion` + shared PostgreSQL
- Phase 1 request contract stays `hours` + `user_id`
- Phase 1 completion gate requires Final Verification Wave 4/4 approval
- Phase 1 is complete: F1/F2/F3/F4 all approved
- Railway deployment shape: 1 PostgreSQL template service + 2 app services from the same repo
- Runtime routing is keyed by Railway service name: `crypto-news-analysis` -> `analysis-service`, `crypto-news-ingestion` -> `ingestion`

## Research Findings
- `docs/RAILWAY_DEPLOYMENT.md`: Railway topology = 2 app services + 1 PostgreSQL service
- `docs/RAILWAY_DEPLOYMENT.md`: `crypto-news-analysis` is public, `crypto-news-ingestion` is private
- `docs/RAILWAY_DEPLOYMENT.md`: migration runs as one-off `migrate-postgres`, not a permanent service
- Current verification state: API tests adapted to lifespan/app-state architecture and F2 approved

## Open Questions
- 无阻塞问题；下一步是 Railway dashboard 部署与用户侧验收

## Scope Boundaries
- INCLUDE: explain Phase 1 deliverables, required Railway resources, and deployment handoff
- EXCLUDE: Phase 2 features, dashboard execution on behalf of the user

## Current Status
- Phase 1 implementation: COMPLETE
- Final Verification Wave: COMPLETE (F1/F2/F3/F4 all approved)
- Immediate next action: user creates Railway PostgreSQL service, `crypto-news-analysis`, and `crypto-news-ingestion`, then runs deployment validation
