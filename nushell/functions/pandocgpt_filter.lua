local typst_break = pandoc.RawInline("typst", "\n")

function RawInline(el)
	-- 将 <br> 替换为换行
	if el.format:match("html") and el.text:lower():match("<br ?/?>") then
		return typst_break
	end
end

-- 将"[-"替换为"[\n-"
function Table(el)
	-- 遍历表格的所有单元格内容
	el = pandoc.walk_block(el, {
		Plain = function(pl)
			-- 仅在 inside_table 为 true 时处理
			local first = pl.content[1]
			if first and first.t == "Str" and first.text == "-" then
				-- 在内容首部插入 Typst 的换行符 RawInline
				table.insert(pl.content, 1, typst_break)
			end
			return pl
		end,
	})

	return el
end

-- 将标题中的序号去掉
function Header(el)
	-- 用于去掉紧跟序号后的空格
	local should_remove_space = false

	function trim_number(el)
		if el.text then
			-- 去掉"1." "1.1." "一、" "(1)" "(2)"等序号
			el.text = el.text:gsub("^%d[%d%.]*", ""):gsub("^[%d一二三四五六七八九十百千]+、", ""):gsub("^%(%d+%)", ""):gsub("^%（%d+%）", "")

			if el.text == "" then
				should_remove_space = true
			end
		end

		return el
	end

	return el:walk({
		Str = trim_number,
		Strong = trim_number,
		Space = function(el)
			if should_remove_space then
				should_remove_space = false
				return {}
			else
				return el
			end
		end,
	})
end
