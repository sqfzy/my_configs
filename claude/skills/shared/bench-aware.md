## Bench 感知约定

> 所有修改代码的 skill 在启动时自动执行 bench 基线检查，修改完成后执行回归对比。

### 启动时：基线检查

```bash
# 1. 查找最近的 bench 基线
grep "bench-data" .artifacts/INDEX.md 2>/dev/null | tail -1

# 2. 从 bench-data 文件头部提取 commit hash
head -5 .artifacts/<bench-data-file> | grep "^# Commit:" | awk '{print $3}'

# 3. 检测代码是否变更
git log <bench-commit>..HEAD --oneline 2>/dev/null | head -5
```

**决策矩阵**：

| 项目有 bench？ | 代码已变更？ | 行为 |
|----------------|-------------|------|
| ✅ 有 | ✅ 是 | **先跑 bench 建立新基线**，持久化后再开始改代码 |
| ✅ 有 | ❌ 否 | 复用最近基线，不重跑 |
| ❌ 无 | — | 不阻断，报告中标注 `ℹ️ 无 benchmark 覆盖，性能影响未验证` |

### 修改后：回归对比

代码修改完成后，若启动时检测到项目有 bench：

1. 以 release/优化模式运行 benchmark
2. 按 `artifacts.md` 的 bench-data 约定持久化结果
3. 与基线对比，判定退化：

| 变化 | 判定 | 行为 |
|------|------|------|
| 改善 >5% | ✅ 改善 | 继续 |
| ±5% 以内 | ➡️ 持平 | 继续 |
| 退化 5–15% | ⚠️ 退化 | 暂停，告知用户，由用户决策（auto 模式：回滚该改动） |
| 退化 >15% | 🔴 严重退化 | 暂停，强烈建议回滚（auto 模式：自动回滚） |

### Skill 引用方式

在 Phase 0（基线建立）和最终验证阶段写 **"按 Bench 感知约定执行"** 即可，不需要重复定义查找、对比、阈值逻辑。
