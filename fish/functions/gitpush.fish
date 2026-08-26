function gitpush --description 'Commit all changes and push the current branch to origin'
    argparse no-verify -- $argv
    or return 2

    if test (count $argv) -ne 0
        printf 'gitpush: unexpected argument: %s\n' "$argv[1]" >&2
        return 2
    end

    set --local verify_option
    set --query _flag_no_verify; and set verify_option --no-verify

    command git add .
    or return $status

    command git commit $verify_option --message update
    or return $status

    set --local current_branch (command git branch --show-current)
    or return $status

    if test -z "$current_branch"
        printf 'gitpush: HEAD is detached; no current branch to push\n' >&2
        return 1
    end

    command git push $verify_option origin "$current_branch"
end
