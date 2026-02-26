-- This will run last in the setup process.
-- This is just pure lua so anything that doesn't
-- fit in the normal config locations above can go here

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
