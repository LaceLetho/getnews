# Sisyphus Active-Artifact Cleanup

## TL;DR
> **Summary**: Archive completed `.sisyphus` planning artifacts so the active area only contains the in-flight `railway-service-split` materials. Use an explicit allowlist; never infer archive eligibility from checkbox state.
> **Deliverables**:
> - `.sisyphus/archive/plans/` with completed plan files moved in
> - `.sisyphus/archive/notepads/` with completed notepad directories moved in
> - Active area reduced to `railway-service-split` artifacts only
> - Move-only verification evidence and single-scope commit
> **Effort**: Quick
> **Parallel**: NO
> **Critical Path**: 1 → 2 → 3 → 4

## Context
### Original Request
- 清理 `.sisyphus` 中除当前推进的 `railway-service-split` 外的 plan 相关文档，避免干扰 agent 执行当前 plan。

### Interview Summary
- 当前继续推进的 plan 只有 `.sisyphus/plans/railway-service-split.md`。
- 用户选择“归档已完成”而不是直接删除。
- 目标是减少 active 区域噪音，同时保留历史记录和可逆性。

### Metis Review (gaps addressed)
- 不允许根据 `[x]` 勾选状态判断是否归档；必须使用显式 allowlist。
- `railway-service-split.md` 即使勾选已满，也仍视为当前 active plan。
- `railway-opencode-skill.md` 没有 companion notepad，执行时必须把“缺失 companion”视为正常情况处理。
- `drafts/sisyphus-cleanup.md` 仅为规划阶段临时草稿；进入执行前由 Prometheus 删除，不纳入 executor 的 active keep-set。

## Work Objectives
### Core Objective
将 `.sisyphus` 的活跃工作集缩减为当前仍在推进的 `railway-service-split` 相关材料，并把已完成事项移动到统一归档区，降低 agent 在 active 路径上的扫描噪音。

### Deliverables
- 归档目录：`.sisyphus/archive/plans/`
- 归档目录：`.sisyphus/archive/notepads/`
- 活跃保留清单：
  - `.sisyphus/plans/railway-service-split.md`
  - `.sisyphus/drafts/railway-service-split.md`
  - `.sisyphus/notepads/railway-service-split/`
- 归档移动清单：
  - `.sisyphus/plans/two-layer-dedup-analyze-flow.md`
  - `.sisyphus/notepads/two-layer-dedup-analyze-flow/`
  - `.sisyphus/plans/railway-opencode-skill.md`

### Definition of Done (verifiable conditions with commands)
- `test -f .sisyphus/plans/railway-service-split.md`
- `test -f .sisyphus/drafts/railway-service-split.md`
- `test -d .sisyphus/notepads/railway-service-split`
- `test ! -f .sisyphus/plans/two-layer-dedup-analyze-flow.md`
- `test ! -d .sisyphus/notepads/two-layer-dedup-analyze-flow`
- `test ! -f .sisyphus/plans/railway-opencode-skill.md`
- `test -f .sisyphus/archive/plans/two-layer-dedup-analyze-flow.md`
- `test -d .sisyphus/archive/notepads/two-layer-dedup-analyze-flow`
- `test -f .sisyphus/archive/plans/railway-opencode-skill.md`
- `git diff --name-status --cached --find-renames` 仅显示约定的 `.sisyphus` 路径变更

### Must Have
- 仅使用显式清单移动文件/目录，不使用通配符或基于文本内容的启发式判断。
- 保留 `railway-service-split` plan、draft、notepad 在 active area。
- archive 保持 subtype 结构，便于回滚：`plans/` 与 `notepads/` 分开。
- 若预检清单与计划不一致，立即停止，不做任何移动。

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- 不删除历史文档。
- 不修改任何 plan/notepad 内容，只允许 move/rename。
- 不移动 `.sisyphus/` 之外的任何文件。
- 不根据“勾选完成”或“文件名猜测”判断归档对象。
- 不引入新的归档框架、README、自动化脚本或 repo 级改造。

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after with shell assertions + git scope verification
- QA policy: Every task includes executable happy-path + edge-case checks
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> This is intentionally sequential because every move depends on the verified manifest from the previous step.

