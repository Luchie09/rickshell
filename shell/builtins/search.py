"""Plain-text search commands."""

import os
import re
from typing import TextIO

from shell.builtins import register
from shell.context import ShellContext

USAGE = "usage: grep [-i] [-n] PATTERN [file...]"


def _read_stream(
    stream: TextIO,
    pattern: str,
    ignore_case: bool,
    show_line_numbers: bool,
    regex: re.Pattern[str] | None,
    show_groups: bool,
    filename: str | None,
    multiple_files: bool,
    stdout: TextIO,
) -> tuple[bool, Exception | None]:
    """Write matching lines and return whether any matched or errored."""
    matched = False

    try:
        for line_number, line in enumerate(stream, start=1):
            found = regex.search(line) if regex is not None else None
            if regex is not None and found is None:
                continue
            if regex is None:
                comparison_pattern = pattern.lower() if ignore_case else pattern
                comparison_line = line.lower() if ignore_case else line
                if comparison_pattern not in comparison_line:
                    continue

            prefix = ""
            if multiple_files and filename is not None:
                prefix += f"{filename}:"
            if show_line_numbers:
                prefix += f"{line_number}:"

            # Remove only the final newline; print adds exactly one newline back.
            if line.endswith("\n"):
                line = line[:-1]
            print(f"{prefix}{line}", file=stdout)
            if show_groups and found is not None and found.groups():
                groups = "  ".join(
                    f"{group_index}={found.group(group_index) or ''}"
                    for group_index in range(1, len(found.groups()) + 1)
                )
                print(f"  groups: {groups}", file=stdout)
            matched = True
    except Exception as error:
        return matched, error

    return matched, None


def _error_reason(error: OSError) -> str:
    if isinstance(error, FileNotFoundError):
        return "No such file or directory"
    return error.strerror or str(error)


def _report_error(stderr: TextIO, filename: str, error: Exception) -> None:
    if isinstance(error, OSError):
        reason = _error_reason(error)
    else:
        reason = str(error) or "input error"
    print(f"grep: {filename}: {reason}", file=stderr)


@register("grep")
def cmd_grep(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Print lines containing a plain-text pattern."""
    ignore_case = False
    show_line_numbers = False
    extended_regex = False
    show_groups = False
    index = 0
    positional: list[str] = []

    while index < len(args):
        flag_word = args[index]
        if flag_word == "-E":
            extended_regex = True
        elif flag_word == "--groups":
            extended_regex = True
            show_groups = True
        elif flag_word.startswith("-") and flag_word != "-":
            for flag in flag_word[1:]:
                if flag == "i":
                    ignore_case = True
                elif flag == "n":
                    show_line_numbers = True
                else:
                    print(f"grep: invalid option -- '{flag}'", file=stderr)
                    return 2
        elif flag_word == "-":
            print("grep: invalid option -- '-'", file=stderr)
            return 2
        else:
            positional.append(flag_word)
        index += 1

    if not positional:
        print(USAGE, file=stderr)
        return 2

    pattern = positional[0]
    filenames = positional[1:]
    regex: re.Pattern[str] | None = None
    if extended_regex:
        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as error:
            print(f"grep: invalid pattern: {error}", file=stderr)
            return 2

    matched = False
    failed = False

    if not filenames:
        matched, failed = _read_stream(
            stdin,
            pattern,
            ignore_case,
            show_line_numbers,
            regex,
            show_groups,
            None,
            False,
            stdout,
        )
        if failed is not None:
            _report_error(stderr, "stdin", failed)
            return 2
        return 0 if matched else 1

    multiple_files = len(filenames) > 1
    for filename in filenames:
        path = os.path.join(ctx.cwd, filename)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as source:
                file_matched, read_error = _read_stream(
                    source,
                    pattern,
                    ignore_case,
                    show_line_numbers,
                    regex,
                    show_groups,
                    filename,
                    multiple_files,
                    stdout,
                )
                matched = matched or file_matched
                if read_error is not None:
                    _report_error(stderr, filename, read_error)
                    failed = True
        except OSError as error:
            print(
                f"grep: {filename}: {_error_reason(error)}",
                file=stderr,
            )
            failed = True
        except Exception as error:
            _report_error(stderr, filename, error)
            failed = True

    if failed:
        return 2
    return 0 if matched else 1
