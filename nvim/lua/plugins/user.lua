-- You can also add or configure plugins by creating files in this `plugins/` folder
-- PLEASE REMOVE THE EXAMPLES YOU HAVE NO INTEREST IN BEFORE ENABLING THIS FILE
-- Here are some examples:

local Snacks = require "snacks"

---@type LazySpec
return {

  -- == Examples of Adding Plugins ==

  -- "andweeb/presence.nvim",
  -- {
  --   "ray-x/lsp_signature.nvim",
  --   event = "BufRead",
  --   config = function() require("lsp_signature").setup() end,
  -- },
  --
  -- == Examples of Overriding Plugins ==

  -- customize dashboard options
  {
    "folke/snacks.nvim",
    opts = function(_, opts)
      opts.dashboard = {
        preset = {
          header = table.concat({

            -- " █████  ███████ ████████ ██████   ██████",
            -- "██   ██ ██         ██    ██   ██ ██    ██",
            -- "███████ ███████    ██    ██████  ██    ██",
            -- "██   ██      ██    ██    ██   ██ ██    ██",
            -- "██   ██ ███████    ██    ██   ██  ██████",
            -- " ",
            -- "    ███    ██ ██    ██ ██ ███    ███",
            -- "    ████   ██ ██    ██ ██ ████  ████",
            -- "    ██ ██  ██ ██    ██ ██ ██ ████ ██",
            -- "    ██  ██ ██  ██  ██  ██ ██  ██  ██",
            -- "    ██   ████   ████   ██ ██      ██",

            -- "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡀⠀⠀⠀⠀⢀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⡖⠁⠀⠀⠀⠀⠀⠀⠈⢲⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⠀⠀⠀⠀⣼⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢹⣧⠀⠀⠀⠀⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⠀⠀⠀⣸⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⣿⣇⠀⠀⠀⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⠀⠀⠀⣿⣿⡇⠀⢀⣀⣤⣤⣤⣤⣀⡀⠀⢸⣿⣿⠀⠀⠀⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⣔⢿⡿⠟⠛⠛⠻⢿⡿⣢⣿⣿⡟⠀⠀⠀⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⣀⣤⣶⣾⣿⣿⣿⣷⣤⣀⡀⢀⣀⣤⣾⣿⣿⣿⣷⣶⣤⡀⠀⠀⠀⠀ ",
            -- "⠀⠀⢠⣾⣿⡿⠿⠿⠿⣿⣿⣿⣿⡿⠏⠻⢿⣿⣿⣿⣿⠿⠿⠿⢿⣿⣷⡀⠀⠀ ",
            -- "⠀⢠⡿⠋⠁⠀⠀⢸⣿⡇⠉⠻⣿⠇⠀⠀⠸⣿⡿⠋⢰⣿⡇⠀⠀⠈⠙⢿⡄⠀ ",
            -- "⠀⡿⠁⠀⠀⠀⠀⠘⣿⣷⡀⠀⠰⣿⣶⣶⣿⡎⠀⢀⣾⣿⠇⠀⠀⠀⠀⠈⢿⠀ ",
            -- "⠀⡇⠀⠀⠀⠀⠀⠀⠹⣿⣷⣄⠀⣿⣿⣿⣿⠀⣠⣾⣿⠏⠀⠀⠀⠀⠀⠀⢸⠀ ",
            -- "⠀⠁⠀⠀⠀⠀⠀⠀⠀⠈⠻⢿⢇⣿⣿⣿⣿⡸⣿⠟⠁⠀⠀⠀⠀⠀⠀⠀⠈⠀ ",
            -- "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣼⣿⣿⣿⣿⣧⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⠐⢤⣀⣀⢀⣀⣠⣴⣿⣿⠿⠋⠙⠿⣿⣿⣦⣄⣀⠀⠀⣀⡠⠂⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⠀⠈⠉⠛⠛⠛⠛⠉⠀⠀⠀⠀⠀⠈⠉⠛⠛⠛⠛⠋⠁⠀⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣠⣤⣤⣴⣦⣤⣤⣄⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⠀⠀⢀⣤⣾⣿⣿⣿⣿⠿⠿⠿⠿⣿⣿⣿⣿⣶⣤⡀⠀⠀⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⣠⣾⣿⣿⡿⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⢿⣿⣿⣶⡀⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⣴⣿⣿⠟⠁⠀⠀⠀⣶⣶⣶⣶⡆⠀⠀⠀⠀⠀⠀⠈⠻⣿⣿⣦⠀⠀⠀ ",
            -- "⠀⠀⣼⣿⣿⠋⠀⠀⠀⠀⠀⠛⠛⢻⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⣧⠀⠀ ",
            -- "⠀⢸⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⣿⣷⠀⠀⠀⠀⠀⠀⠀⠀⠸⣿⣿⡇⠀ ",
            -- "⠀⣿⣿⡿⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⣿⣿⣿⣇⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⠀ ",
            -- "⠀⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⢠⣿⣿⡟⢹⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⣹⣿⣿⠀ ",
            -- "⠀⣿⣿⣷⠀⠀⠀⠀⠀⠀⣰⣿⣿⠏⠀⠀⢻⣿⣿⡄⠀⠀⠀⠀⠀⠀⣿⣿⡿⠀ ",
            -- "⠀⢸⣿⣿⡆⠀⠀⠀⠀⣴⣿⡿⠃⠀⠀⠀⠈⢿⣿⣷⣤⣤⡆⠀⠀⣰⣿⣿⠇⠀ ",
            -- "⠀⠀⢻⣿⣿⣄⠀⠀⠾⠿⠿⠁⠀⠀⠀⠀⠀⠘⣿⣿⡿⠿⠛⠀⣰⣿⣿⡟⠀⠀ ",
            -- "⠀⠀⠀⠻⣿⣿⣧⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⠏⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⠈⠻⣿⣿⣷⣤⣄⡀⠀⠀⠀⠀⠀⠀⢀⣠⣴⣾⣿⣿⠟⠁⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⠀⠀⠈⠛⠿⣿⣿⣿⣿⣿⣶⣶⣿⣿⣿⣿⣿⠿⠋⠁⠀⠀⠀⠀⠀⠀ ",
            -- "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉⠛⠛⠛⠛⠛⠛⠉⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀ ",

            --         [[
            --             __
            --   ___  __ _ / _|____   _
            -- / __|/ _` | ||_  / | | |
            -- \__ \ (_| |  _/ /| |_| |
            -- |___/\__, |_|/___|\__, |
            --         |_|       |___/
            --     ]],

            "███████╗ ██████╗ ███████╗███████╗██╗   ██╗",
            "██╔════╝██╔═══██╗██╔════╝╚══███╔╝╚██╗ ██╔╝",
            "███████╗██║   ██║█████╗    ███╔╝  ╚████╔╝ ",
            "╚════██║██║▄▄ ██║██╔══╝   ███╔╝    ╚██╔╝  ",
            "███████║╚██████╔╝██║     ███████╗   ██║   ",
            "╚══════╝ ╚══▀▀═╝ ╚═╝     ╚══════╝   ╚═╝   ",
            -- " ▄▀▀▀▀▄  ▄▀▀▀▀▄    ▄▀▀▀█▄    ▄▀▀▀▀▄   ▄▀▀▄ ▀▀▄ ",
            -- "█ █   ▐ █      █  █  ▄▀  ▀▄ █     ▄▀ █   ▀▄ ▄▀ ",
            -- "   ▀▄   █      █  ▐ █▄▄▄▄   ▐ ▄▄▀▀   ▐     █   ",
            -- "▀▄   █   ▀▄▄▄▄▀▄   █    ▐     █            █   ",
            -- " █▀▀▀           █  █           ▀▄▄▄▄▀    ▄▀    ",
            -- " ▐              ▐ █                ▐     █     ",
            -- "                  ▐                      ▐     ",
            -- " ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄         ▄ ",
            -- "▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░▌       ▐░▌",
            -- "▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀▀▀  ▀▀▀▀▀▀▀▀▀█░▌▐░▌       ▐░▌",
            -- "▐░▌          ▐░▌       ▐░▌▐░▌                    ▐░▌▐░▌       ▐░▌",
            -- "▐░█▄▄▄▄▄▄▄▄▄ ▐░▌       ▐░▌▐░█▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄█░▌▐░█▄▄▄▄▄▄▄█░▌",
            -- "▐░░░░░░░░░░░▌▐░▌       ▐░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌",
            -- " ▀▀▀▀▀▀▀▀▀█░▌▐░█▄▄▄▄▄▄▄█░▌▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀▀▀▀▀▀  ▀▀▀▀█░█▀▀▀▀ ",
            -- "          ▐░▌▐░░░░░░░░░░░▌▐░▌          ▐░▌               ▐░▌     ",
            -- " ▄▄▄▄▄▄▄▄▄█░▌ ▀▀▀▀▀▀█░█▀▀ ▐░▌          ▐░█▄▄▄▄▄▄▄▄▄      ▐░▌     ",
            -- "▐░░░░░░░░░░░▌        ▐░▌  ▐░▌          ▐░░░░░░░░░░░▌     ▐░▌     ",
            -- " ▀▀▀▀▀▀▀▀▀▀▀          ▀    ▀            ▀▀▀▀▀▀▀▀▀▀▀       ▀      ",
            -- "  ██████   █████    █████▒▒███████▒▓██   ██▓",
            -- "▒██    ▒ ▒██▓  ██▒▓██   ▒ ▒ ▒ ▒ ▄▀░ ▒██  ██▒",
            -- "░ ▓██▄   ▒██▒  ██░▒████ ░ ░ ▒ ▄▀▒░   ▒██ ██░",
            -- "  ▒   ██▒░██  █▀ ░░▓█▒  ░   ▄▀▒   ░  ░ ▐██▓░",
            -- "▒██████▒▒░▒███▒█▄ ░▒█░    ▒███████▒  ░ ██▒▓░",
            -- "▒ ▒▓▒ ▒ ░░░ ▒▒░ ▒  ▒ ░    ░▒▒ ▓░▒░▒   ██▒▒▒ ",
            -- "░ ░▒  ░ ░ ░ ▒░  ░  ░      ░░▒ ▒ ░ ▒ ▓██ ░▒░ ",
            -- "░  ░  ░     ░   ░  ░ ░    ░ ░ ░ ░ ░ ▒ ▒ ░░  ",
            -- "      ░      ░              ░ ░     ░ ░     ",
            -- "                          ░         ░ ░     ",
          }, "\n"),
        },
      }

      vim.api.nvim_create_user_command(
        "Message",
        function() Snacks.notifier.show_history() end,
        { desc = "Notification History" }
      )
      vim.api.nvim_create_user_command("Marks", function() Snacks.picker.marks() end, { desc = "Marks" })

      -- opts.picker = {
      --   win = {
      --     input = {
      --       keys = {
      --         ["<c-u>"] = { "preview_scroll_up", mode = { "i", "n" } },
      --         ["<c-d>"] = { "preview_scroll_down", mode = { "i", "n" } },
      --         ["<c-w>"] = { "cycle_win", mode = { "i", "n" } },
      --       },
      --     },
      --     list = {
      --       keys = {
      --         ["<c-u>"] = { "preview_scroll_up", mode = { "i", "n" } },
      --         ["<c-d>"] = { "preview_scroll_down", mode = { "i", "n" } },
      --         ["<c-w>"] = { "cycle_win" },
      --       }
      --     },
      --     preview = {
      --       keys = {
      --         ["<Esc>"] = "cancel",
      --         ["q"] = "close",
      --         -- ["i"] = "focus_input",
      --         ["<c-w>"] = "cycle_win",
      --       },
      --     },
      --   },
      -- }
      -- opts.image = {
      --   force = true,
      --   -- 启用对文档内嵌图片的支持
      --   doc = {
      --     enabled = true,
      --     -- 对于支持的终端，直接在 buffer 中渲染图片
      --     -- 这比浮动窗口的体验更无缝
      --     inline = true,
      --     -- 如果 `inline` 设为 false 或终端不支持，则在浮动窗口中显示
      --     -- float = {
      --     --   -- 浮动窗口的最大宽度和高度（字符数）
      --     --   max_width = 40,
      --     --   max_height = 20,
      --     -- },
      --   },
      --   -- 启用对 LaTeX 数学公式的渲染 ($...$, $$...$$)
      --   -- `math` 依赖于 `doc` 模块
      --   math = {
      --     enabled = true,
      --   },
      -- }
    end,
    keys = {
      { '<leader>s"', function() Snacks.picker.registers() end, desc = "Registers" },
      { "<leader>s/", function() Snacks.picker.search_history() end, desc = "Search History" },
      { "<leader>sa", function() Snacks.picker.autocmds() end, desc = "Autocmds" },
      { "<leader>sb", function() Snacks.picker.lines() end, desc = "Buffer Lines" },
      { "<leader>sc", function() Snacks.picker.command_history() end, desc = "Command History" },
      { "<leader>sC", function() Snacks.picker.commands() end, desc = "Commands" },
      { "<leader>sd", function() Snacks.picker.diagnostics() end, desc = "Diagnostics" },
      { "<leader>sD", function() Snacks.picker.diagnostics_buffer() end, desc = "Buffer Diagnostics" },
      { "<leader>sh", function() Snacks.picker.help() end, desc = "Help Pages" },
      { "<leader>sH", function() Snacks.picker.highlights() end, desc = "Highlights" },
      { "<leader>si", function() Snacks.picker.icons() end, desc = "Icons" },
      { "<leader>sj", function() Snacks.picker.jumps() end, desc = "Jumps" },
      { "<leader>sk", function() Snacks.picker.keymaps() end, desc = "Keymaps" },
      { "<leader>sl", function() Snacks.picker.loclist() end, desc = "Location List" },
      { "<leader>sm", function() Snacks.picker.marks() end, desc = "Marks" },
      { "<leader>sM", function() Snacks.picker.man() end, desc = "Man Pages" },
      { "<leader>sp", function() Snacks.picker.lazy() end, desc = "Search for Plugin Spec" },
      { "<leader>sq", function() Snacks.picker.qflist() end, desc = "Quickfix List" },
      { "<leader>sR", function() Snacks.picker.resume() end, desc = "Resume" },
      { "<leader>su", function() Snacks.picker.undo() end, desc = "Undo History" },
      { "<leader>st", function() Snacks.picker.colorschemes() end, desc = "Colorschemes" },
      { "<leader>sn", function() Snacks.picker.notifications() end, desc = "Notification History" },
    },
  },

  { "max397574/better-escape.nvim" },

  {
    "folke/flash.nvim",
    lazy = false,
    opts = {
      modes = {
        char = {
          -- 将 char_actions 设置为以下函数
          char_actions = function(motion)
            return {
              -- 按下相同的键会继续朝同一个方向搜索
              [motion] = "next",
              -- 按下大小写相反的键会朝相反方向搜索
              [motion:match "%l" and motion:upper() or motion:lower()] = "prev",
              [";"] = "next", -- set to `right` to always go right
              [","] = "prev", -- set to `left` to always go left
            }
          end,
        },
      },
      rainbow = {
        -- 启用彩虹模式
        enabled = true,
        --  颜色的步进和阴影
        shade = 5,
      },
    },
    keys = {
      { "s", mode = { "n", "x", "o" }, function() require("flash").jump() end, desc = "Flash" },
      { "S", mode = { "n", "x", "o" }, function() require("flash").treesitter() end, desc = "Flash Treesitter" },
      { "r", mode = "o", function() require("flash").remote() end, desc = "Remote Flash" },
      { "R", mode = { "o", "x" }, function() require("flash").treesitter_search() end, desc = "Treesitter Search" },
      { "<c-s>", mode = { "c" }, function() require("flash").toggle() end, desc = "Toggle Flash Search" },
    },
  },

  -- -- 将当前代码的上下文（例如函数定义）固定在窗口顶部
  -- {
  --   "nvim-treesitter/nvim-treesitter-context",
  --   opts = {
  --     enable = true, -- Enable this plugin (Can be enabled/disabled later via commands)
  --     multiwindow = false, -- Enable multiwindow support.
  --     max_lines = 0, -- How many lines the window should span. Values <= 0 mean no limit.
  --     min_window_height = 0, -- Minimum editor window height to enable context. Values <= 0 mean no limit.
  --     line_numbers = true,
  --     multiline_threshold = 20, -- Maximum number of lines to show for a single context
  --     trim_scope = "outer", -- Which context lines to discard if `max_lines` is exceeded. Choices: 'inner', 'outer'
  --     mode = "cursor", -- Line used to calculate context. Choices: 'cursor', 'topline'
  --     -- Separator between context and content. Should be a single character string, like '-'.
  --     -- When separator is set, the context will only show up when there are at least 2 lines above cursorline.
  --     separator = nil,
  --     zindex = 20, -- The Z-index of the context window
  --     on_attach = nil, -- (fun(buf: integer): boolean) return false to disable attaching
  --   },
  -- },

  {
    "jake-stewart/multicursor.nvim",
    branch = "1.0",
    config = function()
      local mc = require "multicursor-nvim"
      mc.setup()

      local set = vim.keymap.set

      -- -- Add or skip cursor above/below the main cursor.
      set({ "n", "x" }, "<up>", function() mc.lineAddCursor(-1) end)
      set({ "n", "x" }, "<down>", function() mc.lineAddCursor(1) end)
      set({ "n", "x" }, "<leader><up>", function() mc.lineSkipCursor(-1) end)
      set({ "n", "x" }, "<leader><down>", function() mc.lineSkipCursor(1) end)
      --
      -- -- Add or skip adding a new cursor by matching word/selection
      -- set({ "n", "x" }, "<leader>n", function() mc.matchAddCursor(1) end)
      -- set({ "n", "x" }, "<leader>s", function() mc.matchSkipCursor(1) end)
      -- set({ "n", "x" }, "<leader>N", function() mc.matchAddCursor(-1) end)
      -- set({ "n", "x" }, "<leader>S", function() mc.matchSkipCursor(-1) end)

      -- Add and remove cursors with control + left click.
      set("n", "<c-leftmouse>", mc.handleMouse)
      set("n", "<c-leftdrag>", mc.handleMouseDrag)
      set("n", "<c-leftrelease>", mc.handleMouseRelease)

      -- Disable and enable cursors.
      -- set({ "n", "x" }, "<c-q>", mc.toggleCursor)

      -- Mappings defined in a keymap layer only apply when there are
      -- multiple cursors. This lets you have overlapping mappings.
      mc.addKeymapLayer(function(layerSet)
        -- Select a different cursor as the main one.
        layerSet({ "n", "x" }, "<left>", mc.prevCursor)
        layerSet({ "n", "x" }, "<right>", mc.nextCursor)

        -- Delete the main cursor.
        layerSet({ "n", "x" }, "<leader>x", mc.deleteCursor)

        -- Enable and clear cursors using escape.
        layerSet("n", "<esc>", function()
          if not mc.cursorsEnabled() then
            mc.enableCursors()
          else
            mc.clearCursors()
          end
        end)
      end)

      -- Customize how cursors look.
      local hl = vim.api.nvim_set_hl
      hl(0, "MultiCursorCursor", { reverse = true })
      hl(0, "MultiCursorVisual", { link = "Visual" })
      hl(0, "MultiCursorSign", { link = "SignColumn" })
      hl(0, "MultiCursorMatchPreview", { link = "Search" })
      hl(0, "MultiCursorDisabledCursor", { reverse = true })
      hl(0, "MultiCursorDisabledVisual", { link = "Visual" })
      hl(0, "MultiCursorDisabledSign", { link = "SignColumn" })
    end,
  },

  {
    "mrjones2014/smart-splits.nvim",
    enabled = false,
  },

  {
    "OXY2DEV/markview.nvim",
    -- enabled = false,
    -- lazy = false,

    -- For blink.cmp's completion
    -- source
    dependencies = {
      "saghen/blink.cmp",
    },
  },
}
