"""Built-in commands for displaying text and shell variables."""

from typing import TextIO

from shell.builtins import register
from shell.context import ShellContext


@register("echo")
def echo(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Print arguments separated by spaces."""
    print(" ".join(args), file=stdout)
    return 0


@register("env")
def env(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Print all shell variables in name order."""
    for name in sorted(ctx.variables):
        print(f"{name}={ctx.variables[name]}", file=stdout)
    return 0
