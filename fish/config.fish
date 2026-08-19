fish_add_path --global --move \
    "$HOME/.local/bin" \
    /opt/homebrew/bin \
    /opt/homebrew/sbin

if status is-interactive
    starship init fish | source
end
