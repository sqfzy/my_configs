## 改动总结可视化原则

> **铁律：任何修改了代码的 skill，完成后必须输出"做了什么改动"的总结，用 ASCII 图示呈现，并把同一份总结原样写入产物报告。**

修改完代码不告诉用户具体改了什么，等于让用户自己 diff 一遍——既浪费时间，又容易漏看关键改动。改动总结的目的是让用户**不打开 diff 也能掌握全貌**，并能直接拍板"接受 / 让你回滚 / 让你改 X"。

### 必须包含的维度

每次代码修改完成后，输出包含以下维度的"改动总结"章节（按场景取舍）：

- **文件级清单**：新增 / 修改 / 删除 / 重命名的文件 + 一句话说明每个文件的改动内容
- **结构变化图**：若涉及新增模块、目录调整、依赖关系变化——用 ASCII 图示前后对比
- **接口变化**：公共 API 签名的新增 / 修改 / 移除（精确到函数签名）
- **行为变化**：在用户视角能观察到的差异（输出格式、错误信息、性能、副作用）
- **未改动但相关的位置**：考虑过但**有意未改**的地方（避免用户以为遗漏）

### ASCII 图示偏好

凡能画图的就不要纯文字描述：

**文件改动一览**：

```
文件改动清单
─────────────
+ src/core/engine.rs            新增：核心调度器（230 行）
+ src/core/state.rs             新增：共享状态（85 行）
~ src/lib.rs                    修改：re-export engine/state
~ src/adapters/http.rs          修改：改用 Engine 而非旧 Dispatcher
- src/old_dispatcher.rs         删除：被 Engine 替代
↻ src/legacy.rs → src/compat.rs 重命名 + 缩减
```

**改造前后结构对比**：

```
   改前                              改后
   ────                              ────
   ┌──────────┐                      ┌──────────┐    ┌──────────┐
   │ HTTP     │──┐                   │ HTTP     │───▶│ Engine   │
   ├──────────┤  ▼                   ├──────────┤    ├──────────┤
   │ Dispatcher│ ← 1500 LoC          │ Adapter  │    │ State    │
   └──────────┘                      └──────────┘    └──────────┘
                                          已拆分：调度 + 状态
```

**接口变化**：

```
接口变化
─────────
+ pub fn Engine::new(cfg: Config) -> Self
+ pub fn Engine::run(&mut self, req: Request) -> Result<Response, EngError>
~ pub fn handle_http(req) -> Result<Resp, Box<dyn Error>>
                  ↓ 错误类型从 Box<dyn Error> 改为 EngError（更精确）
- pub fn Dispatcher::dispatch        移除：Engine 取代
```

**未改动但考虑过的位置**：

```
故意未改
─────────
✗ src/legacy/v1_handler.rs     仍有 2 个外部调用方，本轮不动；后续 /migrate 处理
✗ src/util/format.rs           风格不一致但属于其他模块的"领地"，不在本次范围
```

### 输出位置（双份）

改动总结**必须出现在两处，内容完全一致**：

1. **会话末尾**：在最终交付前直接打印给用户审阅，便于即时反馈
2. **`.artifacts/<skill>-*.md` 报告中**：作为一个固定的二级章节 `## 改动总结`，原样写入。这样用户日后回看报告也能直接复盘改动，不必去翻 git log

> 不要在报告里写"详见会话输出"——会话输出会消失，报告要能独立成立。

### 反模式（必须避免）

- ❌ 只说"修改了 N 个文件"或只列文件名，不说"做了什么"
- ❌ 让用户自己看 diff——你已经知道你改了什么，写出来即可
- ❌ 在报告里和会话里写两份**不一样**的总结——必须 1:1 一致
- ❌ 漏掉重命名 / 删除——只记新增和修改
- ❌ 改动跨多个 commit 时只总结最后一个——要覆盖**本次 skill 执行的全部改动**
- ❌ 把"接口变化"埋在文字里——必须独立成段，让用户一眼看到 breaking change

### 适用 skill

所有会修改代码的 skill：`/design`、`/fix`、`/refactor`、`/improve`、`/cleanup`、`/migrate`、`/evolve`、`/ship`、`/merge`（port 模式）。

只读类 skill（`/review`、`/debug`、`/discuss`、`/bench` 的非 optimize 模式、`/doc`）不需要——它们没改代码。
