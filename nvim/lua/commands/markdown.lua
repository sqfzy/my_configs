local config = {
  browser_application = "Microsoft Edge",
}

local M = {}

local function current_markdown_path()
  if vim.bo.filetype ~= "markdown" then return nil, "当前缓冲区不是 Markdown 文件" end
  if vim.bo.modified then return nil, "当前 Markdown 文件尚未保存，请先保存后再预览" end

  local path = vim.api.nvim_buf_get_name(0)
  if path == "" then return nil, "当前 Markdown 文件尚未落盘" end

  return path
end

local function notify_open_failure(result)
  if result.code == 0 then return end

  local detail = vim.trim(result.stderr or "")
  if detail == "" then detail = ("退出码 %d"):format(result.code) end
  vim.notify("无法使用 Edge 打开 Markdown：" .. detail, vim.log.levels.ERROR)
end

function M.preview()
  local path, error_message = current_markdown_path()
  if not path then
    vim.notify(error_message, vim.log.levels.ERROR)
    return
  end

  vim.system({ "open", "-a", config.browser_application, path }, {}, function(result)
    vim.schedule(function() notify_open_failure(result) end)
  end)
end

return M
