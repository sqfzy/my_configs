---
name: create-agent
description: "Interactive creation of custom Claude Code subagent definitions — guides through name, description, tools, model, hooks, memory, and system prompt, then writes the agent markdown file. TRIGGER when: user asks to create a new agent, subagent, or custom agent definition, or says \"create agent\", \"new agent\", \"make an agent\". DO NOT TRIGGER when: user is asking about how agents work (use documentation), or wants to edit an existing agent file directly."
argument-hint: "[name] [scope: user|project] [target: <path>] [auto]"
allowed-tools: Bash(ls:*), Bash(cat:*), Bash(find:*), Bash(date:*)
---

# /create-agent

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
现有用户级 agents：!`ls ~/.claude/agents/ 2>/dev/null | sed 's/\.md$//' || echo "(无)"`
现有项目级 agents：!`ls .claude/agents/ 2>/dev/null | sed 's/\.md$//' || echo "(无)"`

需求：$ARGUMENTS

---

## 参数解析

- `[name]`：agent 名称（小写字母+连字符），如未提供则在 Phase 1 中询问
- `[scope: user|project]`：保存位置，`user` = `~/.claude/agents/`（全局可用），`project` = `.claude/agents/`（仅当前项目）。默认 `user`。当指定 `target` 时此参数被忽略
- `[target: <path>]`：直接指定 agent 文件的写入目录路径（如 `target: /path/to/agents/`）。指定后忽略 `scope`，文件写入 `<path>/<name>.md`。如目录不存在则创建
- `[auto]`：无人值守模式——跳过所有交互确认，根据需求描述自动推断所有配置

---

## Phase 1: 需求收集

收集以下信息。如果用户在 $ARGUMENTS 中已提供部分信息，直接采用，仅询问缺失项。

### 1.1 基本信息

| 字段 | 说明 | 必需 |
|------|------|------|
| `name` | 小写字母+连字符的唯一标识符，如 `code-reviewer` | 是 |
| `description` | Claude 何时应委托给此 agent（写清楚触发条件） | 是 |
| `scope` | `user`（全局）或 `project`（仅当前项目） | 是 |

### 1.2 能力配置

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `tools` | agent 可用的工具列表 | 继承所有工具 |
| `disallowedTools` | 要禁止的工具列表 | 无 |
| `model` | 使用的模型：`sonnet`、`opus`、`haiku`、`inherit` | `inherit` |
| `permissionMode` | 权限模式：`default`、`acceptEdits`、`dontAsk`、`bypassPermissions`、`plan` | 不设置（使用默认） |
| `maxTurns` | 最大代理轮数 | 不设置 |
| `memory` | 持久内存范围：`user`、`project`、`local` | 不设置 |
| `background` | 是否始终后台运行 | `false` |
| `isolation` | 设为 `worktree` 在隔离 git worktree 中运行 | 不设置 |
| `color` | 背景颜色，便于在 UI 中区分 | 不设置 |

### 1.3 高级配置（仅在用户主动提及时询问）

| 字段 | 说明 |
|------|------|
| `hooks` | 生命周期 hooks（PreToolUse / PostToolUse / Stop） |
| `skills` | 启动时预加载的 skills 列表 |
| `mcpServers` | 可用的 MCP servers |

#### Hooks 配置示例

**1. PreToolUse hook — 在执行 Bash 命令前进行验证或拦截：**

```yaml
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "echo 'About to run bash command'"
```

**2. PostToolUse hook — 在文件编辑后执行日志记录或格式检查：**

```yaml
hooks:
  PostToolUse:
    - matcher: "Edit"
      hooks:
        - type: command
          command: "echo 'File edited: checking format...'"
```

**3. Stop hook — Agent 完成时执行清理操作：**

```yaml
hooks:
  Stop:
    - hooks:
        - type: command
          command: "echo 'Agent completed, running cleanup...'"
```

> **说明：**
> - `matcher` 匹配工具名称，如 `Bash`、`Edit`、`Write`、`Read`、`Grep`、`Glob` 等。`Stop` 事件无需 matcher。
> - `type: command` 表示运行一条 shell 命令；该命令通过环境变量接收上下文信息（如工具输入参数等）。
> - Hooks 在用户的 shell 中执行，而非在 agent 沙箱内部运行。

