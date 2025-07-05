# 搜索linux头文件中的声明
export def main [
  pattern: string,
  --fuzzy(-f),
] {
  let pattern1 = if $fuzzy {
    $' \w*($pattern)\w* \{'
  } else {
    $' ($pattern) \{.*?^\}'
  } 
  let pattern2 = if $fuzzy {
    ' \w*' + $pattern + '\w*\('
  } else {
    ' ' + $pattern + '\(.*?\);'
  }

  mut args  = [
    "--type", "c",
    "--multiline",
    "--multiline-dotall",
    "--no-filename",
    "--json"
  ]

  let matches = rg ...$args $'($pattern1)|($pattern2)' $env.BPFTRACE_KERNEL_SOURCE  
    | lines 
    | each {|it| $it | from json } 
    | where type == "match" 

  for $match in $matches {
    let file_name = $match | get data.path.text
    let text = $match | get data.lines.text
    $text | bat --paging=never -l c --file-name $file_name
  }
}
