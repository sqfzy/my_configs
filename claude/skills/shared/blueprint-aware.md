## Blueprint 感知约定

> 所有执行类 skill 在 Phase 0 自动检测项目中的活跃 blueprint，将已确定的决策作为约束。

### 命名约定

blueprint 文件统一使用 `blueprint-<项目名>-YYYYMMDD-HHMMSS.md` 格式，存入 `.artifacts/`，与所有 skill 产物一致。

### 检测逻辑

启动时搜索 `.artifacts/` 中所有活跃的计划文件：

```bash
find .artifacts -name "blueprint-*.md" 2>/dev/null | head -10
```

**若找到 blueprint 文件**：
- 读取计划内容，**跳过状态为"已完成"的 blueprint**
- 提取活跃 blueprint 中已确定的决策（技术选型、架构设计、接口设计、编码规范等）
- 将这些决策作为本次执行的**约束**——不重新讨论已确定的事项
- 在 skill 内部的设计/讨论阶段，跳过 blueprint 已覆盖的维度

**auto 模式**：直接读取 blueprint 作为已确认的决策，不向用户确认是否采纳。

**若未找到**：正常执行 skill 自身的计划/讨论流程，不受影响。

### Commit 约定

基于 blueprint 执行时，每个阶段完成并通过验收后必须提交一次 commit（通过 `/git`），commit message 标注阶段编号。这确保：
- 每个阶段是独立的**回滚点**
- 发现问题时可 `git reset` 到任意阶段，修改 blueprint 后重新执行
- blueprint 本身的修改也应单独 commit（`blueprint: 更新 <blueprint名> — <修改内容>`）