Wave 1: manifest lock + archive move + postflight verification (`1,2,3,4`)

### Dependency Matrix (full, all tasks)
- `1` blocks `2,3,4`
- `2` blocks `3,4`
- `3` blocks `4`
- `4` precedes Final Verification Wave

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 4 tasks → `quick`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. 锁定 keep/archive manifest 并执行预检

  **What to do**: 明确唯一允许保留的 active artifacts 与唯一允许归档的 completed artifacts；先验证所有源路径存在、所有目标路径不存在，再开始任何移动。执行前假定 `drafts/sisyphus-cleanup.md` 已由 Prometheus 清理。
  **Must NOT do**: 不使用 `*`、`**`、批量 mv；不根据 plan 勾选状态决定归档对象；不提前创建 commit。

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: 纯清单与预检工作，逻辑简单但需要精确
  - Skills: [`git-master`] — 需要后续 git-scope 校验与原子提交习惯
  - Omitted: `['playwright']` — 无浏览器或 UI

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: `2,3,4` | Blocked By: none

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `.sisyphus/plans/railway-service-split.md:1-645` — 当前唯一 active plan，必须保留在 active area
  - Pattern: `.sisyphus/plans/two-layer-dedup-analyze-flow.md:1-80` — 已完成且待归档的 plan 文件
  - Pattern: `.sisyphus/plans/railway-opencode-skill.md:1-80` — 已完成且待归档的 plan 文件
  - Pattern: `.sisyphus/drafts/` — 当前 active drafts 目录；执行时只保留 `railway-service-split.md`
  - Pattern: `.sisyphus/notepads/railway-service-split/` — 当前 active notepad，必须保留
  - Pattern: `.sisyphus/notepads/two-layer-dedup-analyze-flow/` — 已完成且待归档的 notepad 目录

  **Acceptance Criteria** (agent-executable only):
  - [ ] `test -f .sisyphus/plans/railway-service-split.md`
  - [ ] `test -f .sisyphus/drafts/railway-service-split.md`
  - [ ] `test -d .sisyphus/notepads/railway-service-split`
  - [ ] `test -f .sisyphus/plans/two-layer-dedup-analyze-flow.md`
  - [ ] `test -d .sisyphus/notepads/two-layer-dedup-analyze-flow`
  - [ ] `test -f .sisyphus/plans/railway-opencode-skill.md`
  - [ ] `test ! -e .sisyphus/archive/plans/two-layer-dedup-analyze-flow.md`
  - [ ] `test ! -e .sisyphus/archive/notepads/two-layer-dedup-analyze-flow`
  - [ ] `test ! -e .sisyphus/archive/plans/railway-opencode-skill.md`

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Preflight inventory exactly matches expected cleanup set
    Tool: Bash
    Steps: run the exact `test` assertions above and tee output to `.sisyphus/evidence/task-1-preflight.txt`
    Expected: all expected source paths exist, all expected archive targets do not yet exist, exit code 0
    Evidence: .sisyphus/evidence/task-1-preflight.txt

  Scenario: Unexpected pre-existing archive target stops execution
    Tool: Bash
    Steps: if any target under `.sisyphus/archive/` already exists, fail fast and tee output to `.sisyphus/evidence/task-1-preflight-edge.txt`
    Expected: command exits non-zero before any move occurs
    Evidence: .sisyphus/evidence/task-1-preflight-edge.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `none`

