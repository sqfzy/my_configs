function __noxe_log --argument-names level message
    set --local configured_level (string lower -- "$NOXE_LOG_LEVEL")

    switch "$configured_level:$level"
        case 'debug:*' 'info:info' 'info:error' 'error:error'
            printf '[noxe] %s: %s\n' (string upper -- "$level") "$message" >&2
    end
end

function __noxe_validate_topic --argument-names topic
    if test -z "$topic"
        __noxe_log error 'topic must not be empty'
        return 2
    end

    if string match --quiet --regex '[[:cntrl:]/]' -- "$topic"
        __noxe_log error 'topic must not contain control characters or /'
        return 2
    end
end

function __noxe_escape_yaml_string --argument-names value
    set value (string replace --all "\\" "\\\\" -- "$value")
    string replace --all "\"" "\\\"" -- "$value"
end

function __noxe_write_diary --argument-names file_path title author timestamp
    set --local escaped_title (__noxe_escape_yaml_string "$title")
    set --local escaped_author (__noxe_escape_yaml_string "$author")

    printf '%s\n' \
        '---' \
        "title: \"$escaped_title\"" \
        "author: \"$escaped_author\"" \
        "date: \"$timestamp\"" \
        '---' \
        '' >?"$file_path"
end

function __noxe_print_help
    printf '%s\n' \
        'Usage: noxe [--help] [--] [TOPIC ...]' \
        '' \
        'Create a dated Markdown diary and open it in $EDITOR.' \
        'When TOPIC is omitted, noxe prompts for it.' \
        '' \
        'Configuration:' \
        '  NOXE_DIARY_DIR  Diary directory (default: $HOME/work_space/my_notes/Diary)' \
        '  NOXE_AUTHOR     Front-matter author (default: git config user.name)' \
        '  NOXE_LOG_LEVEL  error, info, or debug (default: info)' \
        '  EDITOR          Editor executable (default: nvim)'
end

function noxe --description 'Create and open a dated Markdown diary'
    set --local diary_directory "$HOME/work_space/my_notes/Diary"
    set --local log_level info
    set --local editor nvim

    set --query NOXE_DIARY_DIR; and set diary_directory "$NOXE_DIARY_DIR"
    set --query NOXE_LOG_LEVEL; and set log_level (string lower -- "$NOXE_LOG_LEVEL")
    set --query EDITOR; and test -n "$EDITOR"; and set editor "$EDITOR"
    set --local --export NOXE_LOG_LEVEL "$log_level"

    if not contains -- "$log_level" error info debug
        printf '[noxe] ERROR: NOXE_LOG_LEVEL must be error, info, or debug\n' >&2
        return 2
    end

    if test (count $argv) -gt 0; and contains -- "$argv[1]" -h --help
        __noxe_print_help
        return 0
    end

    if test (count $argv) -gt 0; and test "$argv[1]" = --
        set --erase argv[1]
    else if test (count $argv) -gt 0; and string match --quiet -- '-*' "$argv[1]"
        __noxe_log error "unknown option: $argv[1] (use -- before a topic beginning with -)"
        return 2
    end

    if not test -d "$diary_directory"
        __noxe_log error "diary directory does not exist: $diary_directory"
        return 2
    end
    if not test -w "$diary_directory"
        __noxe_log error "diary directory is not writable: $diary_directory"
        return 2
    end

    set --local topic
    if test (count $argv) -gt 0
        set topic (string join ' ' -- $argv | string trim)
    else
        read --prompt-str 'Diary topic: ' topic
        or begin
            __noxe_log error 'failed to read topic'
            return 2
        end
        set topic (string trim -- "$topic")
    end

    __noxe_validate_topic "$topic"; or return $status

    set --local author
    if set --query NOXE_AUTHOR; and test -n "$NOXE_AUTHOR"
        set author "$NOXE_AUTHOR"
    else
        set author (command git -C "$diary_directory" config user.name 2>/dev/null)
    end
    if test -z "$author"
        __noxe_log error 'author is empty; set NOXE_AUTHOR or git config user.name'
        return 2
    end

    set --local date_prefix (command date '+%Y-%m-%d')
    set --local timestamp (command date '+%Y-%m-%d %H:%M:%S')
    set --local title "$date_prefix $topic"
    set --local file_path "$diary_directory/$title.md"

    __noxe_log debug "creating diary: $file_path"
    if not __noxe_write_diary "$file_path" "$title" "$author" "$timestamp"
        if test -e "$file_path"
            __noxe_log error "diary already exists: $file_path"
        else
            __noxe_log error "failed to create diary: $file_path"
        end
        return 1
    end

    __noxe_log info "created diary: $file_path"
    __noxe_log debug "opening editor: $editor"
    command "$editor" "$file_path"
    set --local editor_status $status
    if test $editor_status -ne 0
        __noxe_log error "editor failed; diary retained at: $file_path"
        return $editor_status
    end

    __noxe_log debug "completed diary creation: $file_path"
end
