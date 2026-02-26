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
  s(
    { trig = "pcall", dscr = "pcall for require" },
    fmt(
      [[
local ok, {} = pcall(require, "{}")
if not ok then
	vim.notify('"plugin-config/{}.lua:" cannot require {}')
	return
end
  ]],
      {
        i(1, "plugin"),
        i(2, "plugin"),
        rep(2),
        rep(2),
      }
    )
  ),
  s("foo(%w)", { t "foofoo" }, { snippetType = "autosnippet", regTrig = true }),
}

-- t表示最简单的文本
-- i的文本是自动选中的可方便修改
-- f代表函数

-- trig自动补全后可以通过<A-n>和<A-p>选择不同的补全
-- return {
-- 	s(
-- 		{trig = "trig", dscr = "描述", hidden = true}, -- hidden,cmp中隐藏
-- 		c(1, {
-- 			t("Ugh boring, a text node"),
-- 			i(nil, "At least I can edit something now..."),
-- 			f(function(args)
-- 				return "Still only counts as text!!"
-- 			end, {}),
-- 		})
-- 	),
-- }
--
-- t和i混用时需要sn
-- s(
-- 	{ trig = "va_arg", dscr = "使用列表中的下一个参数,默认参数类型为int" },
-- 	sn(1, {
-- 		t("va_arg(valist,"),
-- 		i(1, "int"),
-- 		t(")"),
-- 	})
-- ),

-- {}代表节点
-- s(
-- 	"trig",
-- 	fmt(
-- 		[[
--    local {} = function({})
-- {}  {{大括号转义}}
--    end
--    ]],
-- 		{
-- i(1, "my_fun"),
-- i(2, "my_arg"),
-- i(3, "my_code"),
-- 		}
-- 	)
-- ),

--自动展开
-- s({ trig = "test", snippetType = "autosnippet" }, t("this is a autosnippet")),
-- 带正则的自动展开
-- s({ trig = "test%d", snippetType = "autosnippet", regTrig = true }, t("this is a auto regex text")),

-- 函数节点
-- s({ trig = "test" }, {
-- 	i(1, "this is 1"),
-- 	f(function(arg)
-- 		return arg[2][1]     -- arg[2]代表节点i2，arg[2][1]代表i2的内容(i2没有内嵌其它节点)
-- 	end,
-- 	{ 1, 2 },  -- {1, 2}代表节点i1,i2
--  { user_args = { '"plugin"' } },  -- user_args代表custom文本
-- 	),
-- 	i(2, "this is 2"),
-- }),

-- 重复节点,相当于在不同的地方设置相同的节点，并且节点可以同时操作
-- s({ trig = "test" }, {
-- 	i(1, "this is 1"),
--  rep(1),
-- }),
--
-- 设置显示的条件
-- s({ trig = "abc" }, t("aaa"), {
-- 	show_condition = function(cursor)
-- 		if cursor:match("test") then
-- 			return true
-- 		end
-- 		return false
-- 	end,
-- }),
--
-- 后缀，text.br -> [text]
-- postfix(".br", {
-- 	f(function(_, parent)
-- 		return "[" .. parent.snippet.env.POSTFIX_MATCH .. "]"
-- 	end, {}),
-- }),
