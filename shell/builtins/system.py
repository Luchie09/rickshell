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
