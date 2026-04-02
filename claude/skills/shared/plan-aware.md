## Plan 感知约定

> 所有执行类 skill 在 Phase 0 自动检测项目中的 plan.md，将已确定的决策作为约束。

### 检测逻辑

启动时搜索项目中所有计划文件：

```bash
find . -name "plan.md" -o -name "*.plan.md" 2>/dev/null | grep -v node_modules | grep -v target | grep -v .git | head -10
```

**若找到 plan.md**：
- 读取计划内容，提取已确定的决策（技术选型、架构设计、接口设计、编码规范等）
- 将这些决策作为本次执行的**约束**——不重新讨论已确定的事项
- 在 skill 内部的设计/讨论阶段，跳过 plan.md 已覆盖的维度

**auto 模式**：直接读取 plan.md 作为已确认的决策，不向用户确认是否采纳。

**若未找到**：正常执行 skill 自身的计划/讨论流程，不受影响。
