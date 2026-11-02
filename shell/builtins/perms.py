"""Simulated file permissions for the shell."""

import getpass
import os
import re
from datetime import datetime, timedelta
from typing import TextIO

from shell.builtins import register
from shell.builtins.files import resolve
from shell.context import ShellContext

MODE_PATTERN = re.compile(r"^[0-7]{3,4}$")


def get_mode(ctx: ShellContext, abs_path: str) -> int:
    """Return a stored mode or the shell's default simulated mode."""
    if abs_path in ctx.permissions:
        return ctx.permissions[abs_path]
    if os.path.isdir(abs_path):
        return 0o755
    return 0o644


def _permission_text(mode: int, is_directory: bool) -> str:
    """Build the type and nine permission characters from mode bits."""
    permission_text = ""
    for shift in (6, 3, 0):
        permission_text += "r" if mode & (0o4 << shift) else "-"
        permission_text += "w" if mode & (0o2 << shift) else "-"
        permission_text += "x" if mode & (0o1 << shift) else "-"
    return ("d" if is_directory else "-") + permission_text


def _owner_name() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "user"


def _link_count(abs_path: str, is_directory: bool) -> int:
    if not is_directory:
        return 1
    try:
        subdirectories = sum(
            os.path.isdir(os.path.join(abs_path, name))
            for name in os.listdir(abs_path)
        )
        return 2 + subdirectories
    except OSError:
        return 2


def _display_date(abs_path: str) -> str:
    modified = datetime.fromtimestamp(os.path.getmtime(abs_path))
    now = datetime.now()
    month = (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    )[modified.month - 1]

    six_months_ago_month = now.month - 6
    six_months_ago_year = now.year
    if six_months_ago_month <= 0:
        six_months_ago_month += 12
        six_months_ago_year -= 1
    day = min(
        now.day,
        (
            datetime(
                six_months_ago_year,
                six_months_ago_month % 12 + 1,
                1,
            )
            - timedelta(days=1)
        ).day,
    )
    threshold = now.replace(
        year=six_months_ago_year,
        month=six_months_ago_month,
        day=day,
    )

    if threshold <= modified <= now:
        return f"{month} {modified.day:2} {modified:%H:%M}"
    return f"{month} {modified.day:2}  {modified.year:04}"


def format_long(
    ctx: ShellContext,
    abs_path: str,
    name: str | None = None,
    widths: tuple[int, int, int] | None = None,
    use_color: bool = False,
) -> str:
    """Format an aligned long-listing row using simulated permission bits."""
    mode = get_mode(ctx, abs_path)
    is_directory = os.path.isdir(abs_path)
    if name is None:
        name = os.path.basename(os.path.normpath(abs_path))

    owner = _owner_name()
    group = owner
    links = str(_link_count(abs_path, is_directory))
    size = 4096 if is_directory else os.path.getsize(abs_path)
    if widths is None:
        widths = (len(links), len(owner), len(group))
        size_width = len(str(size))
    else:
        size_width = widths[2]
        widths = (widths[0], widths[1], widths[1])

    link_width, owner_width, group_width = widths
    row_name = name
    if use_color and is_directory:
        row_name = f"\x1b[1;34m{name}\x1b[0m"

    return (
        f"{_permission_text(mode, is_directory)} "
        f"{links:>{link_width}} "
        f"{owner:<{owner_width}} "
        f"{group:<{group_width}} "
        f"{size:>{size_width}} "
        f"{_display_date(abs_path)} "
        f"{row_name}"
    )


def format_long_rows(
    ctx: ShellContext,
    entries: list[tuple[str, str]],
    use_color: bool = False,
) -> list[str]:
    """Format all entries in one directory with shared column widths."""
    owner = _owner_name()
    link_width = 1
    size_width = 1
    for _, abs_path in entries:
        is_directory = os.path.isdir(abs_path)
        link_width = max(
            link_width,
            len(str(_link_count(abs_path, is_directory))),
        )
        size = 4096 if is_directory else os.path.getsize(abs_path)
        size_width = max(size_width, len(str(size)))

    widths = (link_width, len(owner), size_width)
    return [
        format_long(ctx, abs_path, name, widths, use_color)
        for name, abs_path in entries
    ]


def _error_reason(error: OSError) -> str:
    return error.strerror or str(error)


def _report_error(stderr: TextIO, path: str, error: OSError) -> None:
    print(f"chmod: {path}: {_error_reason(error)}", file=stderr)


@register("chmod")
def chmod(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Record a simulated octal mode for each existing path."""
    if not args:
        print("chmod: missing operand", file=stderr)
        return 2

    mode_text = args[0]
    if not MODE_PATTERN.fullmatch(mode_text):
        print(
            f"chmod: invalid mode '{mode_text}' (use 3 or 4 octal digits)",
            file=stderr,
        )
        return 2
    if len(args) == 1:
        print("chmod: missing operand", file=stderr)
        return 2

    mode = int(mode_text, 8)
    failed = False
    for path in args[1:]:
        abs_path = resolve(ctx, path)
        if not os.path.exists(abs_path):
            _report_error(
                stderr,
                path,
                FileNotFoundError(2, "No such file or directory", path),
            )
            failed = True
            continue
        ctx.permissions[abs_path] = mode

    return 1 if failed else 0
