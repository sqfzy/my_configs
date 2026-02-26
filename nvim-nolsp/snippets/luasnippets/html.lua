local ls = require "luasnip"
local s = ls.snippet
local sn = ls.snippet_node -- 只用来包含其它节点，可用于dynamic_node返回
local isn = ls.indent_snippet_node
local t = ls.text_node -- 文本节点
local i = ls.insert_node -- 插入节点
local f = ls.function_node -- 返回字符串
local c = ls.choice_node -- 可变的节点
local d = ls.dynamic_node -- 与函数节点类似，但返回节点
local r = ls.restore_node
local events = require "luasnip.util.events"
local ai = require "luasnip.nodes.absolute_indexer"
local extras = require "luasnip.extras"
local l = extras.lambda
local rep = extras.rep
local p = extras.partial
local m = extras.match
local n = extras.nonempty
local dl = extras.dynamic_lambda
local fmt = require("luasnip.extras.fmt").fmt
local fmta = require("luasnip.extras.fmt").fmta
local conds = require "luasnip.extras.expand_conditions"
local postfix = require("luasnip.extras.postfix").postfix
local types = require "luasnip.util.types"
local parse = require("luasnip.util.parser").parse_snippet
local ms = ls.multi_snippet

return {
  s("!", {
    t { "<!DOCTYPE html>" },
    t { "", '<html lang="zn">' },
    t { "", "", "<head>" }, --""转行
    t { "", '  <meta charset = "UTF-8">' },
    t {
      "",
      '  <meta name="viewport" content="width=device-width, initial-csale=1, maximum-scale=1, user-scalable=no">',
    },
    t { "", "</head>" },
    t { "", "", "<body>" },
    t { "", "", "  " },
    i(1),
    t { "", "", "</body>" },
    t { "", "", "</html>" },
  }),

  s("$", {
    t '$("',
    i(1),
    t '")',
  }),

  s("lin", { t '<link rel="stylesheet" href="', i(1), t '"/>' }),
}
