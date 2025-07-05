local ls = require "luasnip"
local s = ls.snippet
local sn = ls.snippet_node -- 只用来包含其它节点，可用于dynamic_node返回
local t = ls.text_node -- 文本节点
local i = ls.insert_node -- 插入节点
local c = ls.choice_node -- 可变的节点
local d = ls.dynamic_node -- 与函数节点类似，但返回节点
local f = ls.function_node -- 返回字符串
local extras = require "luasnip.extras"
local rep = extras.rep
local fmt = require("luasnip.extras.fmt").fmt

return {
  s("!", {
    t { "#include <stdio.h>" },
    t { "", "#include <stdlib.h>" },
    t { "", "", "int main(int argc, char *argv[]) {" },
    t { "", "  " },
    i(1, "//"), -- 在此处开始写,顺序为1,2,3...n,0
    t { "", "", "  return EXIT_SUCCESS;" },
    t { "", "}" },
  }),
  s(
    { trig = "SEEK", dscr = "fwrite()的第三个参数" },
    c(1, {
      t "SEEK_SET",
      t "SEEK_CUR",
      t "SEEK_END",
    })
  ),
  s({ trig = "FLT", dscr = "float.h中的宏" }, t "FLT_EPSILON"),
  s({ trig = "CLO", dscr = "time.h中的宏，表示一秒有多少个时钟计时单元" }, t "CLOCKS_PER_SEC"),

  --------------------------- 创建可变参数的函数 -----------------------------------
  s({ trig = "va_list", dscr = "创建可变参数列表默认名为valist" }, t "va_list valist;"),
  s(
    { trig = "va_start", dscr = "初始化可变参数列表,valist为默认列表,num为参数个数" },
    t "va_start(valist, num);"
  ),
  s(
    { trig = "va_arg", dscr = "使用列表中的下一个参数,默认参数类型为int" },
    sn(1, {
      t "va_arg(valist,",
      i(1, "int"),
      t ")",
    })
  ),
  s({ trig = "va_end", dscr = "清理结束列表" }, t "va_end(valist);"),
  s(
    { trig = "for([%w_])(%s)", regTrig = true, snippetType = "autosnippet" },
    fmt(
      [[
  for (int {} = 0; {} < {}; {}++) {{
    {}
  }}
    ]],
      {
        d(1, function(_, snip)
          -- captures[1],获取正则()中的字符作为insert节点的文本
          return sn(1, t(snip.captures[1]))
        end),
        rep(1),
        c(2, { i(1, "len"), sn(1, { t "sizeof(", i(1, "arr"), t ")" }) }),
        rep(1),
        i(3),
      }
    )
  ),
  s({
    trig = "debug(%d)(%s)",
    regTrig = true,
    snippetType = "autosnippet",
  }, {
    f(function(args, snip) return 'printf("debug' .. snip.captures[1] .. '\\n");' end, {}),
  }),
  s({
    trig = "\\n(%s)",
    regTrig = true,
    snippetType = "autosnippet",
  }, {
    t 'printf("\\n");',
  }),

  --  s(
  --    { trig = "fori" },
  --    fmt(
  --      [[
  -- for (int {} = 0; {} < {}; {}++) {{
  --   {}
  -- }}
  --   ]],
  --      {
  --        i(1, "i"),
  --        rep(1),
  --        i(2, "len"),
  --        rep(1),
  --        i(3),
  --      }
  --    )
  --  ),
  -- debug

  s("INCLUDE", {
    d(1, function(args, snip)
      -- Create a table of nodes that will go into the header choice_node
      local headers_to_load_into_choice_node = {}

      -- Step 1: get companion .h file if the current file is a .c or .cpp file excluding main.c
      local extension = vim.fn.expand "%:e"
      local is_main = vim.fn.expand("%"):match "main%.cp?p?" ~= nil
      if (extension == "c" or extension == "cpp") and not is_main then
        local matching_h_file = vim.fn.expand("%:t"):gsub("%.c", ".h")
        local companion_header_file = string.format('#include "%s"', matching_h_file)
        table.insert(headers_to_load_into_choice_node, t(companion_header_file))
      end

      -- Step 2: get all the local headers in current directory and below
      local current_file_directory = vim.fn.expand "%:h"
      local local_header_files = require("plenary.scandir").scan_dir(
        current_file_directory,
        { respect_gitignore = true, search_pattern = ".*%.h$" }
      )

      -- Clean up and insert the detected local header files
      for _, local_header_name in ipairs(local_header_files) do
        -- Trim down path to be a true relative path to the current file
        local shortened_header_path = local_header_name:gsub(current_file_directory, "")
        -- Replace '\' with '/'
        shortened_header_path = shortened_header_path:gsub([[\+]], "/")
        -- Remove leading forward slash
        shortened_header_path = shortened_header_path:gsub("^/", "")
        local new_header = t(string.format('#include "%s"', shortened_header_path))
        table.insert(headers_to_load_into_choice_node, new_header)
      end

      -- Step 3: allow for custom insert_nodes for local and system headers
      local custom_insert_nodes = {
        sn(
          nil,
          fmt(
            [[
                         #include "{}"
                         ]],
            {
              i(1, "custom_insert.h"),
            }
          )
        ),
        sn(
          nil,
          fmt(
            [[
                         #include <{}>
                         ]],
            {
              i(1, "custom_system_insert.h"),
            }
          )
        ),
      }
      -- Add the custom insert_nodes for adding custom local (wrapped in "") or system (wrapped in <>) headers
      for _, custom_insert_node in ipairs(custom_insert_nodes) do
        table.insert(headers_to_load_into_choice_node, custom_insert_node)
      end

      -- Step 4: finally last priority is the system headers
      local system_headers = {
        t "#include <assert.h>",
        t "#include <complex.h>",
        t "#include <ctype.h>",
        t "#include <errno.h>",
        t "#include <fenv.h>",
        t "#include <float.h>",
        t "#include <inttypes.h>",
        t "#include <iso646.h>",
        t "#include <limits.h>",
        t "#include <locale.h>",
        t "#include <math.h>",
        t "#include <setjmp.h>",
        t "#include <signal.h>",
        t "#include <stdalign.h>",
        t "#include <stdarg.h>",
        t "#include <stdatomic.h>",
        t "#include <stdbit.h>",
        t "#include <stdbool.h>",
        t "#include <stdckdint.h>",
        t "#include <stddef.h>",
        t "#include <stdint.h>",
        t "#include <stdio.h>",
        t "#include <stdlib.h>",
        t "#include <stdnoreturn.h>",
        t "#include <string.h>",
        t "#include <tgmath.h>",
        t "#include <threads.h>",
        t "#include <time.h>",
        t "#include <uchar.h>",
        t "#include <wchar.h>",
        t "#include <wctype.h>",
      }
      for _, header_snippet in ipairs(system_headers) do
        table.insert(headers_to_load_into_choice_node, header_snippet)
      end

      return sn(1, c(1, headers_to_load_into_choice_node))
    end, {}),
  }),
}