- [x] 2. 创建 archive 骨架并移动已完成 plan 文件

  **What to do**: 只创建最小归档骨架 `.sisyphus/archive/plans/` 与 `.sisyphus/archive/notepads/`；把 `two-layer-dedup-analyze-flow.md` 与 `railway-opencode-skill.md` 从 `plans/` 移动到 `archive/plans/`。
  **Must NOT do**: 不移动 active `railway-service-split` draft；不编辑 plan 内容；不处理 notepad 目录以外的额外材料。

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: 小范围 move-only 文件操作
  - Skills: [`git-master`] — 需要保留 rename 轨迹并准备后续原子提交
  - Omitted: `['playwright']` — 无 UI

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: `3,4` | Blocked By: `1`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `.sisyphus/plans/railway-opencode-skill.md:1-80` — 归档对象之一；无 companion notepad，属正常情况
  - Pattern: `.sisyphus/plans/two-layer-dedup-analyze-flow.md:1-80` — 归档对象之一
  - Pattern: `.sisyphus/plans/railway-service-split.md:1-645` — active keep file，对照确保不被移动

  **Acceptance Criteria** (agent-executable only):
  - [ ] `test -d .sisyphus/archive/plans`
  - [ ] `test -d .sisyphus/archive/notepads`
  - [ ] `test -f .sisyphus/archive/plans/two-layer-dedup-analyze-flow.md`
  - [ ] `test -f .sisyphus/archive/plans/railway-opencode-skill.md`
  - [ ] `test ! -f .sisyphus/plans/two-layer-dedup-analyze-flow.md`
  - [ ] `test ! -f .sisyphus/plans/railway-opencode-skill.md`
  - [ ] `test -f .sisyphus/plans/railway-service-split.md`

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Completed plan files move to archive without touching active plan
    Tool: Bash
    Steps: create archive dirs, move only the two agreed plan files, then run the acceptance `test` assertions and tee output to `.sisyphus/evidence/task-2-plan-moves.txt`
    Expected: both completed plan files exist only under `.sisyphus/archive/plans/`; `railway-service-split.md` remains in active plans
    Evidence: .sisyphus/evidence/task-2-plan-moves.txt

  Scenario: Wrong-source path aborts the move-only step
    Tool: Bash
    Steps: verify each source before move; if any expected source is missing, abort and tee output to `.sisyphus/evidence/task-2-plan-moves-edge.txt`
    Expected: no partial move occurs when a listed source path is absent
    Evidence: .sisyphus/evidence/task-2-plan-moves-edge.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `.sisyphus/plans/*`, `.sisyphus/archive/plans/*`

- [x] 3. 移动已完成 notepad 并复核 active working set

  **What to do**: 把 `.sisyphus/notepads/two-layer-dedup-analyze-flow/` 移到 `.sisyphus/archive/notepads/`；确认 `railway-service-split` notepad 仍留在 active area，且 active draft 未被移动。
  **Must NOT do**: 不创建不存在的 archived draft；不移动 `railway-service-split` notepad；不改动目录内文档内容。

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: 单目录 move + active set 复核
  - Skills: [`git-master`] — 需要验证 rename 轨迹和变更边界
  - Omitted: `['playwright']` — 无 UI

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: `4` | Blocked By: `2`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `.sisyphus/notepads/two-layer-dedup-analyze-flow/` — 唯一待归档 notepad 目录
  - Pattern: `.sisyphus/notepads/railway-service-split/` — 当前 active notepad，必须保留
  - Pattern: `.sisyphus/drafts/railway-service-split.md` — 当前唯一 active draft，必须保留

  **Acceptance Criteria** (agent-executable only):
  - [ ] `test -d .sisyphus/archive/notepads/two-layer-dedup-analyze-flow`
  - [ ] `test ! -d .sisyphus/notepads/two-layer-dedup-analyze-flow`
  - [ ] `test -d .sisyphus/notepads/railway-service-split`
  - [ ] `test -f .sisyphus/drafts/railway-service-split.md`

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Completed notepad is archived and active workspace stays intact
    Tool: Bash
    Steps: move only `.sisyphus/notepads/two-layer-dedup-analyze-flow/`, then run the acceptance `test` assertions and tee output to `.sisyphus/evidence/task-3-notepad-move.txt`
    Expected: completed notepad exists only in archive; active notepad and active draft still exist in original paths
    Evidence: .sisyphus/evidence/task-3-notepad-move.txt

  Scenario: Active draft protection catches accidental move plans
    Tool: Bash
    Steps: run a path allowlist check before and after the move; tee output to `.sisyphus/evidence/task-3-active-protection.txt`
    Expected: only the allowlisted completed notepad path changes; active draft path does not change
    Evidence: .sisyphus/evidence/task-3-active-protection.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `.sisyphus/notepads/*`, `.sisyphus/archive/notepads/*`

