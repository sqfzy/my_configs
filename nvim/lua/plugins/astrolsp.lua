-- AstroLSP allows you to customize the features in AstroNvim's LSP configuration engine
-- Configuration documentation can be found with `:h astrolsp`
-- NOTE: We highly recommend setting up the Lua Language Server (`:LspInstall lua_ls`)
--       as this provides autocomplete and documentation while editing

local Snacks = require "snacks"

local rust_settings = {
  ["rust-analyzer"] = {
    -- ["imports.granularity.enforce"] = true,

    check = {
      command = "clippy",
      extraArgs = {
        "--no-deps",
      },
    },
    checkOnSave = false,
    files = {
      excludeDirs = {
        ".direnv",
        ".git",
        "target",
      },
    },
    completion = {
      snippets = {
        custom = {
          -- "Arc::new": {
          --     "postfix": "arc",
          --     "body": "Arc::new(${receiver})",
          --     "requires": "std::sync::Arc",
          --     "description": "Put the expression into an `Arc`",
          --     "scope": "expr"
          -- },
          -- ["Deref"] = {
          --   postfix = "def",
          --   body = "*${receiver}",
          --   scope = "expr",
          -- },
          -- ["DerefMut"] = {
          --   postfix = "defm",
          --   body = "*mut ${receiver}",
          --   scope = "expr",
          -- },
        },
      },
    },
    inlayHints = {
      closureCaptureHints = {
        enable = true,
      },
      discriminantHints = {
        enable = true,
      },
      expressionAdjustmentHints = {
        -- enable = true,
      },
      lifetimeElisionHints = {
        enable = true,
      },
    },
    lens = {
      references = {
        adt = {
          enable = true,
        },
        enumVariant = {
          enable = true,
        },
        method = {
          enable = true,
        },
        trait = {
          enable = true,
        },
      },
    },
    hover = {
      -- memoryLayout = {
      --   niches = true,
      -- },
    },
    cargo = {
      extraEnv = { CARGO_PROFILE_RUST_ANALYZER_INHERITS = "dev" },
      extraArgs = { "--profile", "rust-analyzer" },
    },
  },
}

