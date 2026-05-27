
# Wave 1 Task 2 — Decisions

## SafeDataSourceSummary
- Created as a separate `@dataclass` rather than a method on `DataSource`, matching the "safe summary" contract pattern
- Explicitly excludes `config_payload` — no field, no serialization
- Factory `SafeDataSourceSummary.from_datasource(ds)` strips sensitive fields at the boundary
- Reuses `_normalize_datasource_tags()` for tag consistency

## ABC Methods — Default vs Abstract
- All 5 new methods use default `NotImplementedError` stubs (NOT `@abstractmethod`)
- Rationale: matches existing pattern (`save_topic`, `save_topic_prompt`, `save_topic_finding`, etc.)
- Prevents breaking `SQLiteIntelligenceRepository` — concrete subclass doesn't need to implement these yet
- Implementation will be added in a later wave task

## get_raw_items_since — Backward Compatibility
- Added `datasource_ids: Optional[List[str]] = None` as last parameter with default
- None preserves existing behavior (no filtering)
- Updated both `SQLiteIntelligenceRepository` and test mock signatures
- Topic-level checkpoint semantics preserved — no per-datasource checkpoint introduced

## Validation Semantics (Documented in Docstrings)
- 404-style: unknown topic_id → ValueError
- 404-style: unknown datasource_id → ValueError  
- 400-style: non-intelligence datasource → ValueError
- Atomic: `set_topic_datasources` fails all-or-nothing
- Idempotent: add/remove silently skip already-present/missing associations
