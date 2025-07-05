#!/usr/bin/env nu

# Converts Typst file formatting after pandoc conversion.
def convert_format [
    file_path: string # The path to the Typst file to format
] {
    # Check if file exists
    if not ($file_path | path exists) {
        error make { msg: $"Error: File '($file_path)' does not exist." }
    }

    # Read file content line by line
    let content_lines = open $file_path | lines

    # 1. Replace align(center) with align(left), only when #table( follows
    let processed_lines = $content_lines | each { |line|
        $line | str replace 'align(center)[#table' 'align(left)[#table'
    }

    # Join lines back to a single string for subsequent whole-content replacements
    mut content_string = $processed_lines | str join (char nl)

    # 2. Replace '-\n  <content>' or '-\n<content>' with '- <content>' (on new line)
    # Corresponds to: sed -i -z 's/-\n /\n-/g' $file
    # Corresponds to: sed -i -z 's/-\n/\n- /g' $file
    # The order can be important for these kinds of replacements.
    # First, "-\n " -> "\n-"
    $content_string = $content_string | str replace --all '-\n ' "\n-"
    # Second, "-\n" -> "\n- " (if not already handled by the first)
    $content_string = $content_string | str replace --all '-\n' "\n- "


    # 3. Replace ```c with ```C
    # Corresponds to: sed -i 's/```c/```C/g' $file
    $content_string = $content_string | str replace --all '```c' '```C'

    # 4. Replace '\(' with '\ ('
    # Corresponds to: sed -i 's/\\\(/\\\ (/g' $file
    # In Nushell strings, `\` is an escape. To match a literal `\(`, you need `'\\('`.
    # To replace with `\ (`, you need `'\\ ('`.
    $content_string = $content_string | str replace --all '\\(' '\\ ('

    # 5. Remove #none
    # Corresponds to: sed -i 's/#none//g' $file
    $content_string = $content_string | str replace --all '#none' ''

    # 6. Prepend header text
    # Corresponds to: sed -i '1i#import "@local/common:0.0.1": *\n#show: common.with()\n' $file
    let header = $"#import \"@local/common:0.0.1\": *\n#show: common.with\(\)\n\n"
    let final_content = $"($header)($content_string)"

    # Save the modified content back to the file
    $final_content | save --force $file_path
}

# Converts a Markdown file to Typst using pandoc and applies custom formatting.
#
# Usage:
#   pandocgpt                 # Converts ./bibliography/chatgpt.md by default
#   pandocgpt my_file.md      # Converts specified markdown file
export def main [
    input_file?: string, # The input Markdown file path (optional)
    ...rest: string      # Capture any additional arguments to check for incorrect usage
] {
    # Check for too many arguments
    if ($rest | is-not-empty) {
        print "Usage: pandocgpt [input_file]"
        error make { msg: "Too many arguments." } # Exits the script
    }

    # Determine input file: use default if not provided
    let actual_input_file = if ($input_file == null) {
        "./bibliography/chatgpt.md"
    } else {
        $input_file
    }

    # Check if input file exists
    if not ($actual_input_file | path exists) {
        error make { msg: $"Error: Input file '($actual_input_file)' does not exist." }
    }

    # Determine output file path (e.g., input.md -> input.typ)
    let input_path_details = ($actual_input_file | path parse)
    let output_filename = $"($input_path_details.stem).typ"
    let output_file = [$input_path_details.parent $output_filename] | path join


    # Construct path to Lua filter
    let lua_filter_path = $env.HOME + "/.config/nushell/functions/pandocgpt_filter.lua"
    # A more Nushell-idiomatic way to join paths:
    # let lua_filter_path = [ (home) ".config" "fish" "functions" "pandocgpt_filter.lua" ] | path join

    # Check if Lua filter exists
    if not ($lua_filter_path | path exists) {
        print $"Warning: Lua filter not found at '($lua_filter_path)'. Pandoc will run without it."
    }

    # Use pandoc for conversion
    print $"Converting ($actual_input_file) with pandoc..."
    let pandoc_args = [
        $actual_input_file,
        "--from=markdown+tex_math_single_backslash",
        $"--lua-filter=($lua_filter_path)",
        "-o", $output_file
    ]
    match (^pandoc ...($pandoc_args)) {
        { exit_code: 0 } => { print "Pandoc conversion successful." },
        { exit_code: $code } => { error make { msg: $"Pandoc failed with exit code: ($code)" } }
    }

    # Apply custom formatting conversions
    convert_format $output_file

    print $"Successfully converted ($actual_input_file) to ($output_file)."
}
