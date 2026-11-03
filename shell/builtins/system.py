"""Basic shell control commands."""

from typing import TextIO

from shell.builtins import REGISTRY, register
from shell.context import ShellContext


@register("exit")
def exit_command(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Stop the shell loop."""
    ctx.running = False
    return 0


@register("help")
def help_command(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Print the names of all registered commands."""
    for name in sorted(REGISTRY):
        print(name, file=stdout)
    return 0


@register("true")
def true_command(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Return a successful exit code."""
    return 0


@register("false")
def false_command(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Return an unsuccessful exit code."""
    return 1


@register("clear")
def cmd_clear(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Clear a terminal without producing escape codes in redirected output."""
    if args:
        stderr.write("clear: usage: clear\n")
        return 2

    try:
        is_terminal = stdout.isatty()
    except (AttributeError, OSError):
        is_terminal = False

    if is_terminal:
        # Home, clear display, then clear scrollback; terminals interpret these codes.
        stdout.write("\033[H\033[2J\033[3J")
        stdout.flush()
    # Non-terminals receive no output so redirects and pipes stay clean.
    return 0


@register("rick")
def cmd_rick(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Stream the live Rick animation or toggle its automatic triggers."""
    if args == ["on"]:
        ctx.easter_eggs = True
        return 0
    if args == ["off"]:
        ctx.easter_eggs = False
        return 0
    if args not in ([], ["--live"]):
        stderr.write("rick: usage: rick [on|off|--live]\n")
        return 2

    from shell.easter.rick import play_rick

    play_rick(stdout)
    return 0
