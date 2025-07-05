if not vim.g.neovide then
  return {} -- do nothing if not in a Neovide session
end

return {
  "AstroNvim/astrocore",
  ---@type AstroCoreOpts
  opts = {
    options = {
      opt = { -- configure vim.opt options
        -- configure font
        -- line spacing
        -- linespace = 0,
      },
      g = { -- configure vim.g variables
        neovide_opacity = 0.85,
        -- neovide_theme = "auto",
        neovide_hide_mouse_when_typing = true,
        neovide_fullscreen = true,
      },
    },
  },
}

-- if vim.g.neovide then
--   vim.g.neovide_transparency = 0.85
--   vim.g.neovide_hide_mouse_when_typing = true
--   vim.g.neovide_theme = "auto"
--   -- vim.g.neovide_refresh_rate = 60
--   -- vim.g.neovide_confirm_quit = true
--   vim.g.neovide_fullscreen = true
--   -- vim.g.neovide_remember_window_size = true
--   -- vim.g.neovide_cursor_animation_length = 0.05
--   -- vim.g.neovide_cursor_trail_size = 0.5
--   -- vim.g.neovide_cursor_vfx_mode = "pixiedust"
--   --
--   -- vim.g.neovide_hide_mouse_when_typing = true
--   -- vim.g.neovide_refresh_rate = 60
--   -- vim.g.neovide_refresh_rate_idle = 5
--   -- vim.g.neovide_no_idle = true
--   -- vim.g.neovide_confirm_quit = true
--   -- vim.g.neovide_input_use_logo = true
--   --
--   -- vim.g.neovide_padding_top = 0
--   -- vim.g.neovide_padding_bottom = 0
--   -- vim.g.neovide_padding_right = 0
--   -- vim.g.neovide_padding_left = 0
-- end
--
