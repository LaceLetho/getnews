# Intelligence Topic System Implementation Plan

## 1. Goal

当前情报收集模块已经可以从 Telegram/V2EX 等来源定期提取 `slang` 和 `channel` 词条，并通过 `/intel_recent` 给用户做筛选。

本次改造目标是建立一个更高层级的“情报主题”系统：

1. 降低 `/intel_recent` 中黑话变体、重复词条带来的阅读噪音。
2. 用户 follow 某个词条后，系统自动将词条归属到一个研究主题。
3. 主题持续吸收新 evidence，由 LLM 增量总结并做深。
4. 系统自动将相似主题收敛合并，避免用户关注太多分散方向。
5. 用户主要通过 Telegram/HTTP 查询主题成果和自动运行日志，不需要手动管理复杂知识库。

核心原则：

```text
自动为主，查询为辅，人工只做 follow/unfollow。
```

## 2. Product Model

### 2.1 用户心智模型

用户只需要理解三个概念：

```text
词条 Entry：
系统从原始情报中提取出的 slang/channel，例如 “GPT plus”、“土区”、“某 Telegram channel”。

关注 Follow：
用户认为某个词条值得追踪，点击 follow。

主题 Topic：
系统自动把相关已关注词条收敛成的研究方向，例如 “GPT Plus 订阅渠道研究”。
```

用户不需要理解：

```text
topic embedding
收敛阈值
enrichment 触发条件
手动 topic link/unlink
```

## 3. Scope

### 3.1 First Version Must Include

1. 新增 `intelligence_topics` 表。
2. 新增 `intelligence_topic_run_logs` 表。
3. 给 `intelligence_canonical_entries` 增加 `topic_id` 字段。
4. follow 词条时自动：
   - 搜索相似 topic。
   - 匹配则挂载。
   - 不匹配则创建新 topic。
   - 写 auto_link run log。
5. collection 完成后，自动 enrich 有足够新增 evidence 的 topic。
6. 每天如果 active topic 数比上次 converge 增加，自动触发 topic convergence。
7. `/intel_recent` 增加非持久化 novelty 标注。
8. `/intel_detail` 增加所属 topic 摘要。
9. 新增 Telegram 命令：
   - `/topic_list`
   - `/topic_detail <topic_id>`
   - `/topic_logs [topic_id]`
   - `/topic_converge`
10. 新增 HTTP 接口：
    - `GET /intelligence/topics`
    - `GET /intelligence/topics/{topic_id}`
    - `GET /intelligence/topic-runs`
    - `POST /intelligence/topics/converge`

### 3.2 Explicitly Out Of Scope For First Version

不要第一版实现：

1. 手动 topic CRUD。
2. 手动 topic link/unlink。
3. 多对多 topic-entry 关系。
4. daily snapshot 表。
5. discovery novelty 入库。
6. 大规模 pairwise LLM convergence。
7. 复杂 UI 或复杂人工审批流。

## 4. Current System Context

相关现有文件：

```text
crypto_news_analyzer/domain/models.py
crypto_news_analyzer/domain/repositories.py
crypto_news_analyzer/storage/data_manager.py
crypto_news_analyzer/storage/repositories.py
crypto_news_analyzer/intelligence/pipeline.py
crypto_news_analyzer/intelligence/merge.py
crypto_news_analyzer/intelligence/search.py
crypto_news_analyzer/analyzers/intelligence_extractor.py
crypto_news_analyzer/api_server.py
crypto_news_analyzer/reporters/telegram_command_handler.py
prompts/intelligence_extraction_prompt.md
migrations/postgresql/
```

当前核心数据模型：

```text
CanonicalIntelligenceEntry
RawIntelligenceItem
ExtractionObservation
IntelligenceCrawlCheckpoint
```

当前 follow 状态：

```text
follow_status:
- follow
- unfollow
- unset
```

当前 intelligence pipeline：

```text
crawl raw items
→ save raw items
→ filter untracked slang items
→ LLM extraction
→ canonicalize observations
→ generate embeddings
→ create related candidates
→ TTL cleanup
```

本次应在 pipeline 后半段接入：

```text
→ topic enrichment
→ daily topic convergence
```

## 5. Data Model

### 5.1 Add `intelligence_topics`

PostgreSQL migration should be added as:

```text
migrations/postgresql/008_intelligence_topics.sql
```

Suggested schema:

```sql
CREATE TABLE IF NOT EXISTS intelligence_topics (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    enriched_summary TEXT,
    source_channels TEXT NOT NULL DEFAULT '[]',
    methods TEXT,
    vulnerabilities TEXT,
    latest_findings TEXT NOT NULL DEFAULT '[]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_evidence_at TIMESTAMPTZ,
    enriched_at TIMESTAMPTZ,
    embedding vector(1536),
    embedding_model TEXT,
    embedding_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intelligence_topics_active
ON intelligence_topics (is_active, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_topics_enriched_at
ON intelligence_topics (enriched_at);
```

