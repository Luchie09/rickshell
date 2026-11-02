"""Read, dispatch, and run shell commands."""

import sys

from shell.builtins import system  # Importing this module registers the built-ins.
from shell.builtins import vars as _vars  # Register variable-related built-ins.
from shell.context import ShellContext
from shell.executor import execute
from shell.parser import parse
from shell.tokenizer import ShellSyntaxError, tokenize

PROMPT = "rickshell> "


def run(ctx: ShellContext) -> None:
    """Run the interactive shell until it receives an exit request or EOF."""
    while ctx.running:
        try:
            sys.stdout.write(PROMPT)
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
