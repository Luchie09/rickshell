"""Basic file and directory commands for the shell."""

import errno
import os
import shutil
from typing import TextIO

from shell.builtins import register
from shell.context import ShellContext


def resolve(ctx: ShellContext, path: str) -> str:
    """Resolve a path against the shell's working directory."""
    if os.path.isabs(path):
        return os.path.abspath(os.path.normpath(path))
    return os.path.abspath(os.path.normpath(os.path.join(ctx.cwd, path)))


def _reason(error: OSError) -> str:
    standard_reasons = {
        errno.EEXIST: "File exists",
        errno.ENOENT: "No such file or directory",
        errno.ENOTDIR: "Not a directory",
        errno.EISDIR: "Is a directory",
        errno.ENOTEMPTY: "Directory not empty",
        errno.EACCES: "Permission denied",
    }
    if error.errno in standard_reasons:
        return standard_reasons[error.errno]
    return error.strerror or str(error)


def _error(stderr: TextIO, command: str, path: str, reason: str) -> None:
    print(f"{command}: {path}: {reason}", file=stderr)


def _os_error(stderr: TextIO, command: str, path: str, error: OSError) -> None:
    _error(stderr, command, path, _reason(error))


def _missing_operand(stderr: TextIO, command: str) -> int:
    print(f"{command}: missing operand", file=stderr)
    return 2


def _is_terminal(stdout: TextIO) -> bool:
    """Check whether colored, column-formatted output is appropriate."""
    try:
        return stdout.isatty()
    except (AttributeError, OSError):
        return False


def _color_name(name: str, is_directory: bool, use_color: bool) -> str:
    if use_color and is_directory:
        return f"\x1b[1;34m{name}\x1b[0m"
    return name


def _write_columns(names: list[tuple[str, bool]], stdout: TextIO) -> None:
    """Write entries down as many terminal columns as will fit."""
    if not names:
        return

    width = shutil.get_terminal_size(fallback=(80, 24)).columns
    if max(len(name) for name, _ in names) > width:
        for name, is_directory in names:
            print(_color_name(name, is_directory, True), file=stdout)
        return

    chosen_columns = [names]
    chosen_widths = [max(len(name) for name, _ in names)]
    for column_count in range(len(names), 1, -1):
        short_column_size, taller_columns = divmod(len(names), column_count)
        columns = []
        start = 0
        for column_index in range(column_count):
            column_size = short_column_size + (
                1 if column_index < taller_columns else 0
            )
            if column_size:
                columns.append(names[start : start + column_size])
                start += column_size
        column_widths = [
            max(len(name) for name, _ in column)
            for column in columns
        ]
        if sum(column_widths) + 2 * (len(columns) - 1) <= width:
            chosen_columns = columns
            chosen_widths = column_widths
            break

    row_count = max(len(column) for column in chosen_columns)
    for row in range(row_count):
        row_entries = [
            (column_index, column[row])
            for column_index, column in enumerate(chosen_columns)
            if row < len(column)
        ]
        pieces: list[str] = []
        for entry_index, (column_index, entry) in enumerate(row_entries):
            name, is_directory = entry
            rendered = _color_name(name, is_directory, True)
            if entry_index < len(row_entries) - 1:
                rendered += " " * (
                    chosen_widths[column_index] - len(name) + 2
                )
            pieces.append(rendered)
        print("".join(pieces), file=stdout)


def _parse_ls_args(
    args: list[str],
    stderr: TextIO,
) -> tuple[bool, bool, bool, list[str]] | None:
    """Read ls flags and paths, reporting an unsupported flag immediately."""
    show_hidden = False
    long_format = False
    recursive = False
    paths: list[str] = []
    for arg in args:
        if arg.startswith("-") and arg != "-":
            for option in arg[1:]:
                if option == "a":
                    show_hidden = True
                elif option == "l":
                    long_format = True
                elif option == "R":
                    recursive = True
                else:
                    print(f"ls: invalid option -- '{option}'", file=stderr)
                    return None
        else:
            paths.append(arg)
    return show_hidden, long_format, recursive, paths


def _display_path(path: str) -> str:
    """Format recursive headers with forward slashes on every platform."""
    display_path = path.replace("\\", "/")
    if len(display_path) > 1 and display_path.endswith("/") and not (
        len(display_path) == 3 and display_path[1] == ":"
    ):
        display_path = display_path.rstrip("/")
    return display_path or "/"


def _directory_entries(
    abs_path: str,
    show_hidden: bool,
) -> list[tuple[str, str]]:
    names = sorted(os.listdir(abs_path))
    if not show_hidden:
        names = [name for name in names if not name.startswith(".")]

    entries = [(name, os.path.join(abs_path, name)) for name in names]
    if show_hidden:
        parent = os.path.dirname(os.path.abspath(abs_path)) or abs_path
        if parent == os.path.abspath(abs_path):
            parent = abs_path
        entries = [(".", abs_path), ("..", parent)] + entries
    return entries


