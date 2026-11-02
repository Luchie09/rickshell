"""Read, dispatch, and run shell commands."""

import os
import sys

from shell.builtins import system  # Importing this module registers the built-ins.
from shell.builtins import vars as _vars  # Register variable-related built-ins.
from shell.context import ShellContext
from shell.executor import execute
from shell.parser import parse
from shell.tokenizer import ShellSyntaxError, tokenize


def build_prompt(ctx: ShellContext) -> str:
    """Return the working directory relative to where the shell started."""
    start_dir = os.path.abspath(ctx.start_dir)
    cwd = os.path.abspath(ctx.cwd)
    base = os.path.basename(os.path.normpath(start_dir))

    try:
        relative_path = os.path.relpath(cwd, start_dir)
    except ValueError:
        return ctx.cwd + "> "

    if relative_path == os.curdir:
        return base + "> "
    if relative_path != os.pardir and not relative_path.startswith(
        os.pardir + os.sep
    ):
        return base + os.sep + relative_path + "> "
    return ctx.cwd + "> "


def run(ctx: ShellContext) -> None:
    """Run the interactive shell until it receives an exit request or EOF."""
    while ctx.running:
        try:
            sys.stdout.write(build_prompt(ctx))
            sys.stdout.flush()
            line = sys.stdin.readline()

            if line == "":
                ctx.running = False
                break

            tokens = tokenize(line)
            if not tokens:
                continue

            command_list = parse(tokens)
            execute(
                command_list,
                ctx,
                sys.stdin,
                sys.stdout,
                sys.stderr,
            )
        except ShellSyntaxError as error:
            ctx.last_exit_code = 2
            print(f"rickshell: syntax error: {error}", file=sys.stderr)
        except KeyboardInterrupt:
            sys.stdout.write("\n")
        except Exception as error:
            ctx.last_exit_code = 1
            print(f"rickshell: {error}", file=sys.stderr)
