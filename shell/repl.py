"""Read, dispatch, and run shell commands."""

import sys

from shell.builtins import REGISTRY
from shell.builtins import system  # Importing this module registers the built-ins.
from shell.context import ShellContext

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

            words = line.split()
            if not words:
                continue

            name = words[0]
            command = REGISTRY.get(name)
            if command is None:
                print(
                    f"rickshell: {name}: command not found",
                    file=sys.stderr,
                )
                ctx.last_exit_code = 127
                continue

            ctx.last_exit_code = command(
                words[1:],
                sys.stdin,
                sys.stdout,
                sys.stderr,
                ctx,
            )
        except KeyboardInterrupt:
            sys.stdout.write("\n")
        except Exception as error:
            ctx.last_exit_code = 1
            print(f"rickshell: {error}", file=sys.stderr)
