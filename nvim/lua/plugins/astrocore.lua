-- AstroCore provides a central place to modify mappings, vim options, autocommands, and more!
-- Configuration documentation can be found with `:h astrocore`
-- NOTE: We highly recommend setting up the Lua Language Server (`:LspInstall lua_ls`)
--       as this provides autocomplete and documentation while editing

---@type LazySpec
return {
  "AstroNvim/astrocore",
  ---@type AstroCoreOpts
  opts = {
    rooter = {
      -- list of detectors in order of prevalence, elements can be:
      --   "lsp" : lsp detection
      --   string[] : a list of directory patterns to look for
      --   fun(bufnr: integer): string|string[] : a function that takes a buffer number and outputs detected roots
      -- detector = {
      --   "lsp", -- highest priority is getting workspace from running language servers
      --   { ".git", "_darcs", ".hg", ".bzr", ".svn" }, -- next check for a version controlled parent directory
      --   { "lua", "MakeFile", "package.json" }, -- lastly check for known project root files
      -- },
      -- ignore things from root detection
      ignore = {
        servers = {}, -- list of language server names to ignore (Ex. { "efm" })
        dirs = {
          "~/work_space/demo_code/*",
        }, -- list of directory patterns (Ex. { "~/.cargo/*" })
      },
      -- -- automatically update working directory (update manually with `:AstroRoot`)
      -- autochdir = false,
      -- -- scope of working directory to change ("global"|"tab"|"win")
      -- scope = "global",
      -- -- show notification on every working directory change
      -- notify = false,
    },
    -- Configure core features of AstroNvim
    features = {
      large_buf = { size = 1024 * 256, lines = 10000 }, -- set global limits for large files for disabling features like treesitter
      autopairs = true, -- enable autopairs at start
      cmp = true, -- enable completion at start
      diagnostics = { virtual_text = false, virtual_lines = false }, -- diagnostic settings on startup
      highlighturl = true, -- highlight URLs at start
      notifications = true, -- enable notifications at start
    },
    -- Diagnostics configuration (for vim.diagnostics.config({...})) when diagnostics are on
    diagnostics = {
      virtual_text = false,
      underline = true,
    },
    -- passed to `vim.filetype.add`
    filetypes = {
      -- see `:h vim.filetype.add` for usage
      extension = {
        foo = "fooscript",
      },
      filename = {
        [".foorc"] = "fooscript",
      },
      pattern = {
        [".*/etc/foo/.*"] = "fooscript",
      },
    },
    -- vim options can be configured here
    options = {
      opt = { -- vim.opt.<key>
        relativenumber = false, -- sets vim.opt.relativenumber
        number = true, -- sets vim.opt.number
        spell = false, -- sets vim.opt.spell
        signcolumn = "yes", -- sets vim.opt.signcolumn to yes
        wrap = false, -- sets vim.opt.wrap
        cmdheight = 0,
        mouse = "a",
        cursorline = false,
        clipboard = "unnamedplus",
        guifont = "0xProto,LXGW WenKai,Hack_Nerd_Font:h12",
      },
      g = { -- vim.g.<key>
        -- configure global vim variables (vim.g)
        -- NOTE: `mapleader` and `maplocalleader` must be set in the AstroNvim opts or before `lazy.setup`
        -- This can be found in the `lua/lazy_setup.lua` file

        mkdp_width = 80,
      },
    },
    -- Mappings can be configured through AstroCore as well.
    -- NOTE: keycodes follow the casing in the vimdocs. For example, `<Leader>` must be capitalized
    mappings = {
      n = {
        -- 光标位移
        ["<S-Right>"] = { "<Left>" },
        ["L"] = { "5l" },
        ["H"] = { "5h" },
        ["J"] = { "5j" },
        ["K"] = { "5k" },
        ["<C-d>"] = { "10j" },
        ["<C-u>"] = { "10k" },
        ["mj"] = { "mJ" },
        ["mk"] = { "mK" },
        ["gj"] = { "`J" },
        ["gk"] = { "`K" },

        -- 行位移
        ["<A-S-j>"] = { ":m .+1<CR>==" },
        ["<A-S-k>"] = { ":m .-2<CR>==" },
        ["<A-j>"] = { "<S-j>" },

        -- buf位移
        ["<A-o>"] = { "<C-^>" }, -- 在两个最近的标签页间跳转

        -- 按范围删除
        ["c"] = { '"dc' },
        ["C"] = { '"dc' },
        -- ["s"] = { '"ds' },
        -- ["S"] = { '"dS' },
        ["x"] = { '"_x' }, --剪切一行
        ["X"] = { "dd" }, --剪切一行
        -- ["<C-x>"] = '"+dw', --剪切单词
        ["d"] = { '"_d' }, --删除
        ["D"] = { '"_D' },
        ["dL"] = { '"_d$' },
        ["dH"] = { '"_d^' },

        -- 按文本对象删除
        ["cb"] = { '"_cib' }, --()
        ["ci"] = { '"_ciB' }, --{}
        ["cw"] = { '"_ciw' }, --单词
        ["cs"] = { '"_ci"' }, --字符串
        ["c'"] = { "\"_ci'" }, -- ''
        ["c["] = { '"_ci[' }, -- []
        ["c,"] = { '"_ci<' }, -- <>
        ["c4"] = { '"_F$lvf$h"_di' }, -- $$

        ["db"] = { 'vi("_d' }, --()
        ["di"] = { 'vi{"_d' }, --{}
        ["ds"] = { 'vi""_d' }, --字符串
        ["d'"] = { "vi'\"_d" }, -- ''
        ["d["] = { 'vi["_d' }, -- []
        ["d,"] = { 'vi<"_d' }, -- <>
        ["d4"] = { '"_F$lvf$h"_d' }, -- $$

        ["Db"] = { '"tyi(da(h"tp' }, -- 删除()
        ["D9"] = { '"tyi(da(h"tp' }, -- 删除()
        ["Ds"] = { '"tyi"da"h"tp' }, -- 删除""
        ["D'"] = { "\"tyi'da'h\"tp" }, -- 删除''
        ["D["] = { '"tyi[da[h"tp' }, -- 删除[]
        ["Di"] = { '"tyi{da{h"tp' }, -- 删除{}
        ["<BS>"] = { '%"_x``"_x' }, -- 删除一对括号

        -- 删除buf
        -- ["<Leader>c"] = false,
        ["<Leader>C"] = false,
        ["<A-c>"] = { function() require("astrocore.buffer").close() end, desc = "Close buffer" },
        ["<A-C>"] = { function() require("astrocore.buffer").close_all(true) end, desc = "Close all buffers" },
        ["<A-h>"] = {
          function() require("astrocore.buffer").nav(-vim.v.count1) end,
          desc = "Previous Buffer",
        },
        ["<A-l>"] = {
          function() require("astrocore.buffer").nav(vim.v.count1) end,
          desc = "Next Buffer",
        },

        ["<Leader>b"] = { desc = "Buffer" },
        ["<Leader>bh"] = {
          function() require("astrocore.buffer").close_left() end,
          desc = "Close all buffers to the left",
        },
        ["<Leader>br"] = false,
        ["<Leader>bl"] = {
          function() require("astrocore.buffer").close_right() end,
          desc = "Close all buffers to the right",
        },

        -- ["dm"] = { function() vim.cmd "%s/\r//g" end, desc = "Remove ^M" },

        -- 添加标点、括号
        ["<A-;>"] = { "$a;<ESC>" }, --句尾添';'
        ["<A-,>"] = { "$a,<ESC>" },
        ["<A-.>"] = { "lbi<<ESC>ea><ESC>" },
        ["<A-s>"] = { 'lbi"<ESC>ea"<ESC>' },
        ["<A-i>"] = { "lbi{<ESC>ea}<ESC>" },
        ["<A-'>"] = { "lbi'<ESC>ea'<ESC>" },
        ["<A-b>"] = { "lbi(<ESC>ea)<ESC>" },
        ["<A-9>"] = { "lbi(<ESC>ea)<ESC>" },
        ["<A-[>"] = { "lbi[<ESC>ea]<ESC>" },
        ["<A-7>"] = "mtbi&<Esc>`t", -- 单词首部添加'&'
        ["<A-8>"] = "mtbi*<Esc>`t", -- 单词首部添加'*'

        -- 复制
        ["yL"] = { "y$" },

        ["yw"] = { "byw" }, -- 复制单词
        ["yib"] = { "yi(" },
        ["yis"] = { 'yi"' },
        ["yii"] = { "yi{" },
        ["yi4"] = { "F$lvf$hy" },

        -- 其它
        ["<C-a>"] = { "gg^vG$" }, -- 选中所有
        ["<A-a>"] = { "<C-a>" }, -- 值加1
        ["<A-d>"] = { "<C-x>" }, -- 值减1
        ["<A-f>"] = { "/<C-r>+<CR>" }, --搜寻复制内容
        ["<S-Enter>"] = "mto<Esc>`t", -- 在下一行插入空行
        ["<Leader>h"] = false,
        ["<Leader>;"] = {
          function()
            local wins = vim.api.nvim_tabpage_list_wins(0)
            if #wins > 1 and vim.bo[vim.api.nvim_win_get_buf(wins[1])].filetype == "neo-tree" then
              vim.fn.win_gotoid(wins[2]) -- go to non-neo-tree window to toggle alpha
            end
            require("alpha").start(false)
          end,
          desc = "Home Screen",
        },
        ["<Leader>E"] = {
          function()
            if vim.bo.filetype == "neo-tree" then
              vim.cmd.wincmd "p"
            else
              vim.cmd.Neotree "focus"
            end
          end,
          desc = "Toggle Explorer Focus",
        },
        ["zh"] = { "zc", desc = "Close fold under cursor" },
        ["zl"] = { "zo", desc = "Open fold under cursor" },

        -- 保存
        ["<Leader>W"] = {
          function()
            vim.lsp.buf.format(require("astrolsp").format_opts)
            vim.cmd "w!"
          end,
          desc = "Save with format",
        },
        ["<Leader>w"] = { "<cmd>w!<cr>", desc = "Save" },

        ["<Leader>n"] = { "", desc = "Neo-tree" },
        ["<Leader>nh"] = { "<cmd>Neotree ~/<CR>", desc = "Home" },
        ["<Leader>nw"] = { "<cmd>Neotree ~/work_space/<CR>", desc = "Work dir" },
        ["<Leader>nc"] = { "<cmd>Neotree ~/.config/nvim/<CR>", desc = "Config dir" },
        ["<Leader>nn"] = { "<cmd>Neotree dir=%:p:h<CR>", desc = "Current dir" },

        ["<A-w>"] = {
          "<C-w>w",
          desc = "Switch windows",
        },

        -- ["<Leader>a"] = { "", desc = "Avante" },

        -- ["<Leader>lc"] = {
        --   function() vim.print(vim.inspect(require("lspconfig")["<server_name>"].document_config)) end,
        --   desc = "Print LSP config",
        -- },

        -- 插件快捷键
        ["<Leader>o"] = { function() require("aerial").toggle() end, desc = "Symbols outline" },

        -- ["<Leader>c"] = { "", desc = "Colorscheme" },
        -- ["<Leader>ct"] = { "<cmd>colorscheme tokyonight<CR>", desc = "Tokyonight" },
        -- ["<Leader>cc"] = { "<cmd>colorscheme catppuccin<CR>", desc = "Catppuccin" },
        -- ["<Leader>cf"] = { "<cmd>colorscheme duskfox<CR>", desc = "Catppuccin" },
        -- ["<Leader>cr"] = { "<cmd>colorscheme rose-pine<CR>", desc = "Rose-pine" },
        -- ["<Leader>ce"] = { "<cmd>colorscheme everforest<CR>", desc = "Everforest" },
        -- ["<Leader>ck"] = { "<cmd>colorscheme kanagawa<CR>", desc = "Kanagawa" },
        -- ["<Leader>co"] = { "<cmd>colorscheme osaka<CR>", desc = "Osaka" },

        -- 打开终端
        ["<A-4>"] = {
          function()
            local dir = tostring(vim.fn.expand "%:p:h")
            require("toggleterm").exec("cd " .. dir, 3, nil, nil, "float", "Term3", false, true)
          end,
          desc = "ToggleTerm current dir",
        },
        ["<A-5>"] = {
          "<cmd>4ToggleTerm size=10 direction=horizontal<CR>",
          -- function() require("toggleterm").exec("zsh", 4, 10, nil, "horizontal", "Term4", false, true) end,
          desc = "ToggleTerm horizontal split",
        },
        ["<A-3>"] = {
          "<cmd>3ToggleTerm direction=float<CR>",
          -- function() require("toggleterm").exec("exec fish", 3, nil, nil, "float", "Term3", false, true) end,
          desc = "ToggleTerm float",
        },
        ["<A-2>"] = {
          "<cmd>2ToggleTerm size=10 direction=horizontal<CR>",
          -- function() require("toggleterm").exec("zsh", 2, 10, nil, "horizontal", "Term2", false, true) end,
          desc = "ToggleTerm horizontal split",
        },
        ["<A-1>"] = {
          "<cmd>1ToggleTerm size=50 direction=vertical<CR>",
          -- function() require("toggleterm").exec("zsh", 1, 50, nil, "vertical", "Term1", false, true) end,
          desc = "ToggleTerm vertical split",
        },

        -- { "<leader>sH", function() Snacks.picker.highlights() end, desc = "Highlights" },
        ["<Leader>fH"] = {
          function() require("snacks").picker.highlights() end,
          desc = "Snacks highlights",
        },

        ["<A-m>"] = false,

        ["<Leader><CR>"] = { "mmo<Esc>`m" },
      },
      i = {
        ["<S-Right>"] = { "<Left>" },

        ["jj"] = { "<Esc>" },
        ["jk"] = { "<Esc>" },

        ["<A-S-j>"] = { "<Esc>:m .+1<CR>==gi" },
        ["<A-S-k>"] = { "<Esc>:m .-2<CR>==gi" },

        ["<A-;>"] = { "<ESC>$a;" }, --句尾添';'
        ["<A-s>"] = { '<ESC>lbi"<ESC>ea"' },
        ["<A-i>"] = { "<ESC>lbi{<ESC>ea}" },
        ["<A-9>"] = { "<ESC>lbi(<ESC>ea)" },
        ["<A-'>"] = { "<ESC>lbi'<ESC>ea'" },
        ["<A-[>"] = { "<ESC>lbi[<ESC>ea]" },
        ["<A-,>"] = { "<ESC>lbi<<ESC>ea>" },
        ["<A-->"] = { "->" },
        ["<A-=>"] = { "=>" },
        -- ["<Tab>"] = "<cmd>tabNext<CR>",
        -- ["<S-Tab>"] = "<Left>",

        -- ["<S-l><S-l>"] = "<Esc><S-a>",
        -- ["<S-h><S-h>"] = "<Esc><S-i>",

        ["<C-h>"] = { "<Esc>gh" },
        ["<C-l>"] = { "<Esc>lgh" },

        ["<A-h>"] = { "<cmd>lua require('luasnip').jump(-1)<Cr>" },
        ["<A-l>"] = { "<cmd>lua require('luasnip').jump(1)<Cr>" },
      },
      v = {

        -- 移动行
        ["<A-S-j>"] = { ":m .+1<CR>==" },
        ["<A-S-k>"] = { ":m .-2<CR>==" },

        -- 光标位移
        ["<S-Right>"] = { "<Left>" },
        ["L"] = { "5l" },
        ["H"] = { "5h" },
        ["J"] = { "5j" },
        ["K"] = { "5k" },

        ["<C-a>"] = { "<ESC>gg" }, --取消全选
        ["<A-a>"] = { "<C-a>" },

        -- 复制与删除
        ["X"] = { "D" }, --剪切一行
        ["d"] = { '"_d' }, --删除
        ["D"] = { '"_D' },
        ["p"] = { '"_dP' }, -- 粘贴后不会复制被粘贴的文本
        -- ["1y"] = { '"1y' },
        -- ["1p"] = { '"_d"1P' },
        -- ["2y"] = { '"2y' },
        -- ["2p"] = { '"_d"2P' },
        -- ["3y"] = { '"3y' },
        -- ["3p"] = { '"_d"3P' },
        -- ["4y"] = { '"4y' },
        -- ["4p"] = { '"_d"4P' },
        -- ["5y"] = { '"5y' },
        -- ["5p"] = { '"_d"5P' },
        -- ["1Y"] = { '"1Y' },
        -- ["1P"] = { '"_d"1P' },
        -- ["2Y"] = { '"2Y' },
        -- ["2P"] = { '"_d"2P' },
        -- ["3Y"] = { '"3Y' },
        -- ["3P"] = { '"_d"3P' },
        -- ["4Y"] = { '"4Y' },
        -- ["4P"] = { '"_d"4P' },
        -- ["5Y"] = { '"5Y' },
        -- ["5P"] = { '"_d"5P' },

        -- 添加标点、括号
        ["<A-s>"] = { '"-xi""<Esc>"-P' },
        ["<A-i>"] = { '"-xi{}<Esc>"-P' },
        ["<A-'>"] = { "\"-xi''<Esc>\"-P" },
        ["<A-b>"] = { '"-xi()<Esc>"-P' },
        ["<A-[>"] = { '"-xi[]<Esc>"-P' },
        ["<A-.>"] = { '"-xi<><Esc>"-P' },
        ["<A-8>"] = { '"-xi**<Esc>"-P' },
        ["<A-4>"] = { '"-xi$$<Esc>"-P' },

        -- ["s"] = false,
        -- ["S"] = false,
      },
      t = {
        ["<S-Right>"] = { "<Left>" },

        -- 关闭终端
        ["<A-4>"] = { function() require("toggleterm").exec("exit", 3) end, desc = "ToggleTerm float" },
        ["<A-3>"] = { "<cmd>3ToggleTerm direction=float<cr>", desc = "ToggleTerm float" },
        ["<A-2>"] = { "<cmd>2ToggleTerm size=10 direction=horizontal<cr>", desc = "ToggleTerm horizontal split" },
        ["<A-1>"] = { "<cmd>1ToggleTerm size=50 direction=vertical<cr>", desc = "ToggleTerm vertical split" },
        ["<Esc>"] = { "<c-\\><c-n>", desc = "Back normal mode" },
      },
      s = {
        ["p"] = { "p" },
        ["d"] = { "d" },
        ["D"] = { "D" },
        ["<BS>"] = { "<BS>i" },
        ["<C-l>"] = { "<Right>" },
        ["<C-h>"] = { "<Left>" },

        ["<A-h>"] = { "<cmd>lua require('luasnip').jump(-1)<Cr>" },
        ["<A-l>"] = { "<cmd>lua require('luasnip').jump(1)<Cr>" },
      },
    },
  },
}