- [x] 4. 运行 postflight、范围校验并创建单一 move-only commit

  **What to do**: 跑完整 postflight 断言，确认 staged changes 仅限约定 `.sisyphus` 路径，且 git 将移动识别为 rename/move；若无需引用修复，则创建单一 move-only commit。该步骤不再依赖 `sisyphus-cleanup.md` 草稿存在。
  **Must NOT do**: 不修改归档文档内容以“顺手整理”；不触碰非 `.sisyphus/` 路径；不在校验失败时提交。

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: 最终校验 + 原子提交
  - Skills: [`git-master`] — git 范围检查与提交规范是关键
  - Omitted: `['playwright']` — 无 UI

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: Final Verification Wave | Blocked By: `3`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `.sisyphus/archive/plans/` — 最终 plan 归档目标
  - Pattern: `.sisyphus/archive/notepads/` — 最终 notepad 归档目标
  - Pattern: `.sisyphus/plans/railway-service-split.md:1-645` — active keep file，postflight 必须仍存在
  - Pattern: `.sisyphus/drafts/railway-service-split.md` — active keep draft

  **Acceptance Criteria** (agent-executable only):
  - [ ] `test -f .sisyphus/plans/railway-service-split.md`
  - [ ] `test -f .sisyphus/drafts/railway-service-split.md`
  - [ ] `test -d .sisyphus/notepads/railway-service-split`
  - [ ] `test -f .sisyphus/archive/plans/two-layer-dedup-analyze-flow.md`
  - [ ] `test -f .sisyphus/archive/plans/railway-opencode-skill.md`
  - [ ] `test -d .sisyphus/archive/notepads/two-layer-dedup-analyze-flow`
  - [ ] `git diff --name-status --cached --find-renames` only reports the agreed `.sisyphus` moves
  - [ ] `git diff --name-only --cached | grep -v '^\.sisyphus/'` produces no output

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Final staged diff contains only approved .sisyphus moves
    Tool: Bash
    Steps: stage cleanup changes, run `git diff --name-status --cached --find-renames` and `git diff --name-only --cached | grep -v '^\.sisyphus/'`, tee both outputs to `.sisyphus/evidence/task-4-git-scope.txt`
    Expected: staged diff shows only agreed `.sisyphus` moves; second command has no output
    Evidence: .sisyphus/evidence/task-4-git-scope.txt

  Scenario: Postflight catches missing active artifact before commit
    Tool: Bash
    Steps: rerun the full postflight `test` assertions before commit and tee output to `.sisyphus/evidence/task-4-postflight-edge.txt`
    Expected: commit is blocked if any active keep path is missing or any archive target is absent
    Evidence: .sisyphus/evidence/task-4-postflight-edge.txt
  ```

  **Commit**: YES | Message: `chore(sisyphus): archive completed planning artifacts` | Files: `.sisyphus/plans/*`, `.sisyphus/notepads/*`, `.sisyphus/archive/**`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Preferred: 单一 move-only commit：`chore(sisyphus): archive completed planning artifacts`
- Only if broken references are proven: 追加第二个 docs-only commit：`docs(sisyphus): update active planning references`
- 禁止把 move 与内容重写混在同一个 commit 里

## Success Criteria
- active area 只保留 `railway-service-split` plan/draft/notepad
- `two-layer-dedup-analyze-flow` 与 `railway-opencode-skill` 不再出现在 active `plans/`
- `two-layer-dedup-analyze-flow` notepad 不再出现在 active `notepads/`
- 所有变更都可通过 archive 路径逆向恢复，且 git staged diff 仅包含约定的 `.sisyphus` 路径