### 1.4 系统提示

这是 agent 的核心行为指导。询问用户：
- 这个 agent 的职责是什么？
- 被调用时应该执行什么流程？
- 有哪些关键规则或约束？

**`auto` 模式**：根据 name 和 description 自动生成系统提示，不暂停询问。

---

**如果非 `auto` 模式，在此处暂停，向用户确认所有配置，再继续。**

输出格式：

```
## Agent 配置确认

- 名称：<name>
- 描述：<description>
- 写入路径：<target 或 scope 对应的路径>
- 工具：<tools 或 "继承所有">
- 模型：<model>
- 其他配置：<如有>

### 系统提示摘要
<概括 agent 的行为>

确认后将生成 agent 文件。
```

---

## Phase 2: 生成 Agent 文件

### 2.1 确定保存路径

优先级：`target` > `scope`

- 指定了 `target` → `<target>/<name>.md`（如目录不存在则创建）
- `user` scope → `~/.claude/agents/<name>.md`
- `project` scope → `.claude/agents/<name>.md`（如目录不存在则创建）

### 2.2 检查冲突

检查目标路径是否已存在同名 agent 文件。如已存在：
- 非 `auto` 模式：提示用户是否覆盖
- `auto` 模式：自动覆盖并在输出中标注

### 2.3 生成文件内容

按以下模板生成 markdown 文件：

```markdown
---
name: <name>
description: <description>
tools: <tools>                    # 仅在非默认时包含
disallowedTools: <disallowed>     # 仅在有值时包含
model: <model>                    # 仅在非 inherit 时包含
permissionMode: <mode>            # 仅在非 default 时包含
maxTurns: <number>                # 仅在有值时包含
memory: <scope>                   # 仅在有值时包含
background: true                  # 仅在为 true 时包含
isolation: worktree               # 仅在有值时包含
color: <color>                    # 仅在有值时包含
skills:                           # 仅在有值时包含
  - <skill-name>
mcpServers:                       # 仅在有值时包含
  - <server-name>
hooks:                            # 仅在有值时包含
  PreToolUse:
    - matcher: "<tool>"
      hooks:
        - type: command
          command: "<script>"
---

<系统提示内容>
```

**Frontmatter 原则**：只包含用户明确配置的字段，省略所有使用默认值的字段，保持文件简洁。

### 2.4 写入文件

使用 Write 工具将文件写入目标路径。

---

## Phase 3: 验证 & 提示

1. 确认文件已写入
2. 提示用户：
   - agent 已可用（用户级立即生效，项目级需重启会话或运行 `/agents`）
   - 使用方式：`Use the <name> agent to <task>` 或让 Claude 根据 description 自动委托
   - 如需修改，可直接编辑文件或再次运行 `/create-agent`

---

## 系统提示编写指南

生成系统提示时遵循以下最佳实践：

1. **开头明确角色**：用一句话说明 agent 是什么、擅长什么
2. **定义工作流程**：用编号步骤描述被调用时的执行流程
3. **列出关键规则**：agent 必须遵循的约束和原则
4. **指定输出格式**：如果 agent 需要返回结构化结果，明确格式
5. **保持聚焦**：每个 agent 应该专注于一个特定领域，不要试图包罗万象
6. **使用中文**：与用户的语言偏好保持一致（如用户使用中文则用中文）

### 常见 Agent 模式参考

**只读分析型**（如 code-reviewer）：
- tools: `Read, Grep, Glob, Bash`
- 不包含 Write/Edit
- 适合审查、分析、搜索类任务

**读写执行型**（如 debugger）：
- tools: `Read, Write, Edit, Bash, Grep, Glob`
- 适合需要修改代码的任务

**研究型**（如 researcher）：
- tools: `Read, Grep, Glob, WebSearch, WebFetch`
- 适合需要搜索外部信息的任务

**轻量快速型**：
- model: `haiku`
- 适合简单、重复、对延迟敏感的任务
