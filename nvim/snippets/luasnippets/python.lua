local ls = require "luasnip"
local s = ls.snippet
local i = ls.insert_node
local t = ls.text_node
local c = ls.choice_node
local sn = ls.snippet_node
local isn = ls.indent_snippet_node
local fmt = require("luasnip.extras.fmt").fmt
local types = require "luasnip.util.types"
local d = ls.dynamic_node -- 与函数节点类似，但返回节点

local function node_with_virtual_text(pos, node, text)
  local nodes
  if node.type == types.textNode then
    node.pos = 2
    nodes = { i(1), node }
  else
    node.pos = 1
    nodes = { node }
  end
  return sn(pos, nodes, {
    node_ext_opts = {
      active = {
        -- override highlight here ("GruvboxOrange").
        virt_text = { { text, "GruvboxOrange" } },
      },
    },
  })
end

local function nodes_with_virtual_text(nodes, opts)
  if opts == nil then opts = {} end
  local new_nodes = {}
  for pos, node in ipairs(nodes) do
    if opts.texts[pos] ~= nil then node = node_with_virtual_text(pos, node, opts.texts[pos]) end
    table.insert(new_nodes, node)
  end
  return new_nodes
end

local function choice_text_node(pos, choices, opts)
  choices = nodes_with_virtual_text(choices, opts)
  return c(pos, choices, opts)
end

local ct = choice_text_node

return {
  s("!", t "test"),
  s(
    { trig = "for([%d_]+)", regTrig = true },
    fmt(
      [[
for i in range({}):
  {}
  ]],
      {
        d(1, function(_, snip)
          -- captures[1],获取正则()中的字符作为insert节点的文本
          return sn(1, t(snip.captures[1]))
        end),
        i(2),
      }
    )
  ),
}
