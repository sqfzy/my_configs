function gitpush --description 'Commit all changes and push the current branch to origin'
    command git add .
    or return $status

    command git commit --message update
    or return $status

    set --local current_branch (command git branch --show-current)
    or return $status

    if test -z "$current_branch"
        printf 'gitpush: HEAD is detached; no current branch to push\n' >&2
        return 1
    end

    command git push origin "$current_branch"
end
