# config.nu
#
# Installed by:
# version = "0.104.1"
#
# This file is used to override default Nushell settings, define
# (or import) custom commands, or run any other startup tasks.
# See https://www.nushell.sh/book/configuration.html
#
# This file is loaded after env.nu and before login.nu
#
# You can open this file in your default editor using:
# config nu
#
# See `help config nu` for more options
#
# You can remove these comments if you want or leave
# them for future reference.

# local function depending_on_appearance()
# 	local hr = tonumber(os.date("%H"))
# 	if 7 < hr and hr < 18 then -- 早上7点到下午6点之间为亮色模式
# 		return "light"
# 	else
# 		return "dark"
# 	end
# end

use ./functions/pandocgpt.nu 
use ./functions/gitpush.nu  
use ./functions/lh.nu  
source ./functions/autojump.nu

$env.config = {
    show_banner: false
}
# FIX: issue: https://github.com/nushell/nushell/issues/5585
$env.config.shell_integration.osc133 = false

# 主题设置
let hr = date now | format date '%H' | into int
if 7 < $hr and $hr < 18 {
    $env.THEME_MODE = "light"
    $env.STARSHIP_THEME = 'catppuccin_mocha'
} else {
    $env.THEME_MODE = "dark"
    $env.STARSHIP_THEME = 'catppuccin_latte'
}
mkdir ($nu.data-dir | path join "vendor/autoload")
starship init nu | save -f ($nu.data-dir | path join "vendor/autoload/starship.nu")

# 新增PATH
let new_paths = [
    $"($env.HOME)/.cargo/bin",
    $"($env.HOME)/.local/share/nvim/mason/bin",
    $"($env.HOME)/.local/bin"
]
for path_item in $new_paths {
    if not ($path_item in $env.PATH) {
        $env.PATH = ($env.PATH | prepend $path_item)
    }
}


# NOXE_* 变量
$env.NOXE_ROOT = $"($env.HOME)/work_space/notes"
$env.NOXE_AUTHOR = "sqfzy"
$env.NOXE_TYPE = "typ"
$env.NOXE_TEMPLATE = $"($env.NOXE_ROOT)/noxe_template.yml" # 使用 $env.NOXE_ROOT
$env.NOXE_EDIT = "nvim"

# 要使用外部命令 exa, bat, rg，需要用 `^` 符号
alias oldls = ^ls
alias ls = ^eza
alias oldcat = ^cat
alias cat = ^bat
alias oldgrep = ^grep
alias grep = ^rg
alias top = ^btop
alias objdump = ^llvm-objdump
alias readelf = ^llvm-readobj
alias readobj = ^llvm-readobj

# carapace: 自动补全工具
source ./carapace_init.nu

# pyenv configuration for Nushell
$env.PYENV_ROOT = ($env.HOME | path join ".pyenv")
$env.PATH = ($env.PATH | prepend $"($env.PYENV_ROOT)/shims")
$env.PYENV_SHELL = "nu"

# api key
# 保存在 $HOME/key/gemini_api_key
$env.GEMINI_API_KEY = ^cat $"($env.HOME)/key/gemini_api_key" 

# bpftrace configuration
$env.BPFTRACE_KERNEL_SOURCE = $"/usr/src/((uname | get kernel-release))"
