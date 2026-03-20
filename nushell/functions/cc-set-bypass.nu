#!/usr/bin/env nu
#
# 用法：
#   nu cc-set-bypass.nu                        # 写入（默认 project scope）
#   nu cc-set-bypass.nu --scope user           # 写入 user scope
#   nu cc-set-bypass.nu --restore              # 还原备份
#   nu cc-set-bypass.nu --restore --scope user
#
# 作为模块导入：
#   use cc-set-bypass.nu *
#   cc-set-bypass apply
#   cc-set-bypass restore

const C_RST = "\e[0m"
const C_DIM = "\e[2m"
const C_GRN = "\e[32m"
const C_YLW = "\e[33m"

const BYPASS_SETTINGS = {
    defaultMode: "bypassPermissions"
    skipDangerousModePermissionPrompt: true
    permissions: {
        allow: [
            "Bash(*)", "Read(*)", "Write(*)", "Edit(*)", "MultiEdit(*)",
            "Glob(*)", "Grep(*)", "WebFetch(*)",
            "TodoRead", "TodoWrite", "NotebookRead", "NotebookEdit"
        ]
        deny: []
    }
}

def settings_path [scope: string] {
    if $scope == "user" {
        $"($env.HOME)/.claude/settings.json"
    } else {
        ".claude/settings.json"
    }
}

# 写入无限制 settings，返回备份路径（无备份则返回空串）
export def "cc-set-bypass apply" [--scope (-s): string = "project"] {
    let path = settings_path $scope
    let dir  = ($path | path dirname)

    if not ($dir | path exists) { mkdir $dir }

    let backup = if ($path | path exists) {
        let b = $"($path).bak"
        cp $path $b
        print $"($C_DIM)↳ 已备份 → ($b)($C_RST)"
        $b
    } else { "" }

    $BYPASS_SETTINGS | to json | save --force $path
    print $"($C_GRN)✔ 已写入无限制 settings.json → ($path)($C_RST)"
    $backup
}

# 还原备份；若无备份则删除 settings 文件
export def "cc-set-bypass restore" [--scope (-s): string = "project", --backup (-b): string = ""] {
    let path = settings_path $scope
    let bak  = if ($backup | str length) > 0 { $backup } else { $"($path).bak" }

    if ($bak | path exists) {
        mv --force $bak $path
        print $"($C_GRN)✔ 已还原 ($path)($C_RST)"
    } else if ($path | path exists) {
        rm $path
        print $"($C_YLW)⚠ 无备份可还原，已删除 ($path)($C_RST)"
    } else {
        print $"($C_DIM)  无需操作，文件不存在($C_RST)"
    }
}

# 直接执行入口
export def main [
    --restore (-r)
    --scope   (-s): string = "project"
    --backup  (-b): string = ""
] {
    if $restore {
        cc-set-bypass restore --scope $scope --backup $backup
    } else {
        cc-set-bypass apply --scope $scope
    }
}
