## Plan 感知约定

> 所有执行类 skill 在 Phase 0 自动检测项目中的活跃 plan，将已确定的决策作为约束。

### 命名约定

plan 文件统一使用 `<项目名>-<YYYYMMDD>.plan.md` 格式。已完成的 plan 归档至 `.artifacts/`。

### 检测逻辑

启动时搜索项目中所有活跃的计划文件（排除 `.artifacts/` 中已归档的）：

```bash
find . -name "*.plan.md" 2>/dev/null | grep -v node_modules | grep -v target | grep -v .git | grep -v .artifacts | head -10
```

**若找到 plan 文件**：
- 读取计划内容，**跳过状态为"已完成"的 plan**（若发现未归档的已完成 plan，自动移入 `.artifacts/`）
- 提取活跃 plan 中已确定的决策（技术选型、架构设计、接口设计、编码规范等）
- 将这些决策作为本次执行的**约束**——不重新讨论已确定的事项
- 在 skill 内部的设计/讨论阶段，跳过 plan 已覆盖的维度

**auto 模式**：直接读取 plan 作为已确认的决策，不向用户确认是否采纳。

**若未找到**：正常执行 skill 自身的计划/讨论流程，不受影响。

### Commit 约定

基于 plan 执行时，每个阶段完成并通过验收后必须提交一次 commit（通过 `/git`），commit message 标注阶段编号。这确保：
- 每个阶段是独立的**回滚点**
- 发现问题时可 `git reset` 到任意阶段，修改 plan 后重新执行
- plan 本身的修改也应单独 commit（`plan: 更新 <plan名> — <修改内容>`）
