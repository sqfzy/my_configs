# my_configs

个人开发环境配置集合。

## 文件组织

```text
.
├── .codex/             # 本仓库的 Release Gate 默认模式与 finding 清单
├── btop/               # btop 监控工具配置
├── carapace/           # Carapace 补全桥接与命令规格
├── clangd/             # clangd 语言服务器配置
├── claude/             # Claude Code 的代理、命令与技能配置
├── codex/              # Codex 的代理规则、发布前 Git hook 与本地技能
│   ├── AGENTS.md       # 全局开发约定
│   ├── git-hooks/      # 可版本控制的全局 Git hook 入口
│   └── skills/         # PR、部署与 Release Gate 等可复用工作流
├── fish/
│   ├── config.fish     # Fish 启动入口与交互环境初始化
│   └── functions/      # Fish 自动加载的独立命令函数
├── fonts/              # 终端与编辑器使用的字体文件
├── nushell/
│   ├── config.nu       # Nushell 启动入口与交互环境初始化
│   └── functions/      # Nushell 自定义命令
├── nvim/               # 启用语言服务器的 Neovim 配置
├── nvim-nolsp/         # 不启用语言服务器的 Neovim 配置
└── starship.toml       # Starship 跨 Shell 提示符配置
```
