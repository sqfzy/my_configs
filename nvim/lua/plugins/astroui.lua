-- AstroUI provides the basis for configuring the AstroNvim User Interface
-- Configuration documentation can be found with `:h astroui`
-- NOTE: We highly recommend setting up the Lua Language Server (`:LspInstall lua_ls`)
--       as this provides autocomplete and documentation while editing

local function random_from_table(table)
  math.randomseed(os.time()) -- 初始化随机数种子
  if #table == 0 then return nil end
  return table[math.random(#table)]
end

local themes = {
  tokyonight = {
    dawns = { "tokyonight-day" },
    days = { "tokyonight-day" },
    dusk = { "tokyonight-moon", "tokyonight-storm" },
    night = { "tokyonight-night" },
  },

  catppuccin = {
    dawns = { "catppuccin-latte" },
    days = { "catppuccin-latte" },
    dusk = { "catppuccin-macchiato", "catppuccin-frappe" },
    night = { "catppuccin-mocha" },
  },

  fox = {
    dawns = { "dawnfox" },
    days = { "dayfox" },
    dusk = { "duskfox" },
    night = { "nightfox", "terafox", "carbonfox" },
  },

  rose = {
    dawns = { "rose-pine-dawn" },
    days = { "rose-pine-dawn" },
    dusk = { "rose-pine-moon" },
    night = { "rose-pine-main" },
  },

  everforest = {
    dawns = { "everforest" },
    days = { "everforest" },
    dusk = { "everforest" },
    night = { "everforest" },
  },

  -- kanagawa = {
  --   dawns = { "kanagawa-lotus" },
  --   days = { "kanagawa-lotus" },
  --   dusk = { "kanagawa-wave" },
  --   night = { "kanagawa-dragon" },
  -- },

  osaka = {
    dawns = {},
    days = {},
    dusk = {},
    night = { "solarized-osaka" },
  },

  astrotheme = {
    dawns = { "astrolight" },
    days = { "astrolight" },
    dusk = { "astrodark" },
    night = { "astromars" },
  },
}
-- local function choose_theme_by_time(scheme)
--   local hr = tonumber(os.date("%H", os.time()))
--
--   if hr > 6 and hr <= 9 then
--     vim.opt.background = "light"
--     return random_from_table(scheme.dawn)
--   elseif hr > 9 and hr <= 16 then
--     vim.opt.background = "light"
--     return random_from_table(scheme.day)
--   elseif hr > 16 and hr <= 21 then
--     vim.opt.background = "dark"
--     return random_from_table(scheme.dusk)
--   else
--     vim.opt.background = "dark"
--     return random_from_table(scheme.night)
--   end
-- end

local function choose_theme_by_time_from_all(scheme)
  local hr = tonumber(os.date "%H")
  local time_of_day

  if hr > 7 and hr < 9 then
    vim.opt.background = "light"
    time_of_day = "dawns"
  elseif hr >= 9 and hr < 18 then
    vim.opt.background = "light"
    time_of_day = "days"
  elseif hr >= 18 and hr < 24 then
    vim.opt.background = "dark"
    time_of_day = "dusk"
  else
    vim.opt.background = "dark"
    time_of_day = "night"
  end

  local all_themes = {}
  for _, v in pairs(scheme) do
    for _, theme in ipairs(v[time_of_day]) do
      table.insert(all_themes, theme)
    end
  end

  return random_from_table(all_themes)
end

---@type LazySpec
return {
  {

    "AstroNvim/astroui",
    ---@type AstroUIOpts
    opts = {
      colorscheme = choose_theme_by_time_from_all(themes),

      -- AstroUI allows you to easily modify highlight groups easily for any and all colorschemes
      highlights = {
        init = { -- this table overrides highlights in all themes
          -- Normal = { ctermbg = 0 },
          -- LspReferenceText = { guisp = "#b8b8b8" },
          -- SnacksNormal = { fg = "#fdf6e3" },
          -- SnacksBorder = { ctermbg = 0 },
          -- TelescopePromptNormal = { ctermbg = 0 },
          -- TelescopePromptBorder = { ctermbg = 0 },
          -- TelescopePromptTitle = { ctermbg = 0 },
          -- TelescopeMultiSelection = { ctermbg = 0 },
          -- TelescopeSelection = { ctermbg = 0 },
          -- TelescopePromptTitle = { ctermbg = 0 },
          -- TelescopePromptTitle = { ctermbg = 0 },
          -- TelescopePromptTitle = { ctermbg = 0 },
          -- NeoTreeNormal = { ctermbg = 0 },
          -- NeoTreeNormalNC = { ctermbg = 0 },
          -- NeoTreeFloatNormal = { ctermbg = 0 },
          -- NeoTreeFloatTitle = { ctermbg = 0 },
          -- NeoTreeFloatBorder = { ctermbg = 0 },
          -- TerminalNormal = { ctermbg = 0 },
          -- TerminalBorder = { ctermbg = 0 },
          -- WinBar = { ctermbg = 0 },
          -- WinBarNC = { ctermbg = 0 },
          -- TabLine = { ctermbg = 0 }, -- tab not choose
          -- TabLineFill = { ctermbg = 0 },
          -- TabLineSel = { ctermbg = 0 }, -- tab choosed
          -- Float = { ctermbg = 0 },
          -- FloatBorder = { ctermbg = 0 },
          -- NormalFloat = { ctermbg = 0 },
          -- StatusLine = { ctermbg = 0 },
          -- StatusLineNC = { ctermbg = 0 },
          -- WhichKeyFloat = { ctermbg = 0 },
          -- WhichKeyBorder = { ctermbg = 0 },
          -- FloatTitle = { ctermbg = 0 },
          LspInlayHint = { fg = "#848cb5" },

          -- Normal
          Normal = { bg = "none" },
          SignColumn = { bg = "none" },
          FoldColumn = { bg = "none" },
          NormalFloat = { bg = "none" },
          NormalNC = { bg = "none" },
          NormalSB = { bg = "none" },
          FloatBorder = { bg = "none" },
          FloatTitle = { bg = "none" },
          -- WinBar
          WinBar = { bg = "none" },
          WinSeparator = { bg = "none" },
          WinBarNC = { bg = "none" },
          WhichKeyFloat = { bg = "none" },
          -- Telescope
          SnacksBorder = { bg = "none" },
          SnacksPromptTitle = { bg = "none" },
          SnacksPromptBorder = { bg = "none" },
          SnacksNormal = { bg = "none" },
          -- Diagnosis
          DiagnosticVirtualTextHint = { bg = "none" },
          DiagnosticVirtualTextWarn = { bg = "none" },
          DiagnosticVirtualTextInfo = { bg = "none" },
          DiagnosticVirtualTextError = { bg = "none" },
          -- NeoTree
          NeoTreeNormal = { bg = "none" },
          NeoTreeNormalNC = { bg = "none" },
          NeoTreeTabInactive = { bg = "none" },
          NeoTreeTabSeperatorActive = { bg = "none" },
          NeoTreeTabSeperatorInactive = { bg = "none" },
          NvimTreeTabSeperatorActive = { bg = "none" },
          NvimTreeTabSeperatorInactive = { bg = "none" },
          MiniTabLineFill = { bg = "none" },
          -- Spectre
          -- DiffChange = { fg = "#F2F3F5", bg = "#050a30" },
          -- DiffDelete = { fg = "#F2F3F5", bg = "#bd2c00" },
          -- StatusLine
          StatusLine = { bg = "none" },
          StatusLineNC = { bg = "none" },
          StatusLineTerm = { bg = "none" },
          StatusLineTermNC = { bg = "none" },
          VertSplit = { bg = "none" },
          -- QuickFixLine
          QuickFixLine = { bg = "none" },
          -- TabLine
          TabLine = { bg = "none" },
          TabLineSel = { bg = "none" },
          TabLineFill = { bg = "none" },
          -- Cursor
          CursorLineNr = { bg = "none" },
          CursorLine = { bg = "none" },
          ColorColumn = { bg = "none" },
          -- Search
          Search = { fg = "red" },
          IncSearch = { fg = "red" },
          -- Pmenu
          -- Pmenu = { bg = "none" },
          -- PmenuSel = { bg = "none" },
          -- PmenuSbar = { bg = "none" },
          -- PmenuThumb = { bg = "none" },
          -- Notifications
          NotifyINFOBody = { bg = "none" },
          NotifyWARNBody = { bg = "none" },
          NotifyERRORBody = { bg = "none" },
          NotifyDEBUGBody = { bg = "none" },
          NotifyTRACEBody = { bg = "none" },
          NotifyINFOBorder = { bg = "none" },
          NotifyWARNBorder = { bg = "none" },
          NotifyERRORBorder = { bg = "none" },
          NotifyDEBUGBorder = { bg = "none" },
          NotifyTRACEBorder = { bg = "none" },
          NotifyBackground = { bg = "#000000" },

          -- CmpItemMeum = {fg= "#848cb5"},
        },
        astrotheme = { -- a table of overrides/changes when applying the astrotheme theme
          -- Normal = { bg = "#000000" },
        },
        tokyonight = {
          -- link = "@Comment",
        },
      },
      -- Icons can be configured throughout the interface
      icons = {
        ActiveLSP = "",
        ActiveTS = " ",
        BufferClose = "",
        DapBreakpoint = "",
        DapBreakpointCondition = "",
        DapBreakpointRejected = "",
        DapLogPoint = "",
        DapStopped = "",
        DefaultFile = "",
        Diagnostic = "",
        DiagnosticError = "",
        DiagnosticHint = "",
        DiagnosticInfo = "",
        DiagnosticWarn = "",
        Ellipsis = "",
        FileModified = "",
        FileReadOnly = "",
        FoldClosed = "",
        FoldOpened = "",
        FolderClosed = "",
        FolderEmpty = "",
        FolderOpen = "",
        Git = "",
        GitAdd = "",
        GitBranch = "",
        GitChange = "",
        GitConflict = "",
        GitDelete = "",
        GitIgnored = "",
        GitRenamed = "",
        GitStaged = "",
        GitUnstaged = "",
        GitUntracked = "",
        LSPLoaded = "",
        -- LSPLoading1 = "",
        -- LSPLoading2 = "",
        -- LSPLoading3 = "",
        MacroRecording = "",
        Paste = "",
        Search = "",
        Selected = "",
        TabClose = "",

        -- configure the loading of the lsp in the status line
        LSPLoading1 = "⠋",
        LSPLoading2 = "⠙",
        LSPLoading3 = "⠹",
        LSPLoading4 = "⠸",
        LSPLoading5 = "⠼",
        LSPLoading6 = "⠴",
        LSPLoading7 = "⠦",
        LSPLoading8 = "⠧",
        LSPLoading9 = "⠇",
        LSPLoading10 = "⠏",
      },
    },
  },

  { "folke/tokyonight.nvim" },
  { "rose-pine/neovim", name = "rose-pine" },
  { "EdenEast/nightfox.nvim" },
  { "catppuccin/nvim", name = "catppuccin", priority = 1000 },
  { "savq/melange-nvim" },
  { "sainnhe/everforest" },
  { "rebelot/kanagawa.nvim" },
  { "craftzdog/solarized-osaka.nvim" },
  { "olimorris/onedarkpro.nvim" },
  { "navarasu/onedark.nvim" },

  {
    "rcarriga/nvim-notify",
    opts = function(_, opts)
      opts.background_colour = "#000000"
      -- opts.stages = "static"
      -- opts.render = "compact"
      -- opts.max_width = "30"
      -- opts.fps = 5
      -- opts.level = 1
      -- opts.timeout = 1000
    end,
  },

  {
    "folke/noice.nvim",
    enabled = true,
    opts = {
      lsp = {
        -- override markdown rendering so that **cmp** and other plugins use **Treesitter**
        override = {
          ["vim.lsp.util.convert_input_to_markdown_lines"] = false,
          ["vim.lsp.util.stylize_markdown"] = false,
          ["cmp.entry.get_documentation"] = false,
        },
        hover = {
          enabled = false,
          silent = true, -- set to true to not show a message if hover is not available
          view = nil, -- when nil, use defaults from documentation
          opts = {}, -- merged with defaults from documentation
        },
        -- 与 lsp_signature.nvim 冲突
        signature = {
          enabled = false,
          auto_open = {
            enabled = false,
            trigger = true, -- Automatically show signature help when typing a trigger character from the LSP
            luasnip = true, -- Will open signature help when jumping to Luasnip insert nodes
            throttle = 50, -- Debounce lsp signature help request by 50ms
          },
          view = nil, -- when nil, use defaults from documentation
          opts = {}, -- merged with defaults from documentation
        },
      },
      routes = {
        {
          filter = {
            event = "msg_show",
            find = " change;",
          },
          opts = { skip = true },
        },
        {
          filter = {
            event = "msg_show",
            kind = "message",
          },
          opts = { skip = true },
        },
        {
          filter = {
            event = "msg_show",
            find = "more lines",
          },
          opts = { skip = true },
        },

        {
          filter = {
            event = "msg_show",
            find = "fewer lines",
          },
          opts = { skip = true },
        },
        {
          filter = {
            event = "msg_show",
            find = "written",
          },
          opts = { skip = true },
        },
        {
          filter = {
            event = "msg_show",
            find = "lines yanked",
          },
          opts = { skip = true },
        },

        {
          filter = {
            event = "notify",
            find = "-32802: server cancelled the request",
          },
          opts = { skip = true },
        },
        {
          filter = {
            event = "msg_show",
            find = "/usr/share/nvim/runtime/lua/vim/lsp/semantic_tokens.lua",
          },
          opts = { skip = true },
        },
      },
    },
  },
}
