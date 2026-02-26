return { -- override nvim-cmp plugin
  {
    "Saghen/blink.cmp",
    opts = function(_, opts)
      opts.keymap["<A-m>"] = {
        function()
          if vim.g.ai_accept then return vim.g.ai_accept() end
        end,
      }
      opts.keymap["<Tab>"] = { "select_and_accept", "fallback" }
      opts.keymap["<C-n>"] = { "select_next" }
      opts.keymap["<C-p>"] = { "select_prev" }
      opts.keymap["<C-m>"] = { "select_and_accept" }
    end,
  },

  {
    "L3MON4D3/LuaSnip",
    config = function(plugin, opts)
      -- require "astronvim.plugins.configs.luasnip"(plugin, opts) -- include the default astronvim config that calls the setup call
      -- add more custom luasnip configuration such as filetype extend or custom snippets
      local luasnip = require "luasnip"
      luasnip.filetype_extend("javascript", { "javascriptreact" })

      require("luasnip.loaders.from_lua").lazy_load { paths = { "./snippets/luasnippets" } }
      require("luasnip.loaders.from_vscode").lazy_load { paths = { "/snippets/vscode/" }, exclude = { "rust" } }
    end,
  },

  {
    "windwp/nvim-autopairs",
    config = function(plugin, opts)
      require "astronvim.plugins.configs.nvim-autopairs"(plugin, opts) -- include the default astronvim config that calls the setup call
      -- add more custom autopairs configuration such as custom rules
      local npairs = require "nvim-autopairs"
      local Rule = require "nvim-autopairs.rule"
      local cond = require "nvim-autopairs.conds"

      npairs.add_rules {

        -- 注释
        Rule("/* ", " */", { "c", "cpp", "css", "javascript", "php", "rust", "typst" }):with_pair(
          cond.not_inside_quote()
        ),
        Rule("//", " ", { "c", "cpp", "javascript", "php", "rust", "typst" })
          :with_pair(cond.not_inside_quote())
          :replace_endpair(function(opts)
            local prev_2char = opts.line:sub(opts.col - 2, opts.col - 1)
            if prev_2char:match "^/" then
              return "<bs><bs>// "
            elseif prev_2char:match "^%S" then
              return "<bs><bs> // "
            else
              return "<bs><bs>// "
            end
          end)
          :set_end_pair_length(0),
        Rule("// /", "", { "rust" })
          :with_pair(cond.not_inside_quote)
          :replace_endpair(function() return "<bs><bs>/ " end)
          :set_end_pair_length(0),
        Rule("// !", "", { "rust" })
          :with_pair(cond.not_inside_quote)
          :replace_endpair(function() return "<bs><bs>! " end)
          :set_end_pair_length(0),
        Rule("#", "", { "python" })
          :with_pair(cond.not_inside_quote())
          :replace_endpair(function(opts)
            local prev_2char = opts.line:sub(opts.col - 2, opts.col - 1)
            if prev_2char == "" then
              return " "
            elseif prev_2char == "  " then
              return " "
            elseif prev_2char:match "#" then
              return ""
            elseif prev_2char:match "%S%s" then
              return "<bs> # "
            elseif prev_2char:match "%S$" then
              return "<bs>  # "
            else
              return ""
            end
          end)
          :set_end_pair_length(0),
        -- Rule("<", ">", {
        --   -- if you use nvim-ts-autotag, you may want to exclude these filetypes from this rule
        --   -- so that it doesn't conflict with nvim-ts-autotag
        --   "-html",
        --   "-javascriptreact",
        --   "-typescriptreact",
        --   "rust",
        --   "cpp",
        --   "c",
        --   "lua",
        -- }):with_pair(
        --   -- regex will make it so that it will auto-pair on
        --   -- `a<` but not `a <`
        --   -- The `:?:?` part makes it also
        --   -- work on Rust generics like `some_func::<T>()`
        --   cond.before_regex("%a+:?:?$", 3)
        -- ):with_move(function(opts) return opts.char == ">" end),
        Rule("<>", "", { "rust", "cpp", "c", "html", "lua" }):with_pair(cond.none):set_end_pair_length(1),
        Rule("||", "", { "rust" }):with_pair(cond.none):set_end_pair_length(1),
        -- \t  \n
        Rule("\\t", "", { "c", "cpp", "php", "python" })
          :with_pair(cond.not_inside_quote())
          :replace_endpair(function() return "<bs><bs>'\\t'" end)
          :set_end_pair_length(0),
        Rule("$", "", { "typst", "tex", "latex" }):with_cr(cond.none),
        -- Rule("```%w*", "", { "typst", "tex", "latex" }):use_regex(true):with_cr(cond.none),
        -- Rule("`", "", { "typst", "tex", "latex" }),
        Rule("$$", "", { "typst", "tex", "latex" }):with_pair(cond.none):set_end_pair_length(1),
        Rule('""', "", { "typst", "tex", "latex" }):with_pair(cond.none):set_end_pair_length(1),
        Rule("''", "", { "typst", "tex", "latex" }):with_pair(cond.none):set_end_pair_length(1),
        Rule("**", "", { "typst", "tex", "latex" }):with_pair(cond.none):set_end_pair_length(1),
        Rule("__", "", { "typst", "tex", "latex" }):with_pair(cond.none):set_end_pair_length(1),
      }
    end,
  },

  {
    "zbirenbaum/copilot.lua",
    -- enabled = false,
    cmd = "Copilot",
    event = "User AstroFile",
    opts = {
      --   panel = {
      --     enabled = false,
      --     auto_refresh = false,
      --     keymap = {
      --       jump_prev = "[[",
      --       jump_next = "]]",
      --       accept = "<CR>",
      --       refresh = "gr",
      --       open = "<M-CR>",
      --     },
      --     layout = {
      --       position = "bottom", -- | top | left | right
      --       ratio = 0.4,
      --     },
      --   },

      suggestion = {
        enabled = true,
        auto_trigger = true,
        debounce = 75,
        keymap = {
          -- accept = "<A-m>",
          accept = false, -- handled by completion engine
          accept_word = false,
          accept_line = false,
          next = "<A-n>",
          prev = "<A-p>",
          -- dismiss = "<leader>cE",
        },
        -- keymap = {
        -- 	accept = "<M-l>",
        -- 	accept_word = false,
        -- 	accept_line = false,
        -- 	next = "<M-]>",
        -- 	prev = "<M-[>",
        -- 	dismiss = "<C-]>",
        -- },
      },
      filetypes = {
        yaml = true,
        markdown = true,
        help = false,
        gitcommit = false,
        gitrebase = false,
        hgcommit = false,
        svn = false,
        cvs = false,
        ["."] = true,
      },
      -- copilot_model = "gpt-4o-copilot",
      -- copilot_node_command = "node",
      -- server_opts_overrides = {},
    },
    specs = {
      {
        "AstroNvim/astrocore",
        opts = {
          options = {
            g = {
              ai_accept = function()
                if require("copilot.suggestion").is_visible() then
                  require("copilot.suggestion").accept()
                  return true
                end
              end,
            },
          },
        },
      },
    },
  },
  {
    "Exafunction/codeium.nvim",
    enabled = false,
    cmd = "Codeium",
    event = "InsertEnter",
    build = ":Codeium Auth",
    opts = {
      virtual_text = {
        enabled = true,
        key_bindings = {
          accept = false, -- handled by completion engine
          next = "<M-n>",
          prev = "<M-p>",
        },
      },
    },
    specs = {
      {
        "AstroNvim/astrocore",
        opts = {
          options = {
            g = {
              ai_accept = function()
                if require("codeium.virtual_text").get_current_completion_item() then
                  vim.api.nvim_input(require("codeium.virtual_text").accept())
                  return true
                end
              end,
            },
          },
        },
      },
    },
  },
}