SQLite fallback in `DataManager` should use:

```sql
embedding TEXT
```

where embedding is JSON serialized.

### 5.2 Add `intelligence_topic_run_logs`

Schema:

```sql
CREATE TABLE IF NOT EXISTS intelligence_topic_run_logs (
    id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    topic_id TEXT,
    entry_id TEXT,
    message TEXT,
    details TEXT NOT NULL DEFAULT '{}',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intelligence_topic_run_logs_created
ON intelligence_topic_run_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_topic_run_logs_topic
ON intelligence_topic_run_logs (topic_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_topic_run_logs_run_type
ON intelligence_topic_run_logs (run_type, created_at DESC);
```

Allowed `run_type` values:

```text
auto_link
enrich
converge
```

Allowed `status` values:

```text
success
skipped
failed
```

### 5.3 Modify `intelligence_canonical_entries`

Add:

```sql
ALTER TABLE intelligence_canonical_entries
ADD COLUMN IF NOT EXISTS topic_id TEXT;
```

Index:

```sql
CREATE INDEX IF NOT EXISTS idx_intelligence_canonical_entries_topic_id
ON intelligence_canonical_entries (topic_id);
```

Important design decision:

```text
One entry belongs to at most one topic.
One topic can contain many entries.
```

Do not add a topic-entry join table in first version.

## 6. Domain Models

Modify:

```text
crypto_news_analyzer/domain/models.py
```

### 6.1 Add `IntelligenceTopic`

Add dataclass near `CanonicalIntelligenceEntry`.

Fields:

