## Autopilot 感知约定

> 任何可能修改工作区的 skill 在启动时必须检测项目中是否有正在运行的 autopilot，避免与其并发改动同一份代码或 `.artifacts/` 状态。

### 检测逻辑

```bash
find .artifacts -name "autopilot-state-*.json" 2>/dev/null
```

对每个命中文件，读取 `.status` 字段：

| status | 含义 | skill 行为 |
|--------|------|-----------|
| `starting` / `running` | 有 autopilot 在监控一个后台任务 | **停下询问用户**：autopilot 正在看护 `<task>`，当前 skill 可能与它冲突——继续 / 暂停 autopilot / 终止本 skill |
| `escalated` | autopilot 已升级等待用户处理 | 警告用户但不阻断，提示"autopilot 有未处理的升级事件" |
| `crashed` / `finished` / `terminated_by_redline` | 已停止 | 无操作，状态文件仅作历史 |

### 为什么要感知

- **文件锁**：autopilot 可能正在写 state.json、log 文件，并发 skill 若也改这些文件会造成竞态
- **Git 冲突**：autopilot 授权条款里可能允许"修改 `<模块 X>` 的代码"，并发 `/fix` 或 `/refactor` 改同一区域会产生冲突
- **资源竞争**：autopilot 后台任务可能吃 CPU/内存，此时跑 `/bench` 会得到污染数据

### 不阻断的情况

纯只读 skill（`/review`、`/debug`、`/doc summary`）不需要感知——它们不改动任何东西，安全并发。

### Skill 引用方式

在 Phase 0 写**"按 Autopilot 感知约定执行"** 即可，不需要重复定义检测逻辑。
