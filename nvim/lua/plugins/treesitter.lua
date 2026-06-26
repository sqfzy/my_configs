-- Customize Treesitter
--
-- AstroNvim v6 起,nvim-treesitter(main 分支)只作为 parser 的下载工具,
-- 高亮 / 缩进 / 自动安装 / textobjects 全部由 AstroCore 的 `treesitter` 模块接管。
-- 配置文档见 `:h astrocore`。

---@type LazySpec
return {
  "AstroNvim/astrocore",
  opts = function(_, opts)
    local treesitter = opts.treesitter or {}

    treesitter.highlight = true -- 启用 treesitter 高亮
    treesitter.indent = true -- 启用 treesitter 缩进
    treesitter.auto_install = true -- 自动安装检测到的语言 parser

    -- 用 list_insert_unique 累加,防止被社区包(community packs)的同名列表覆盖
    treesitter.ensure_installed = require("astrocore").list_insert_unique(treesitter.ensure_installed, {
      "lua",
      "vim",
      "nu",
      -- 在此追加更多 treesitter parser
    })

    -- textobjects(v6 新 schema):按 type(select / move / swap)→ method → 键位 → { query, desc } 组织,
    -- 键位会在含对应 capture 的 buffer 上自动挂载。需要时取消注释:
    -- treesitter.textobjects = {
    --   select = {
    --     select_textobject = {
    --       ["af"] = { query = "@function.outer", desc = "around function" },
    --       ["if"] = { query = "@function.inner", desc = "inside function" },
    --       ["ac"] = { query = "@class.outer", desc = "around class" },
    --       ["ic"] = { query = "@class.inner", desc = "inside class" },
    --     },
    --   },
    --   move = {
    --     goto_next_start = { ["]f"] = { query = "@function.outer", desc = "Next function start" } },
    --     goto_previous_start = { ["[f"] = { query = "@function.outer", desc = "Prev function start" } },
    --   },
    -- }
    --
    -- 注意:旧的 textobjects `lsp_interop` / `peek_definition_code`(原 go / gO)在上游 main 分支
    -- 已被移除,无直接等价物。peek 定义改用 LSP:`gd` / `<A-k>` hover / `Snacks.picker`。

    opts.treesitter = treesitter
  end,
}
