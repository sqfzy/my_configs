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
  s({
    trig = "debug(%d)(%s)",
    regTrig = true,
    snippetType = "autosnippet",
  }, {
    f(function(args, snip) return 'std::println("debug' .. snip.captures[1] .. '\\n");' end, {}),
  }),
}