```python
@dataclass
class IntelligenceTopic:
    id: str
    name: str
    description: Optional[str] = None
    enriched_summary: Optional[str] = None
    source_channels: List[Dict[str, Any]] = field(default_factory=list)
    methods: Optional[str] = None
    vulnerabilities: Optional[str] = None
    latest_findings: List[str] = field(default_factory=list)
    is_active: bool = True
    last_evidence_at: Optional[datetime] = None
    enriched_at: Optional[datetime] = None
    embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None
    embedding_updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

Required methods:

```python
create()
to_dict()
from_dict()
__post_init__()
```

Validation:

```text
id required
name required
source_channels must be list
latest_findings must be list
embedding values must be float if present
is_active normalized to bool
```

### 6.2 Add `IntelligenceTopicRunLog`

Fields:

```python
@dataclass
class IntelligenceTopicRunLog:
    id: str
    run_type: str
    status: str
    topic_id: Optional[str] = None
    entry_id: Optional[str] = None
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
```

Required methods:

```python
create()
to_dict()
from_dict()
```

Validation:

```text
run_type in {"auto_link", "enrich", "converge"}
status in {"success", "skipped", "failed"}
details must be public JSON payload
```

### 6.3 Modify `CanonicalIntelligenceEntry`

Add:

```python
topic_id: Optional[str] = None
```

Update:

```python
to_dict()
from_dict()
```

## 7. Repository Interface

Modify:

```text
crypto_news_analyzer/domain/repositories.py
```

Add imports for new models.

Add methods to `IntelligenceRepository`.

### 7.1 Topic CRUD

```python
def save_topic(self, topic: IntelligenceTopic) -> str: ...
def get_topic_by_id(self, topic_id: str) -> Optional[IntelligenceTopic]: ...
def list_topics(self, is_active: Optional[bool] = None, limit: int = 100, offset: int = 0) -> List[IntelligenceTopic]: ...
def count_topics(self, is_active: Optional[bool] = None) -> int: ...
def update_topic_embedding(self, topic_id: str, embedding: List[float], model: str) -> bool: ...
```

### 7.2 Entry Topic Association

```python
def assign_entry_to_topic(self, entry_id: str, topic_id: str) -> Optional[CanonicalIntelligenceEntry]: ...
def list_entries_by_topic(self, topic_id: str, limit: int = 100, offset: int = 0) -> List[CanonicalIntelligenceEntry]: ...
def count_entries_by_topic(self, topic_id: str) -> int: ...
```

### 7.3 Topic Evidence

```python
def list_new_topic_evidence(
    self,
    topic_id: str,
    since: Optional[datetime],
    limit: int,
) -> List[Dict[str, Any]]: ...
```

Recommended behavior:

```text
Find entries with entry.topic_id = topic_id.
Find evidence links for those entries.
Filter observed_at > since if since provided.
Join raw_intelligence_items.
Return compact evidence dicts suitable for LLM enrichment.
```

### 7.4 Topic Run Logs

```python
def save_topic_run_log(self, log: IntelligenceTopicRunLog) -> str: ...
def list_topic_run_logs(
    self,
    topic_id: Optional[str] = None,
    run_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[IntelligenceTopicRunLog]: ...
def get_latest_topic_run_log(self, run_type: str) -> Optional[IntelligenceTopicRunLog]: ...
```

### 7.5 Topic Semantic Search

```python
def semantic_search_topics(
    self,
    query_embedding: List[float],
    is_active: Optional[bool] = True,
    limit: int = 10,
) -> List[Tuple[IntelligenceTopic, float]]: ...
```

## 8. DataManager Implementation

Modify:

```text
crypto_news_analyzer/storage/data_manager.py
```

### 8.1 Table Creation

Update intelligence schema init logic to create:

```text
intelligence_topics
intelligence_topic_run_logs
```

Also add missing columns/indexes idempotently:

```text
intelligence_canonical_entries.topic_id
```

Follow existing style:

```python
self._sql(...)
if self.backend == "postgres":
    ALTER TABLE ... ADD COLUMN IF NOT EXISTS
else:
    PRAGMA table_info(...)
```

### 8.2 Serialization Helpers

Add helpers:

```python
_serialize_intelligence_topic_row(row)
_serialize_intelligence_topic_run_log_row(row)
```

JSON fields:

```text
source_channels
latest_findings
details
```

Datetime fields:

```text
last_evidence_at
embedding_updated_at
created_at
updated_at
started_at
finished_at
```

### 8.3 Topic Methods

Implement:

```python
upsert_intelligence_topic(topic: Dict[str, Any]) -> str
get_intelligence_topic_by_id(topic_id: str) -> Optional[Dict[str, Any]]
list_intelligence_topics(is_active: Optional[bool], limit: int, offset: int) -> List[Dict[str, Any]]
count_intelligence_topics(is_active: Optional[bool]) -> int
update_intelligence_topic_embedding(topic_id: str, embedding: List[float], model: str) -> bool
```

### 8.4 Entry Topic Methods

Implement:

```python
assign_intelligence_entry_to_topic(entry_id: str, topic_id: str) -> Optional[Dict[str, Any]]
list_canonical_intelligence_entries_by_topic(topic_id: str, limit: int, offset: int) -> List[Dict[str, Any]]
count_canonical_intelligence_entries_by_topic(topic_id: str) -> int
```

`assign_intelligence_entry_to_topic` should update:

```sql
UPDATE intelligence_canonical_entries
SET topic_id = ?, updated_at = CURRENT_TIMESTAMP
WHERE id = ?
```

Then return updated entry row.

### 8.5 Topic Evidence Method

Implement:

```python
list_new_intelligence_topic_evidence(topic_id: str, since: Optional[datetime], limit: int)
```

Recommended SQL shape:

```sql
SELECT
    link.entry_id,
    link.observation_id,
    link.raw_item_id,
    link.observed_at,
    raw.raw_text,
    raw.source_type,
    raw.source_id,
    raw.source_url,
    raw.published_at,
    raw.collected_at,
    entry.display_name,
    entry.entry_type,
    entry.primary_label
FROM intelligence_entry_evidence_links link
JOIN intelligence_canonical_entries entry ON entry.id = link.entry_id
JOIN raw_intelligence_items raw ON raw.id = link.raw_item_id
WHERE entry.topic_id = ?
  AND (? IS NULL OR link.observed_at > ?)
ORDER BY link.observed_at DESC
LIMIT ?
```

This compact evidence shape is enough for LLM enrichment and cheaper than full context windows.

### 8.6 Run Log Methods

Implement:

```python
upsert_intelligence_topic_run_log(log: Dict[str, Any]) -> str
list_intelligence_topic_run_logs(topic_id, run_type, limit, offset)
get_latest_intelligence_topic_run_log(run_type)
```

### 8.7 Topic Semantic Search

Implement:

```python
semantic_search_intelligence_topics(query_embedding, is_active=True, limit=10)
```

Postgres:

```sql
SELECT *, 1 - (embedding <=> CAST(? AS vector)) AS similarity
FROM intelligence_topics
WHERE embedding IS NOT NULL
  AND (? IS NULL OR is_active = ?)
ORDER BY similarity DESC
LIMIT ?
```

SQLite fallback:

```text
Load embeddings JSON.
Compute cosine similarity in Python.
Sort descending.
```

## 9. Storage Repository Implementation

Modify:

```text
crypto_news_analyzer/storage/repositories.py
```

In `SQLiteIntelligenceRepository`, add thin wrappers around DataManager methods.

Convert rows into:

```python
IntelligenceTopic.from_dict(row)
IntelligenceTopicRunLog.from_dict(row)
CanonicalIntelligenceEntry.from_dict(row)
```

## 10. Topic Embedding Text

Add helper in new service or reuse existing style.

Suggested text:

```python
def build_topic_embedding_text(topic: IntelligenceTopic) -> str:
    parts = [
        topic.name,
        topic.description or "",
        topic.enriched_summary or "",
        " ".join(channel.get("name", "") for channel in topic.source_channels),
        " ".join(channel.get("url", "") for channel in topic.source_channels),
        topic.methods or "",
        topic.vulnerabilities or "",
        " ".join(topic.latest_findings or []),
    ]
    return " ".join(part.strip() for part in parts if str(part or "").strip())
```

Use existing embedding service.

## 11. Topic Auto-Linking

Create new file:

```text
crypto_news_analyzer/intelligence/topics.py
```

Class:

```python
class IntelligenceTopicService:
    def __init__(self, intelligence_repository, search_service):
        ...
```

Main method:

```python
def ensure_entry_topic(self, entry: CanonicalIntelligenceEntry) -> IntelligenceTopic:
```

Behavior:

```text
1. If entry.topic_id exists and topic exists:
   return topic.

2. Build entry embedding text using existing IntelligenceSearchService.build_embedding_text(entry).

3. Generate embedding.

4. Search active topics with semantic_search_topics.

5. If best score >= 0.78:
   assign entry to that topic.
   write auto_link success log.
   return topic.

6. Else:
   create topic from entry:
      name = entry.display_name
      description = entry.explanation or entry.usage_summary
      enriched_summary = entry.explanation
      latest_findings = []
      source_channels = [] unless entry is channel with URL/handle info
   save topic.
   generate topic embedding.
   assign entry to topic.
   write auto_link success log.
   return topic.
```

Constants:

```python
ENTRY_TOPIC_AUTO_LINK_THRESHOLD = 0.78
```

If any exception occurs:

```text
Write auto_link failed log.
Do not fail the original follow operation.
```

## 12. Hook Auto-Link Into Follow

Existing follow paths:

```text
POST /intelligence/entries/{entry_id}/follow-status
Telegram /intel_set_follow <entry_id> follow
Inline callback follow button
```

Preferred design:

```text
Repository only changes follow_status.
Service layer handles topic auto-link.
```

Implementation steps:

1. Find central handler for follow-status changes in API and Telegram.
2. After `set_canonical_entry_follow_status(entry_id, "follow")` returns entry:
   - call `topic_service.ensure_entry_topic(entry)`.
3. Include topic summary in API response / Telegram message if available.
4. If auto-link fails, log error and still complete follow.

Do not put LLM topic logic inside repository.

## 13. Topic Enrichment

Create:

```text
crypto_news_analyzer/intelligence/topic_enricher.py
```

### 13.1 Constants

```python
MIN_NEW_EVIDENCE = 3
MAX_EVIDENCE_PER_RUN = 15
INITIAL_MAX_EVIDENCE = 20
RAW_TEXT_MAX_CHARS = 1000
MIN_ENRICH_INTERVAL_HOURS = 24
PROMPT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
DEFAULT_PROMPT_PATH = Path("prompts/topic_enrichment_prompt.md")
```

### 13.2 Trigger Logic

For each active topic:

```text
new_evidence = evidence where observed_at > topic.last_evidence_at

If topic.enriched_at is None:
    limit = INITIAL_MAX_EVIDENCE
    allow run if at least 1 evidence exists

Else:
    limit = MAX_EVIDENCE_PER_RUN
    allow run only if:
        len(new_evidence) >= MIN_NEW_EVIDENCE
        OR now - topic.enriched_at >= MIN_ENRICH_INTERVAL_HOURS and len(new_evidence) > 0
```

### 13.3 LLM Runtime

Use:

```text
provider: opencode-go
model: deepseek-v4-pro
thinking_level: high
```

Reuse `resolve_model_runtime` pattern from `IntelligenceExtractor`.

Use OpenAI-compatible client exactly like `IntelligenceExtractor`.

### 13.4 LLM Request

Use response format:

```python
response_format={"type": "json_object"}
```

Extra body:

```python
{"thinking": {"type": "enabled"}}
```

for opencode-go + deepseek-v4-pro, same as current extractor.

### 13.5 Prompt Output Schema

Create prompt:

```text
prompts/topic_enrichment_prompt.md
```

Expected JSON:

```json
{
  "enriched_summary": "string",
  "source_channels": [
    {
      "name": "string",
      "url": "string",
      "type": "telegram|website|forum|unknown",
      "confidence": 0.0,
      "evidence": "string"
    }
  ],
  "methods": "string",
  "vulnerabilities": "string",
  "latest_findings": [
    "string"
  ]
}
```

### 13.6 Merge Behavior

When LLM returns data:

```text
enriched_summary:
  Replace with returned version.

source_channels:
  Merge existing + returned.
  Deduplicate by normalized url if present, else normalized name.
  Keep higher confidence.

methods:
  Replace with returned consolidated methods.

vulnerabilities:
  Replace with returned consolidated vulnerabilities.

latest_findings:
  Merge returned findings with existing.
  Keep latest 20 findings max.

last_evidence_at:
  Set to max observed_at among processed evidence.

enriched_at:
  now.
```

After updating topic:

```text
Regenerate topic embedding only if meaningful text changed.
Write enrich success log.
```

On skip:

```text
Write skipped log only if useful, not every topic every hour.
Recommended: write one aggregated skipped log per run.
```

On failure:

```text
Write enrich failed log with error message.
Continue other topics.
```

## 14. Topic Convergence

Create:

```text
crypto_news_analyzer/intelligence/topic_converger.py
```

### 14.1 Constants

```python
CONVERGENCE_AUTO_MERGE_THRESHOLD = 0.88
MAX_CONVERGENCE_PAIRS_PER_RUN = 5
PROMPT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
DEFAULT_PROMPT_PATH = Path("prompts/topic_convergence_prompt.md")
```

### 14.2 Daily Trigger Rule

User requirement:

```text
每天如果主题数比前一天有增加就自动触发合并收敛。
```

Simplified implementation without snapshot table:

```text
1. Find latest run log where run_type='converge'.
2. Read details.active_topic_count_after or details.active_topic_count_before.
3. current_count = count active topics.
4. If no previous converge log:
   run convergence once.
5. Else if current_count > previous_count:
   run convergence.
6. Else:
   skip and write one converge skipped log.
```

To avoid running multiple times per day:

```text
If latest converge log created_at is today:
    skip.
```

### 14.3 Candidate Selection

```text
1. List active topics with embeddings.
2. For each topic, semantic search similar active topics.
3. Keep pairs:
   - different topic id
   - similarity >= 0.88
4. Deduplicate unordered pairs.
5. Sort by similarity desc.
6. Take max 5 pairs.
```

### 14.4 LLM Confirmation

For each pair:

```text
Call LLM with both topics.
Require JSON output.
Only merge if:
    embedding similarity >= 0.88
    AND LLM returns should_merge = true
```

Prompt:

```text
prompts/topic_convergence_prompt.md
```

Expected JSON:

```json
{
  "should_merge": true,
  "reason": "string",
  "merged_name": "string",
  "merged_description": "string",
  "merged_summary": "string",
  "merged_source_channels": [],
  "merged_methods": "string",
  "merged_vulnerabilities": "string",
  "merged_latest_findings": []
}
```

### 14.5 Merge Behavior

If merging topic B into topic A:

```text
1. Choose keeper:
   - topic with more entries, else older topic.
2. Move entries:
   UPDATE intelligence_canonical_entries
   SET topic_id = keeper.id
   WHERE topic_id = merged.id

3. Update keeper:
   name = merged_name
   description = merged_description
   enriched_summary = merged_summary
   source_channels = merged_source_channels
   methods = merged_methods
   vulnerabilities = merged_vulnerabilities
   latest_findings = merged_latest_findings
   updated_at = now

4. Mark merged topic:
   is_active = false
   updated_at = now

5. Regenerate keeper embedding.

6. Write converge success log:
   details includes merged_topic_id, keeper_topic_id, similarity, reason.
```

If LLM says no:

```text
Write converge skipped log with reason.
```

## 15. Discovery Novelty Annotation

Do not persist novelty in DB.

Implement at query/formatting level.

### 15.1 Behavior

For `/intel_recent` and `GET /intelligence/discovery`:

```text
1. Load unset entries as current behavior.
2. For each entry, use embedding search against:
   - canonical entries with tracking_scope='all'
   - exclude itself
3. Get best match.
4. Attach transient annotation:
   novelty_status:
      high
      similar
      duplicate_like
   similar_entry:
      id
      display_name
      score
```

Recommended thresholds:

```text
score >= 0.90:
    duplicate_like
    display lower priority

0.82 <= score < 0.90:
    similar
    normal display with warning

score < 0.82:
    high
```

### 15.2 Telegram Display

Example:

```text
土耳其礼品卡
⚠️ 与「土区」高度相似，相似度 0.89
```

### 15.3 API Response

Add optional field to entry response only for discovery list:

```json
"novelty": {
  "status": "similar",
  "similar_entry_id": "...",
  "similar_entry_name": "土区",
  "score": 0.89
}
```

If adding this into `CanonicalIntelligenceEntry` is awkward, format it in API response layer as a dict wrapper.

## 16. API Endpoints

Modify:

```text
crypto_news_analyzer/api_server.py
```

### 16.1 Add Topic List

```http
GET /intelligence/topics
```

Query params:

```text
active_only: bool = true
page: int = 1
page_size: int = 20
```

Response:

```json
{
  "items": [
    {
      "id": "...",
      "name": "...",
      "description": "...",
      "enriched_summary": "...",
      "entry_count": 3,
      "enriched_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 20
}
```

### 16.2 Add Topic Detail

```http
GET /intelligence/topics/{topic_id}
```

Response includes:

```json
{
  "topic": { ... },
  "entries": [ ... ],
  "recent_logs": [ ... ]
}
```

### 16.3 Add Topic Runs

```http
GET /intelligence/topic-runs
```

Query params:

```text
topic_id: optional
run_type: optional
page
page_size
```

### 16.4 Add Manual Converge Trigger

```http
POST /intelligence/topics/converge
```

Response:

```json
{
  "success": true,
  "merged_count": 1,
  "skipped_count": 2,
  "message": "..."
}
```

### 16.5 Enhance Existing Follow Status Endpoint

Existing:

```http
POST /intelligence/entries/{entry_id}/follow-status
```

When payload follow_status is `"follow"`:

```text
After status update, call topic_service.ensure_entry_topic(entry).
```

Response should include:

```json
"topic": {
  "id": "...",
  "name": "..."
}
```

If topic linking fails:

```json
"topic_error": "..."
```

Do not fail the whole follow request.

## 17. Telegram Commands

Modify:

```text
crypto_news_analyzer/reporters/telegram_command_handler.py
```

### 17.1 Add `/topic_list`

Output:

```text
📚 情报主题

1. GPT Plus 订阅渠道研究
   词条: 4 | 最近更新: 2026-05-13
   /topic_detail xxx

2. 土耳其区套利
   词条: 3 | 最近更新: 2026-05-13
   /topic_detail yyy
```

### 17.2 Add `/topic_detail <topic_id>`

Output:

```text
🔬 GPT Plus 订阅渠道研究

📋 深度摘要
...

🔗 已挖掘渠道
1. @xxx - ...
2. example.com - ...

🛠 方法
...

🧨 漏洞/内幕
...

🆕 最新发现
• ...
• ...

📌 关联词条
GPT plus, 土区, 土耳其礼品卡
```

### 17.3 Add `/topic_logs [topic_id]`

Output recent logs:

```text
🧾 Topic Run Logs

2026-05-13 12:00 enrich success
主题: GPT Plus 订阅渠道研究
处理新 evidence: 8 条

2026-05-13 00:10 converge success
合并: A <- B
原因: ...
```

### 17.4 Add `/topic_converge`

Manual trigger.

Output:

```text
收敛执行完成：
合并 1 个主题
跳过 2 个候选
详情见 /topic_logs
```

### 17.5 Enhance `/intel_detail <entry_id>`

If entry has topic:

```text
🔬 所属主题：GPT Plus 订阅渠道研究

📋 主题摘要
...
```

### 17.6 Enhance Follow Result

When user follows an entry:

```text
已关注：GPT plus
已自动归属主题：GPT Plus 订阅渠道研究
```

or:

```text
已关注：GPT plus
已自动创建新主题：GPT plus
```

## 18. Pipeline Integration

Modify:

```text
crypto_news_analyzer/intelligence/pipeline.py
```

Constructor adds optional dependencies:

```python
topic_enricher: Any = None
topic_converger: Any = None
```

Result dict adds:

```python
"topics_enriched": 0
"topics_converged": 0
"topic_convergence_skipped": False
```

After all datasource processing and before TTL cleanup, add:

```python
if self.topic_enricher:
    result["topics_enriched"] = self.topic_enricher.enrich_due_topics()

if self.topic_converger:
    convergence_result = self.topic_converger.run_daily_if_needed()
    result["topics_converged"] = convergence_result.get("merged_count", 0)
```

Important:

```text
Do not run enrichment per source.
Run once after all sources complete.
```

This avoids repeated LLM calls in one collection cycle.

## 19. Wiring

Find where `IntelligencePipeline` is constructed, likely in:

```text
crypto_news_analyzer/execution_coordinator.py
```

Add construction of:

```python
topic_service = IntelligenceTopicService(...)
topic_enricher = TopicEnricher(...)
topic_converger = TopicConverger(...)
```

Pass into pipeline.

Also expose `topic_service` to API and Telegram command handler where follow-status is handled.

If dependency injection is complex, start with helper factory functions near pipeline setup.

## 20. Config

Modify:

```text
config.jsonc
```

Add under `intelligence_collection`:

```jsonc
"topic_enrichment": {
  "enabled": true,
  "provider": "opencode-go",
  "model": "deepseek-v4-pro",
  "thinking_level": "high",
  "min_new_evidence": 3,
  "max_evidence_per_run": 15,
  "initial_max_evidence": 20,
  "raw_text_max_chars": 1000,
  "min_enrich_interval_hours": 24,
  "entry_topic_auto_link_threshold": 0.78,
  "convergence_similarity_threshold": 0.88,
  "max_convergence_pairs_per_run": 5
},
"discovery_novelty": {
  "enabled": true,
  "similar_threshold": 0.82,
  "duplicate_like_threshold": 0.90
}
```

Add config dataclasses in:

```text
crypto_news_analyzer/models.py
```

Suggested:

```python
@dataclass
class IntelligenceTopicEnrichmentConfig:
    enabled: bool = True
    provider: str = "opencode-go"
    model: str = "deepseek-v4-pro"
    thinking_level: str = "high"
    min_new_evidence: int = 3
    max_evidence_per_run: int = 15
    initial_max_evidence: int = 20
    raw_text_max_chars: int = 1000
    min_enrich_interval_hours: int = 24
    entry_topic_auto_link_threshold: float = 0.78
    convergence_similarity_threshold: float = 0.88
    max_convergence_pairs_per_run: int = 5

@dataclass
class IntelligenceDiscoveryNoveltyConfig:
    enabled: bool = True
    similar_threshold: float = 0.82
    duplicate_like_threshold: float = 0.90
```

Add fields to `IntelligenceConfig`:

```python
topic_enrichment: IntelligenceTopicEnrichmentConfig
discovery_novelty: IntelligenceDiscoveryNoveltyConfig
```

## 21. Prompts

### 21.1 `prompts/topic_enrichment_prompt.md`

Content requirements:

```text
你是一个中文情报分析师。
你会收到一个情报主题的当前知识，以及该主题下多个词条的最新 evidence。
你要将新信息增量合并到主题中。
不要输出 Markdown。
必须输出合法 JSON。
不要泄露任何敏感 token、私钥、账号密码。
如 evidence 不足，保持原有知识，不要编造。
```

Output schema:

```json
{
  "enriched_summary": "string",
  "source_channels": [
    {
      "name": "string",
      "url": "string",
      "type": "telegram|website|forum|unknown",
      "confidence": 0.0,
      "evidence": "string"
    }
  ],
  "methods": "string",
  "vulnerabilities": "string",
  "latest_findings": [
    "string"
  ]
}
```

### 21.2 `prompts/topic_convergence_prompt.md`

Content requirements:

```text
你是一个中文情报主题归并专家。
你会收到两个主题的名称、摘要、渠道、方法、漏洞、最新发现和关联词条。
判断它们是否应合并。
只有当两个主题本质上研究同一条线索/同一类套利/同一渠道生态时，才 should_merge=true。
相近但方向不同，不要合并。
必须输出合法 JSON。
```

Output schema:

```json
{
  "should_merge": true,
  "reason": "string",
  "merged_name": "string",
  "merged_description": "string",
  "merged_summary": "string",
  "merged_source_channels": [],
  "merged_methods": "string",
  "merged_vulnerabilities": "string",
  "merged_latest_findings": []
}
```

## 22. Testing Plan

Add or update tests under:

```text
tests/
```

### 22.1 Model Tests

Test:

```text
IntelligenceTopic.create()
IntelligenceTopic.to_dict/from_dict()
IntelligenceTopicRunLog.create()
CanonicalIntelligenceEntry.topic_id roundtrip
```

### 22.2 DataManager Tests

Test:

```text
create/list/get topic
assign entry to topic
list entries by topic
save/list topic run logs
```

### 22.3 Topic Service Tests

Mock embedding/search.

Test:

```text
followed entry auto-links to existing similar topic
followed entry creates new topic when no match
auto_link failure does not fail follow
```

### 22.4 Enricher Tests

Mock LLM response.

Test:

```text
skip topic with no new evidence
skip topic below min evidence and interval
enrich initial topic with evidence
merge source_channels dedup
update last_evidence_at
write success/failure logs
```

### 22.5 Converger Tests

Mock LLM response.

Test:

```text
skip if already ran today
skip if topic count not increased
select only high similarity pairs
merge only if LLM should_merge=true
move entries from merged topic to keeper
write logs
```

### 22.6 API Tests

Test:

```text
GET /intelligence/topics
GET /intelligence/topics/{id}
GET /intelligence/topic-runs
POST /intelligence/topics/converge
follow-status response includes topic
```

### 22.7 Telegram Tests

If existing test pattern supports it, test formatting helpers:

```text
topic list formatting
topic detail formatting
intel detail includes topic
```

## 23. Implementation Order

Follow this exact sequence:

### Step 1: Data Model Foundation

1. Add migration `008_intelligence_topics.sql`.
2. Update `DataManager` table creation for SQLite/Postgres.
3. Add `topic_id` column handling in canonical entry serialization.

### Step 2: Domain Models

1. Add `IntelligenceTopic`.
2. Add `IntelligenceTopicRunLog`.
3. Add `topic_id` to `CanonicalIntelligenceEntry`.

### Step 3: Repository Layer

1. Add abstract methods to `IntelligenceRepository`.
2. Implement DataManager methods.
3. Implement SQLiteIntelligenceRepository wrappers.

### Step 4: Topic Service

1. Create `intelligence/topics.py`.
2. Implement topic embedding text helper.
3. Implement `ensure_entry_topic`.
4. Add run logs.

### Step 5: Follow Integration

1. Find API follow-status handler.
2. Call `ensure_entry_topic` after follow.
3. Find Telegram follow handler/callback.
4. Call `ensure_entry_topic` after follow.
5. Include topic name in user response.

### Step 6: Topic Enricher

1. Add prompt file.
2. Implement LLM client using `IntelligenceExtractor` pattern.
3. Implement trigger logic.
4. Implement merge behavior.
5. Write logs.

### Step 7: Topic Converger

1. Add prompt file.
2. Implement daily trigger logic.
3. Implement candidate selection.
4. Implement LLM confirmation.
5. Implement merge.
6. Write logs.

### Step 8: Pipeline Integration

1. Add optional `topic_enricher` and `topic_converger`.
2. Run enrichment once after all sources.
3. Run daily convergence once after enrichment.
4. Update result counters.

### Step 9: Discovery Novelty

1. Add query-time novelty annotation helper.
2. Integrate in API discovery endpoint.
3. Integrate in Telegram `/intel_recent` formatting.
4. Do not persist novelty.

### Step 10: API Endpoints

1. Add topic list endpoint.
2. Add topic detail endpoint.
3. Add topic run logs endpoint.
4. Add manual converge endpoint.

### Step 11: Telegram Commands

1. Add `/topic_list`.
2. Add `/topic_detail`.
3. Add `/topic_logs`.
4. Add `/topic_converge`.
5. Enhance `/intel_detail`.

### Step 12: Tests and Verification

Run:

```bash
uv run pytest tests/
uv run black crypto_news_analyzer/ tests/
uv run flake8 crypto_news_analyzer/
uv run mypy crypto_news_analyzer/
```

If full suite is too slow, first run targeted tests:

```bash
uv run pytest tests/test_intelligence_merge.py -v
uv run pytest tests/test_intelligence_ingestion_runtime.py -v
uv run pytest tests/test_intelligence_extraction.py -v
```

## 24. Cost Control Rules

These rules are mandatory:

1. Do not call LLM for every topic every collection cycle.
2. Enrich only if:
   - topic has new evidence, and
   - evidence count >= 3, or last enrich older than 24h.
3. Limit evidence per enrichment:
   - first run max 20
   - normal run max 15
4. Truncate each raw_text to 1000 chars.
5. Convergence:
   - only once per day
   - only if topic count increased
   - max 5 candidate pairs
   - only call LLM for similarity >= 0.88
6. Auto merge only if:
   - embedding similarity >= 0.88
   - LLM returns `should_merge=true`

## 25. Architecture Simplicity Rules

These rules are mandatory:

1. One entry has one `topic_id`.
2. One topic has many entries.
3. Do not add many-to-many topic-entry table.
4. Do not add manual topic CRUD in first version.
5. Do not persist discovery novelty annotations.
6. Keep user operations simple:
   - user follows/unfollows entries
   - system handles topics automatically
   - user reads topic outputs/logs

## 26. Acceptance Criteria

Implementation is complete when:

1. A user can follow a new intel entry and the entry gets a topic automatically.
2. If a similar active topic exists, the entry attaches to it.
3. If no similar topic exists, a new topic is created.
4. Topic auto-link writes a run log.
5. Collection cycle enriches due topics only.
6. Enrichment updates summary/channels/methods/vulnerabilities/latest findings.
7. Convergence runs at most once per day and only when topic count increased.
8. Convergence can automatically merge highly similar topics after LLM confirmation.
9. `/intel_recent` shows similarity warnings for low-novelty entries.
10. `/intel_detail` shows the linked topic summary.
11. `/topic_list`, `/topic_detail`, `/topic_logs`, `/topic_converge` work.
12. HTTP topic list/detail/log/converge endpoints work.
13. Tests pass.
14. No secrets are exposed in prompts, logs, or responses.

## 27. Suggested Commit Message

```text
feat: add intelligence topic enrichment and convergence
```
