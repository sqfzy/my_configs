local ls = require "luasnip"
local s = ls.snippet
local t = ls.text_node -- 文本节点
local fmt = require("luasnip.extras.fmt").fmt

return {
  s({ trig = "tail", dscr = "tailwindcss" }, {
    t { "@tailwind base;" },
    t { "", "@tailwind components;" },
    t { "", "@tailwind utilities;" },
  }),
  s(
    { trig = "reset", dscr = "默认修改样式" },
    fmt(
      [[
* {{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}}
li {{
  list-style: none;
}}
a {{
  text-decoration: none;
}}
.header {{
  background-color: #333333;
}}
.header li a {{
  color: #a7a7a7;
}}
table {{
  border-collapse: collapse;
  border-spacing: 0;
}}

  ]],
      {}
    )
  ),
  s("flex-center", {
    t { "justify-content: center;" },
    t { "", "align-items: center;" },
  }),
  s("text-center", {
    t { "text-align: center;" },
    t { "", "line-height: 1.5;" },
  }),
}
