# Draft: Railway Phase 1 Validation

## Requirements (confirmed)
- phase1 已基本完成
- 已部署 3 个 Railway services
- Telegram 中使用 analyze 命令触发成功
- 需要确认接下来应做哪些验证
- 需要的是快速验证清单
- 只覆盖 phase1

## Technical Decisions
- 范围锁定为 split deployment 的 Phase 1 验证，不覆盖 Phase 2/后续优化
- 输出形态优先为快速验证清单，而非完整执行计划
- 验证内容优先基于仓库内现有 split plan、部署文档、测试与 health-check 能力制定

## Research Findings
- `.sisyphus/plans/railway-service-split.md`: 主 split plan，包含 11 个任务、Definition of Done、Final Verification Wave 与 Phase 1 排除项
- `docs/RAILWAY_DEPLOYMENT.md`: Railway split deployment、验证、回滚与环境约束文档
- `docs/AI_ANALYZE_API_GUIDE.md`: `/analyze` 的 POST → poll → result 异步契约
- `README.md` / `AGENTS.md`: Telegram `/analyze` 与测试/运行命令入口
- `.opencode/skills/crypto-news-debug/SKILL.md`: Railway GraphQL 日志与部署调试能力
- `pyproject.toml`: 已有 pytest / pytest-asyncio / hypothesis / coverage 配置
- `tests/test_api_server.py`: 覆盖 `/health`、Bearer auth、`/analyze` 相关 API 行为
- `tests/test_telegram_command_handler_analyze.py`: 覆盖 Telegram `/analyze` 指令行为
- `tests/test_ingestion_runtime.py`: 覆盖 ingestion runtime / mode 相关验证
- `Dockerfile` + `docker-entrypoint.sh`: 已有 health check、service mode 与启动约束；未发现专门的 Railway split smoke script 或 CI workflow

## Open Questions
- Final Verification Wave 是否已经跑过
- 是否已有 `.sisyphus/evidence/` 里的验证证据文件
- 这次是常规验收，还是有某个具体现象/故障想重点排查

## Pending Follow-up
- 自定义域名 `news.tradao.xyz` 当前 `/health` 返回 404，需后续核对 domain 绑定/路由
- 合法 `API_KEY` 下的 `/analyze` 202 -> poll -> result 仍待手动验收
- analysis job 重启后持久化仍待手动验收
- `analysis_jobs` / `ingestion_jobs` 表查询仍待手动验收
- ingestion 运行时出现 `LLM API密钥不能为空`，需要先定位 root cause 并修复

## Scope Boundaries
- INCLUDE: phase1 部署后验证、服务连通性、Telegram analyze 端到端链路、回归与故障场景、Definition of Done 对照
- EXCLUDE: 直接修改代码、直接执行修复、Phase 2 新功能实现、CI/新 smoke script 搭建