---@type LazySpec
return {
  {
    "AstroNvim/astrolsp",
    ---@type AstroLSPOpts
    opts = {
      -- Configuration table of features provided by AstroLSP
      features = {
        codelens = true, -- enable/disable codelens refresh on start
        inlay_hints = true, -- enable/disable inlay hints on start
        semantic_tokens = true, -- enable/disable semantic token highlighting
        signature_help = false,
      },
      -- customize lsp formatting options
      formatting = {
        -- control auto formatting on save
        format_on_save = {
          enabled = false, -- enable or disable format on save globally
          allow_filetypes = { -- enable format on save for specified filetypes only
            -- "go",
          },
          ignore_filetypes = { -- disable format on save for specified filetypes
            -- "python",
          },
        },
        disabled = { -- disable formatting capabilities for the listed language servers
          -- disable lua_ls formatting capability if you want to use StyLua to format your lua code
          -- "lua_ls",
        },
        timeout_ms = 1000, -- default format timeout
        -- filter = function(client) -- fully override the default formatting function
        --   return true
        -- end
      },
      -- enable servers that you already have installed without mason
      servers = {
        "nushell",
        -- "pyright"
      },
      -- customize language server configuration options passed to `lspconfig`
      ---@diagnostic disable: missing-fields
      config = {
        tinymist = {
          single_file_support = true,
        },
        fish_lsp = {
          command = "fish-lsp",
          filetypes = { "fish" },
          args = { "start" },
        },
        rust_analyzer = {
          settings = rust_settings,
          root_dir = function(fname)
            local root_patterns = require("lspconfig").util.root_pattern("Cargo.toml", "rust-project.json")
            local root_dir = root_patterns(fname)

            if root_dir and root_dir:find "demo_code" then
              return nil
            else
              return root_dir
            end
          end,
          single_file_support = true,
        },
        -- clangd = { capabilities = { offsetEncoding = "utf-8" } },
      },
      -- customize how language servers are attached
      handlers = {
        -- a function without a key is simply the default handler, functions take two parameters, the server name and the configured options table for that server
        -- function(server, opts) require("lspconfig")[server].setup(opts) end

        -- the key is the server that is being setup with `lspconfig`
        -- rust_analyzer = false, -- setting a handler to false will disable the set up of that language server
        -- pyright = function(_, opts) require("lspconfig").pyright.setup(opts) end -- or a custom handler function can be passed
      },
      -- Configure buffer local auto commands to add when attaching a language server
      autocmds = {
        -- first key is the `augroup` to add the auto commands to (:h augroup)
        lsp_codelens_refresh = {
          -- Optional condition to create/delete auto command group
          -- can either be a string of a client capability or a function of `fun(client, bufnr): boolean`
          -- condition will be resolved for each client on each execution and if it ever fails for all clients,
          -- the auto commands will be deleted for that buffer
          cond = "textDocument/codeLens",
          -- cond = function(client, bufnr) return client.name == "lua_ls" end,
          -- list of auto commands to set
          {
            -- events to trigger
            event = { "InsertLeave", "BufEnter" },
            -- the rest of the autocmd options (:h nvim_create_autocmd)
            desc = "Refresh codelens (buffer)",
            callback = function(args)
              if require("astrolsp").config.features.codelens then vim.lsp.codelens.refresh { bufnr = args.buf } end
            end,
          },
        },
      },
      -- mappings to be set up on attaching of a language server
      mappings = {
        n = {
          gl = { function() vim.diagnostic.open_float() end, desc = "Hover diagnostics" },
          gd = { function() Snacks.picker.lsp_definitions() end, desc = "Goto Definition" },
          gD = { function() Snacks.picker.lsp_declarations() end, desc = "Goto Declaration" },
          gr = { function() Snacks.picker.lsp_references() end, nowait = true, desc = "References" },
          gI = { function() Snacks.picker.lsp_implementations() end, desc = "Goto Implementation" },
          gy = { function() Snacks.picker.lsp_type_definitions() end, desc = "Goto T[y]pe Definition" },

          ["<A-k>"] = {
            function()
              vim.lsp.buf.hover {
                border = "rounded",
              }
            end,
            desc = "Hover",
          },

          -- ["<Leader>lR"] = {
          --   function() require("snacks").picker.lsp_references() end,
          --   desc = "References",
          -- },

          ["<Leader>ls"] = {
            function() Snacks.picker.lsp_symbols() end,
            desc = "Symbols",
          },

          ["<Leader>lS"] = {
            function() Snacks.picker.lsp_workspace_symbols() end,
            desc = "Workspace Symbols",
          },

          ["<Leader>lc"] = {
            function() Snacks.picker.lsp_config() end,
            desc = "Lsp Config",
          },

          -- ["<A-d>"] = {function() vim.lsp.buf.definition() end, desc = "Definition"},
          -- ["<A-D>"] = {function() vim.lsp.buf.declaration() end, desc = "Declaration"},
          -- ["<A-i>"] = {function() vim.lsp.buf.implementation() end, desc = "Implementation"},
          -- ["<A-t>"] = {function() vim.lsp.buf.type_definition() end, desc = "Type Definition"},
          -- ["<A-s>"] = {function() vim.lsp.buf.signature_help() end, desc = "Signature Help"},
          -- ["<Leader>la"] = { function() vim.lsp.buf.code_action() end, desc = "Code Action" },
          -- ["<A-f>"] = {function() vim.lsp.buf.formatting() end, desc = "Format"},
          -- ["<A-n>"] = {function() vim.lsp.diagnostic.goto_next() end, desc = "Next Diagnostic"},
          -- ["<A-p>"] = {function() vim.lsp.diagnostic.goto_prev() end, desc = "Previous Diagnostic"},
          -- ["<A-l>"] = {function() vim.lsp.diagnostic.show_line_diagnostics() end, desc = "Line Diagnostics"},
          -- ["<A-L>"] = {function() vim.lsp.diagnostic.set_loclist() end, desc = "Set Loclist"},
          -- ["<A-o>"] = {function() vim.lsp.diagnostic.open_float() end, desc = "Open Diagnostics"},
          -- ["<A-O>"] = {function() vim.lsp.diagnostic.close_float() end, desc = "Close Diagnostics"},
          -- ["<A-c>"] = {function() vim.lsp.buf.clear_references() end, desc = "Clear References"},
          -- ["<A-C>"] = {function() vim.lsp.buf.clear_references() end, desc = "Clear References"},
          -- ["<A-w>"] = {function() vim.lsp.buf.workspace_symbol() end, desc = "Workspace Symbol"},
          -- ["<A-W>"] = {function() vim.lsp.buf.document_symbol() end, desc = "Document Symbol"},
          -- ["<A-x>"] = {function() vim.lsp.stop_client(vim.lsp.get_active_clients()) end, desc = "Stop LSP"},
          -- ["<A-X>"] = {function() vim.lsp.stop_client(vim.lsp.get_active_clients()) end, desc = "Stop LSP"},
          -- ["<A-q>"] = {function() vim.lsp.buf.rename() end, desc = "Rename"},
          -- ["<A-Q>"] = {function() vim.lsp.buf.rename() end, desc = "Rename"},
          -- ["<A-z>"] = {function() vim.lsp.buf.code_lens_action() end, desc = "Code Lens"},
          -- ["<A-Z>"] = {function() vim.lsp.buf.code_lens_action() end, desc = "Code Lens"},
          -- ["<A-g>"] = {function() vim.lsp.buf.document_highlight() end, desc = "Document Highlight"},
          -- ["<A-G>"] = {function() vim.lsp.buf.document_highlight() end, desc = "Document Highlight"},
          -- ["<A-e>"] = {function() vim.lsp.buf.code_action() end, desc = "Code Action"},
          -- ["<A-E>"] = {function() vim.lsp.buf.code_action() end, desc = "Code Action"},
          -- ["<A-v>"] = {function() vim.lsp.buf.definition() end, desc = "Definition"},
          -- ["<A-V>"] = {function() vim.lsp.buf.definition() end, desc = "Definition"},
          -- ["<A-m>"] = {function() vim.lsp.buf.implementation() end, desc = "Implementation"},
          -- ["<A-M>"] = {function() vim.lsp.buf.implementation() end, desc = "Implementation"},
          -- ["<A-y>"] = {function() vim.lsp.buf.type_definition() end, desc = "Type Definition"},
          -- ["<A-Y>"] = {function() vim.lsp.buf.type_definition() end, desc = "Type Definition"},
          -- ["<A-u>"] = {function() vim.lsp.buf.references() end, desc = "References"},
          -- ["<A-U>"] = {function() vim.lsp.buf.references() end, desc = "References"},
          -- ["<A-h>"] = {function() vim.lsp.buf.signature_help() end, desc = "Signature Help"},
          -- ["<A-H>"] = {function() vim.lsp.buf.signature_help()
        },
      },
      -- A custom `on_attach` function to be run after the default `on_attach` function
      -- takes two parameters `client` and `bufnr`  (`:h lspconfig-setup`)
      on_attach = function(client, bufnr)
        -- this would disable semanticTokensProvider for all clients
        -- client.server_capabilities.semanticTokensProvider = nil

        if client.name == "rust_analyzer" then
          -- 获取当前浮动窗口的 ID
          local function get_floating_win_id()
            for _, win in pairs(vim.api.nvim_tabpage_list_wins(0)) do
              if vim.api.nvim_win_get_config(win).relative ~= "" then return win end
            end
            return nil
          end

          vim.keymap.set(
            "n",
            "<A-k>",
            function() vim.cmd.RustLsp { "hover", "actions" } end,
            { silent = true, buffer = bufnr }
          )

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
        end
      end,
    },
  },

  {
    "mrcjkb/rustaceanvim",
    opts = function(_, opts)
      opts.tools.float_win_config = {
        border = "rounded",
      }
    end,
  },
}
