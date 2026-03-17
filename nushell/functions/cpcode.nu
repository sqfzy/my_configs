
#!/usr/bin/env nu
# cpcode
# 将项目代码复制到新目录，排除隐藏文件，尊重 .gitignore
#
# 用法:
#   cpcode                        # src=当前目录, dst=../$(dirname)-arch
#   cpcode <src_dir>              # dst=<src_dir>-arch（同级）
#   cpcode <src_dir> <dst_dir>    # 完全手动指定
#   cpcode --dry-run              # 仅预览，不写入
#   cpcode --log-level debug

# 顶层日志函数，避免在内层 def 中捕获外部变量
def cpcode-log [level: string, msg: string, current_level: int, indent: bool = false] {
    let levels = {error: 0, warn: 1, info: 2, debug: 3, trace: 4}
    let lvl_num = ($levels | get -o $level | default 2)
    if $lvl_num <= $current_level {
        let prefix = match $level {
            "error" => $"(ansi red_bold)[ERROR](ansi reset)",
            "warn"  => $"(ansi yellow_bold)[WARN](ansi reset) ",
            "info"  => $"(ansi green_bold)[INFO](ansi reset) ",
            "debug" => $"(ansi cyan_bold)[DEBUG](ansi reset)",
            "trace" => $"(ansi purple_bold)[TRACE](ansi reset)",
            _       => "[LOG]  "
        }
        let pad = if $indent { "  " } else { "" }
        print $"($pad)($prefix) ($msg)"
    }
}

# 递归列出目录中所有非隐藏文件，返回相对于 base 的路径列表
def cpcode-list-files [base: string, current: string] {
    ls $current
    | where { |it| not ($it.name | path basename | str starts-with ".") }
    | each { |it|
        if $it.type == "dir" {
            cpcode-list-files $base $it.name
        } else {
            $it.name | str replace $"($base)/" ""
        }
    }
    | flatten
}

# 复制单个项目目录到目标，尊重 .gitignore 并排除隐藏文件
def cpcode-copy-project [src: string, dst: string, dry_run: bool, current_level: int] {
    let is_git_repo = ($src | path join ".git" | path exists)

    let files = if $is_git_repo {
        cpcode-log debug $"Git 仓库，使用 git ls-files: ($src)" $current_level true
        let raw = (do { git -C $src ls-files --cached --others --exclude-standard } | complete)
        if $raw.exit_code != 0 {
            cpcode-log warn $"git ls-files 失败，回退到全量扫描 exit_code=($raw.exit_code)" $current_level true
            cpcode-list-files $src $src
        } else {
            $raw.stdout
            | lines
            | where { |f| ($f | str trim) != "" }
            | where { |f|
                not ($f | split row "/" | any { |seg| $seg | str starts-with "." })
            }
        }
    } else {
        cpcode-log debug $"非 Git 仓库，递归扫描非隐藏文件: ($src)" $current_level true
        cpcode-list-files $src $src
    }

    let total = ($files | length)
    cpcode-log info $"共 ($total) 个文件 → ($dst)" $current_level true

    if $total == 0 {
        cpcode-log warn "没有需要复制的文件，跳过" $current_level true
        return
    }

    for rel in $files {
        let src_file   = ($src | path join $rel)
        let dst_file   = ($dst | path join $rel)
        let dst_parent = ($dst_file | path dirname)

        cpcode-log trace $"复制: ($rel)" $current_level true

        if not $dry_run {
            if not ($dst_parent | path exists) {
                mkdir $dst_parent
            }
            try {
                cp $src_file $dst_file
            } catch { |e|
                cpcode-log error $"复制失败 [($rel)]: ($e.msg)" $current_level true
            }
        }
    }

    if $dry_run {
        cpcode-log info "[dry-run] 以上文件未实际写入" $current_level true
    } else {
        cpcode-log info $"完成: ($dst)" $current_level true
    }
}

export def main [
    src_dir?: string,             # 源目录，默认为当前目录
    dst_dir?: string,             # 目标目录，默认为 <src>-arch（同级）
    --dry-run (-n),               # 仅打印，不实际复制
    --log-level: string = "info"  # 日志级别: error/warn/info/debug/trace
] {
    let levels = {error: 0, warn: 1, info: 2, debug: 3, trace: 4}
    let current_level = ($levels | get -o $log_level | default 2)

    # ---------- 检查依赖 ----------
    if (which git | is-empty) {
        cpcode-log error "未找到 git 命令，无法解析 .gitignore，请安装 git" $current_level
        exit 1
    }

    # ---------- 解析源目录 ----------
    let src = if $src_dir == null {
        (pwd)
    } else {
        ($src_dir | path expand)
    }

    if not ($src | path exists) {
        cpcode-log error $"源目录不存在: ($src)" $current_level
        exit 1
    }
    if not (($src | path type) == "dir") {
        cpcode-log error $"源路径不是目录: ($src)" $current_level
        exit 1
    }

    # ---------- 解析目标目录 ----------
    let dst = if $dst_dir == null {
        let src_name = ($src | path basename)
        let parent   = ($src | path dirname)
        ($parent | path join $"($src_name)-arch")
    } else {
        ($dst_dir | path expand)
    }

    # 防止目标是源的子目录
    if ($dst | str starts-with $"($src)/") {
        cpcode-log error $"目标目录不能是源目录的子目录: ($dst)" $current_level
        exit 1
    }

    cpcode-log info $"源目录: ($src)" $current_level
    cpcode-log info $"目标目录: ($dst)" $current_level
    if $dry_run { cpcode-log warn "dry-run 模式：不会写入任何文件" $current_level }

    # ---------- 创建目标根目录 ----------
    if not $dry_run {
        if not ($dst | path exists) {
            cpcode-log debug $"创建目标目录: ($dst)" $current_level
            mkdir $dst
        }
    }

    # ---------- 枚举顶层子目录 ----------
    let projects = (
        ls $src
        | where type == "dir"
        | where { |it| not ($it.name | path basename | str starts-with ".") }
    )

    if ($projects | is-empty) {
        cpcode-log debug "源目录下无子目录，将源目录本身作为单个项目处理" $current_level
        cpcode-copy-project $src $dst $dry_run $current_level
    } else {
        cpcode-log info $"发现 ($projects | length) 个项目" $current_level
        for proj in $projects {
            let proj_name = ($proj.name | path basename)
            let proj_dst  = ($dst | path join $proj_name)
            cpcode-log info $"处理项目: ($proj_name)" $current_level
            cpcode-copy-project $proj.name $proj_dst $dry_run $current_level
        }
    }

    cpcode-log info "全部完成" $current_level
}
