-- Customize Treesitter

---@type LazySpec
return {
  "nvim-treesitter/nvim-treesitter",
  opts = function(_, opts)
    -- add more things to the ensure_installed table protecting against community packs modifying it
    opts.ensure_installed = require("astrocore").list_insert_unique(opts.ensure_installed, {
      "lua",
      "vim",
      "nu",
      -- add more arguments for adding more treesitter parsers
    })
    opts.textobjects.lsp_interop = {
      enable = true,
      border = "single",
      floating_preview_opts = {
        -- - height: (integer) height of floating window
        -- - width: (integer) width of floating window
        -- - wrap: (boolean, default true) wrap long lines
        -- - wrap_at: (integer) character to wrap at for computing height when wrap is enabled
        -- - max_width: (integer) maximal width of floating window
        -- - max_height: (integer) maximal height of floating window
        -- - pad_top: (integer) number of lines to pad contents at top
        -- - pad_bottom: (integer) number of lines to pad contents at bottom
        -- - focus_id: (string) if a popup with this id is opened, then focus it
        -- - close_events: (table) list of events that closes the floating window
        -- - focusable: (boolean, default true) Make float focusable
        -- - focus: (boolean, default true) If `true`, and if {focusable}
        --          is also `true`, focus an existing floating window with the same
        --          {focus_id}
      },
      peek_definition_code = {
        ["go"] = "@function.outer",
        ["gO"] = "@class.outer",
      },
    }
    -- opts.textobjects.select = {
    --   enable = true,
    --   lookahead = true,
    --   keymaps = {
    --     ["B"] = { query = "@block.outer", desc = "around block" },
    --     ["b"] = { query = "@block.inner", desc = "inside block" },
    --     ["C"] = { query = "@class.outer", desc = "around class" },
    --     ["c"] = { query = "@class.inner", desc = "inside class" },
    --     ["?"] = { query = "@conditional.outer", desc = "around conditional" },
    --     ["/"] = { query = "@conditional.inner", desc = "inside conditional" },
    --     ["F"] = { query = "@function.outer", desc = "around function" },
    --     ["f"] = { query = "@function.inner", desc = "inside function" },
    --     ["O"] = { query = "@loop.outer", desc = "around loop" },
    --     ["o"] = { query = "@loop.inner", desc = "inside loop" },
    --     ["A"] = { query = "@parameter.outer", desc = "around argument" },
    --     ["a"] = { query = "@parameter.inner", desc = "inside argument" },
    --   },
    -- }
  end,
}
