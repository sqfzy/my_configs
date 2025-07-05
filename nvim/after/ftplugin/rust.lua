-- ~/.config/nvim/after/ftplugin/rust.lua

-- 获取当前缓冲区
local bufnr = vim.api.nvim_get_current_buf()

-- -- 定义函数来解释错误并切换到浮动窗口
-- function ExplainErrorAndEnterFloat()
--   -- 运行 RustLsp 的 explainError 命令
--   vim.cmd.RustLsp "explainError"
--
--   -- 等待一段时间确保浮动窗口已经打开
--   vim.defer_fn(function()
--     -- 获取所有窗口的 ID
--     local win_ids = vim.api.nvim_list_wins()
--     for _, win_id in ipairs(win_ids) do
--       -- 检查窗口是否为浮动窗口
--       local config = vim.api.nvim_win_get_config(win_id)
--       if config.relative ~= "" then
--         -- 切换到浮动窗口
--         vim.api.nvim_set_current_win(win_id)
--         -- 映射 gL 键到浮动窗口的退出操作或滚动操作
--         vim.api.nvim_buf_set_keymap(0, "n", "q", "<Cmd>close<CR>", { noremap = true, silent = true })
--         vim.api.nvim_buf_set_keymap(0, "n", "j", "j", { noremap = true, silent = true })
--         vim.api.nvim_buf_set_keymap(0, "n", "k", "k", { noremap = true, silent = true })
--         break
--       end
--     end
--   end, 100) -- 延迟 100 毫秒
-- end

-- 获取当前浮动窗口的 ID
local function get_floating_win_id()
  for _, win in pairs(vim.api.nvim_tabpage_list_wins(0)) do
    if vim.api.nvim_win_get_config(win).relative ~= "" then return win end
  end
  return nil
end

vim.keymap.set("n", "<A-k>", function() vim.cmd.RustLsp { "hover", "actions" } end, { silent = true, buffer = bufnr })

vim.keymap.set("n", "<Leader>W", function()
  vim.lsp.buf.format(require("astrolsp").format_opts)
  vim.cmd "w!"
  vim.cmd.RustLsp "flyCheck"
end, { silent = true, buffer = bufnr, desc = "Save and check" })

vim.keymap.set("n", "gL", function()
  local float_win_id = get_floating_win_id()
  if float_win_id then
    -- 如果浮动窗口已经打开，切换到该窗口
    vim.api.nvim_set_current_win(float_win_id)
  else
    -- 如果浮动窗口没有打开，执行 RustLsp explainError 命令
    vim.cmd.RustLsp { "explainError", "current" }
  end
end, { silent = true, buffer = bufnr, desc = "Explain Error or Enter Floating Window" })

vim.keymap.set(
  "n",
  "<A-j>",
  function() vim.cmd.RustLsp "joinLines" end,
  { silent = true, buffer = bufnr, desc = "Join Lines" }
)

-- vim.keymap.set(
--   "n",
--   "<leader>lf",
--   function() vim.lsp.buf.format() end,
--   { silent = true, buffer = bufnr, desc = "Foramat" }
-- )

-- vim.keymap.set(
--   "n",
--   "<leader>lr",
--   function() vim.lsp.buf.rename() end,
--   { silent = true, buffer = bufnr, desc = "Rename" }
-- )
--
-- vim.keymap.set(
--   "n",
--   "<leader>la",
--   function() vim.cmd.RustLsp "codeAction" end,
--   { silent = true, buffer = bufnr, desc = "Code Action" }
-- )

vim.keymap.set(
  "n",
  "<leader>le",
  function() vim.cmd.RustLsp "expandMacro" end,
  { silent = true, buffer = bufnr, desc = "Expand Macro" }
)

vim.keymap.set("n", "<leader>ld", function()
  local float_win_id = get_floating_win_id()
  if float_win_id then
    -- 如果浮动窗口已经打开，切换到该窗口
    vim.api.nvim_set_current_win(float_win_id)
  else
    vim.cmd.RustLsp { "renderDiagnostic", "current" }
  end
end, { silent = true, buffer = bufnr, desc = "Render Diagnostic" })

-- vim.keymap.set(
--   "n",
--   "<leader>lC",
--   function() vim.cmd.RustLsp "openCargo" end,
--   { silent = true, buffer = bufnr, desc = "Open Cargo" }
-- )

vim.keymap.set(
  "n",
  "<leader>lg",
  function() vim.cmd.RustLsp { "crateGraph", "[backend]", "[output]" } end,
  { silent = true, buffer = bufnr, desc = "Crate Graph" }
)

vim.keymap.set(
  "n",
  "<leader>lt",
  function() vim.cmd.RustLsp "syntaxTree" end,
  { silent = true, buffer = bufnr, desc = "Syntax Tree" }
)

vim.keymap.set(
  "n",
  "<leader>lC",
  function() vim.cmd.RustLsp "flyCheck" end,
  { silent = true, buffer = bufnr, desc = "Fly Check" }
)

vim.keymap.set(
  "n",
  "<leader>lH",
  function() vim.cmd.RustLsp { "view", "hir" } end,
  { silent = true, buffer = bufnr, desc = "View HIR" }
)

vim.keymap.set(
  "n",
  "<leader>lM",
  function() vim.cmd.RustLsp { "view", "mir" } end,
  { silent = true, buffer = bufnr, desc = "View MIR" }
)

-- vim.keymap.set(
--   "n",
--   "<leader>luh",
--   function() vim.cmd.RustLsp { "unpretty", "hir" } end,
--   { silent = true, buffer = bufnr, desc = "Unpretty HIR" }
-- )
--
-- vim.keymap.set(
--   "n",
--   "<leader>lum",
--   function() vim.cmd.RustLsp { "unpretty", "mir" } end,
--   { silent = true, buffer = bufnr, desc = "Unpretty MIR" }
-- )
