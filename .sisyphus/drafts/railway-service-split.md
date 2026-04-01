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
- Final completion gate is blocked on F2 code-quality/test adaptation

## Research Findings
- `docs/RAILWAY_DEPLOYMENT.md`: Railway topology = 2 app services + 1 PostgreSQL service
- `docs/RAILWAY_DEPLOYMENT.md`: `crypto-news-analysis` is public, `crypto-news-ingestion` is private
- `docs/RAILWAY_DEPLOYMENT.md`: migration runs as one-off `migrate-postgres`, not a permanent service

## Open Questions
- 暂不展开 Railway dashboard 操作清单；待 Phase 1 完成后再交付

## Scope Boundaries
- INCLUDE: explain Phase 1 deliverables and required Railway resources
- EXCLUDE: starting F2 fixes, implementation changes, dashboard execution
