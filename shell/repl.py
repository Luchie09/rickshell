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
    """Show paths relative to the directory where this shell started."""
    cwd = os.path.abspath(ctx.cwd)
    start_dir = os.path.abspath(ctx.start_dir)
    start_name = os.path.basename(os.path.normpath(start_dir)) or start_dir

    try:
        remainder = os.path.relpath(cwd, start_dir)
    except ValueError:
        remainder = os.pardir

    if os.path.normcase(cwd) == os.path.normcase(start_dir):
        display_path = start_name
    elif remainder != os.pardir and not remainder.startswith(
        os.pardir + os.sep
    ):
        display_path = os.path.join(start_name, remainder)
    else:
        display_path = cwd

    return f"rickshell:{display_path}> "


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
