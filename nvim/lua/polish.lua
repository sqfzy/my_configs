-- This will run last in the setup process.
-- This is just pure lua so anything that doesn't
-- fit in the normal config locations above can go here

if vim.fn.has "wsl" == 1 then
  vim.g.clipboard = {
    name = "win32yank",
    copy = {
      ["+"] = "win32yank.exe -i --crlf",
      ["*"] = "win32yank.exe -i --crlf",
    },
    paste = {
      ["+"] = "win32yank.exe -o --lf",
      ["*"] = "win32yank.exe -o --lf",
    },
    cache_enabled = 0,
  }
elseif vim.env.NVIM_MINIMAL then
  vim.g.clipboard = {
    name = "OSC 52",
    copy = {
      ["+"] = require("vim.ui.clipboard.osc52").copy "+",
      ["*"] = require("vim.ui.clipboard.osc52").copy "*",
    },
    paste = {
      ["+"] = require("vim.ui.clipboard.osc52").paste "+",
      ["*"] = require("vim.ui.clipboard.osc52").paste "*",
    },
  }
end

-- 让未聚焦的终端窗口（如多个 Claude Code 会话）也跟随输出自动下滚。
-- Neovim 默认只有光标在最后一行时终端才跟随，后台窗口会停住；
-- 这里监听 buffer 变化，把所有显示该终端、但未聚焦的窗口光标钉到底部。
vim.api.nvim_create_autocmd("TermOpen", {
  callback = function(args)
    local buf = args.buf
    vim.api.nvim_buf_attach(buf, false, {
      on_lines = function()
        -- on_lines 处于 textlock，必须 schedule 出去才能改光标
        vim.schedule(function()
          if not vim.api.nvim_buf_is_valid(buf) then return end
          local last_line = vim.api.nvim_buf_line_count(buf)
          for _, win in ipairs(vim.fn.win_findbuf(buf)) do
            -- 只滚后台窗口；聚焦窗口由 terminal-mode 自己跟随，
            -- 这样在某个窗口往上翻历史时不会被强行拉回底部
            if win ~= vim.api.nvim_get_current_win() then
              pcall(vim.api.nvim_win_set_cursor, win, { last_line, 0 })
            end
          end
        end)
      end,
    })
  end,
})

vim.filetype.add {
  -- extension = {
  --   foo = "fooscript",
  -- },
  -- filename = {
  --   ["Foofile"] = "fooscript",
  -- },
  -- pattern = {
  --   ["~/%.config/foo/.*"] = "fooscript",
  -- },
}

require("nvim-web-devicons").set_icon {
  typ = {
    icon = "󰰤",
    color = "#239dad",
    cterm_color = "31", -- 用于终端的颜色编号
    name = "Typst", -- 图标名称，用于调试或扩展支持
  },
  mmd = {
    icon = "Y",
    color = "#fd366e",
    name = "Mmd",
  },
}

-- 自动以work_space为当前工作目录
-- if vim.fn.isdirectory(vim.fn.expand "~/work_space/") == 0 then vim.fn.mkdir(vim.fn.expand "~/work_space/") end
-- vim.cmd "cd ~/work_space"