def _entry_size(abs_path: str) -> int:
    return 4096 if os.path.isdir(abs_path) else os.path.getsize(abs_path)


def _total_blocks(entries: list[tuple[str, str]]) -> int:
    blocks = 0
    for _, abs_path in entries:
        size = _entry_size(abs_path)
        blocks += ((size + 4095) // 4096) * 4
    return blocks


def _write_listing(
    entries: list[tuple[str, str]],
    ctx: ShellContext,
    stdout: TextIO,
    long_format: bool,
    use_color: bool,
    directory_listing: bool,
) -> None:
    from shell.builtins.perms import format_long_rows

    if long_format:
        if directory_listing:
            print(f"total {_total_blocks(entries)}", file=stdout)
        for line in format_long_rows(
            ctx,
            entries,
            use_color,
        ):
            print(line, file=stdout)
        return

    if use_color:
        _write_columns(
            [(name, os.path.isdir(abs_path)) for name, abs_path in entries],
            stdout,
        )
    else:
        for name, _ in entries:
            print(name, file=stdout)


def _permission_denied(stderr: TextIO, display_path: str) -> None:
    print(f"ls: {display_path}: Permission denied", file=stderr)


def _list_recursive(
    abs_path: str,
    display_path: str,
    ctx: ShellContext,
    stdout: TextIO,
    stderr: TextIO,
    show_hidden: bool,
    long_format: bool,
    use_color: bool,
    state: dict[str, int],
) -> bool:
    """List a directory, then recursively visit its child directories."""
    try:
        entries = _directory_entries(abs_path, show_hidden)
    except OSError:
        _permission_denied(stderr, display_path)
        return True

    if state["listings"]:
        print(file=stdout)
    print(f"{display_path}:", file=stdout)
    state["listings"] += 1
    _write_listing(
        entries,
        ctx,
        stdout,
        long_format,
        use_color,
        True,
    )

    failed = False
    for name, child_path in entries:
        if name in (".", "..") or not os.path.isdir(child_path):
            continue
        if os.path.islink(child_path):
            continue
        if name.startswith(".") and not show_hidden:
            continue
        child_display = f"{display_path.rstrip('/')}/{name}"
        if _list_recursive(
            child_path,
            child_display,
            ctx,
            stdout,
            stderr,
            show_hidden,
            long_format,
            use_color,
            state,
        ):
            failed = True
    return failed


def _drop_permissions(ctx: ShellContext, abs_path: str) -> None:
    """Remove stored permissions for a path and any paths below it."""
    prefix = abs_path + os.sep
    for saved_path in list(ctx.permissions):
        if saved_path == abs_path or saved_path.startswith(prefix):
            del ctx.permissions[saved_path]


def _move_permissions(ctx: ShellContext, source: str, destination: str) -> None:
    """Move simulated modes along with a successfully moved path."""
    prefix = source + os.sep
    moved_modes = []
    for saved_path, mode in list(ctx.permissions.items()):
        if saved_path == source:
            moved_modes.append((saved_path, destination, mode))
        elif saved_path.startswith(prefix):
            suffix = saved_path[len(prefix):]
            moved_modes.append((saved_path, os.path.join(destination, suffix), mode))

    for old_path, _, _ in moved_modes:
        del ctx.permissions[old_path]
    for _, new_path, mode in moved_modes:
        ctx.permissions[new_path] = mode


@register("pwd")
def pwd(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Print the shell's current directory."""
    print(ctx.cwd, file=stdout)
    return 0


@register("cd")
def cd(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Change the shell's current directory without changing process cwd."""
    if len(args) > 1:
        print("cd: too many arguments", file=stderr)
        return 2

    target = os.path.expanduser(args[0]) if args else os.path.expanduser("~")
    abs_path = resolve(ctx, target)
    if not os.path.exists(abs_path):
        _error(stderr, "cd", target, "No such file or directory")
        return 1
    if not os.path.isdir(abs_path):
        _error(stderr, "cd", target, "Not a directory")
        return 1

    ctx.cwd = abs_path
    return 0


@register("dir")
@register("ls")
def ls(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """List paths using plain, long, or recursive GNU-style output."""
    parsed = _parse_ls_args(args, stderr)
    if parsed is None:
        return 2
    show_hidden, long_format, recursive, paths = parsed
    no_path_was_given = not paths
    if no_path_was_given:
        paths = ["."]

    use_color = _is_terminal(stdout)
    file_entries: list[tuple[str, str]] = []
    directory_paths: list[tuple[str, str]] = []
    failed = False

    for path in paths:
        abs_path = resolve(ctx, path)
        if os.path.isdir(abs_path):
            directory_paths.append((path, abs_path))
        elif os.path.exists(abs_path):
            file_entries.append((os.path.basename(abs_path), abs_path))
        else:
            _error(stderr, "ls", path, "No such file or directory")
            failed = True

    if file_entries:
        _write_listing(
            file_entries,
            ctx,
            stdout,
            long_format,
            use_color,
            False,
        )

    if recursive:
        if file_entries and directory_paths:
            print(file=stdout)
        state = {"listings": 0}
        for display_path, abs_path in directory_paths:
            if _list_recursive(
                abs_path,
                _display_path(display_path),
                ctx,
                stdout,
                stderr,
                show_hidden,
                long_format,
                use_color,
                state,
            ):
                failed = True
        return 1 if failed else 0

    multi_path = len(paths) > 1
    previous_group = bool(file_entries)
    for display_path, abs_path in directory_paths:
        try:
            entries = _directory_entries(abs_path, show_hidden)
        except OSError:
            _permission_denied(stderr, display_path)
            failed = True
            continue

        if previous_group:
            print(file=stdout)
        if multi_path:
            print(f"{display_path}:", file=stdout)
        _write_listing(
            entries,
            ctx,
            stdout,
            long_format,
            use_color,
            True,
        )
        previous_group = True

    return 1 if failed else 0


@register("mkdir")
def mkdir(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Create each requested directory."""
    if not args:
        return _missing_operand(stderr, "mkdir")

    failed = False
    for path in args:
        try:
            os.mkdir(resolve(ctx, path))
        except OSError as error:
            _os_error(stderr, "mkdir", path, error)
            failed = True
    return 1 if failed else 0


@register("rmdir")
def rmdir(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Remove empty directories."""
    if not args:
        return _missing_operand(stderr, "rmdir")

    failed = False
    for path in args:
        try:
            os.rmdir(resolve(ctx, path))
            _drop_permissions(ctx, resolve(ctx, path))
        except OSError as error:
            _os_error(stderr, "rmdir", path, error)
            failed = True
    return 1 if failed else 0


@register("touch")
def touch(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Create each file or update its modification time."""
    if not args:
        return _missing_operand(stderr, "touch")

    failed = False
    for path in args:
        try:
            abs_path = resolve(ctx, path)
            with open(abs_path, "a"):
                pass
            os.utime(abs_path, None)
        except OSError as error:
            _os_error(stderr, "touch", path, error)
            failed = True
    return 1 if failed else 0


@register("cp")
def cp(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Copy one file, or recursively copy a directory when requested."""
    recursive = bool(args and args[0] == "-r")
    operands = args[1:] if recursive else args
    if len(operands) < 2:
        return _missing_operand(stderr, "cp")
    if len(operands) > 2:
        print("cp: usage: cp [-r] src dst", file=stderr)
        return 2

    source_name, destination_name = operands
    source = resolve(ctx, source_name)
    destination = resolve(ctx, destination_name)

    try:
        if not os.path.exists(source):
            _error(stderr, "cp", source_name, "No such file or directory")
            return 1
        if os.path.isdir(source) and not recursive:
            _error(stderr, "cp", source_name, "omitting directory")
            return 1

        if os.path.isdir(destination):
            destination = os.path.join(destination, os.path.basename(source))

        if os.path.isdir(source):
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        return 0
    except OSError as error:
        _os_error(stderr, "cp", destination_name, error)
        return 1


@register("mv")
def mv(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Move or rename one path and its simulated permissions."""
    if len(args) < 2:
        return _missing_operand(stderr, "mv")
    if len(args) > 2:
        print("mv: usage: mv src dst", file=stderr)
        return 2

    source_name, destination_name = args
    source = resolve(ctx, source_name)
    destination = resolve(ctx, destination_name)
    try:
        if not os.path.exists(source):
            _error(stderr, "mv", source_name, "No such file or directory")
            return 1
        if os.path.isdir(destination):
            destination = os.path.join(destination, os.path.basename(source))
        shutil.move(source, destination)
        _move_permissions(ctx, source, destination)
        return 0
    except OSError as error:
        _os_error(stderr, "mv", destination_name, error)
        return 1


@register("rm")
def rm(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Remove files, or directories when recursive mode is requested."""
    recursive = bool(args and args[0] == "-r")
    paths = args[1:] if recursive else args
    if not paths:
        return _missing_operand(stderr, "rm")

    failed = False
    for path in paths:
        abs_path = resolve(ctx, path)
        try:
            if os.path.isdir(abs_path) and not os.path.islink(abs_path):
                if not recursive:
                    _error(stderr, "rm", path, "Is a directory")
                    failed = True
                    continue
                shutil.rmtree(abs_path)
            else:
                os.remove(abs_path)
            _drop_permissions(ctx, abs_path)
        except OSError as error:
            _os_error(stderr, "rm", path, error)
            failed = True
    return 1 if failed else 0


@register("cat")
def cat(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Print files in order, or copy standard input when no files are given."""
    if not args:
        try:
            shutil.copyfileobj(stdin, stdout)
            return 0
        except OSError as error:
            _error(stderr, "cat", "stdin", _reason(error))
            return 1

    failed = False
    for path in args:
        try:
            with open(resolve(ctx, path), "r") as source:
                shutil.copyfileobj(source, stdout)
        except OSError as error:
            _os_error(stderr, "cat", path, error)
            failed = True
    return 1 if failed else 0
