-- AstroCommunity: import any community modules here
-- We import this file in `lazy_setup.lua` before the `plugins/` folder.
-- This guarantees that the specs are processed before any user plugins.

---@type LazySpec
return {
  "AstroNvim/astrocommunity",
  { import = "astrocommunity.pack.lua" },
  { import = "astrocommunity.pack.rust" },
  { import = "astrocommunity.pack.go" },
  { import = "astrocommunity.pack.cpp" },
  { import = "astrocommunity.pack.html-css" },
  { import = "astrocommunity.pack.python" },
  { import = "astrocommunity.pack.typescript-deno" },
  { import = "astrocommunity.pack.toml" },
  { import = "astrocommunity.pack.yaml" },
  { import = "astrocommunity.pack.json" },
  { import = "astrocommunity.pack.proto" },
  { import = "astrocommunity.pack.typst" },
  { import = "astrocommunity.pack.markdown" },
  { import = "astrocommunity.pack.svelte" },
  -- { import = "astrocommunity.pack.kotlin" },
  -- { import = "astrocommunity.utility.noice-nvim" },

  -- { import = "astrocommunity.colorscheme.catppuccin" },
  -- { import = "astrocommunity.colorscheme.everforest" },
  -- { import = "astrocommunity.colorscheme.gruvbox-nvim" },
  -- { import = "astrocommunity.colorscheme.kanagawa-nvim" },
  -- { import = "astrocommunity.colorscheme.nightfox-nvim" },
  -- { import = "astrocommunity.colorscheme.tokyonight-nvim" },
  -- { import = "astrocommunity.colorscheme.rose-pine" },
  -- { import = "astrocommunity.colorscheme.onedarkpro-nvim" },
  { import = "astrocommunity.recipes.heirline-mode-text-statusline" },
  -- { import = "astrocommunity.bars-and-lines.lualine-nvim" },
  -- { import = "astrocommunity.recipes.heirline-nvchad-statusline" },
  { import = "astrocommunity.recipes.neovide" },
  -- { import = "astrocommunity.bars-and-lines.bufferline-nvim" },
  -- { import = "astrocommunity.editing-support.multicursors-nvim" },
  -- { import = "astrocommunity.editing-support.zen-mode-nvim" },
  -- { import = "astrocommunity.editing-support.copilotchat-nvim" },
  { import = "astrocommunity.test.neotest" },
  -- { import = "astrocommunity.markdown-and-latex.markview-nvim" },
  { import = "astrocommunity.markdown-and-latex.markdown-preview-nvim" },
  -- { import = "astrocommunity.color.transparent-nvim" },

  -- {import = "astrocommunity.completion.copilot-lua-cmp"}
  -- import/override with your plugins folder
  { import = "astrocommunity.recipes.ai" },
  { import = "astrocommunity.remote-development.remote-sshfs-nvim" },
}
