"""Read, dispatch, and run shell commands."""

import os
import sys
import time

from shell.builtins import system  # Importing this module registers the built-ins.
from shell.builtins import vars as _vars  # Register variable-related built-ins.
from shell.context import ShellContext
from shell.easter import rick as _rick
from shell.executor import execute
from shell.parser import parse
from shell.tokenizer import ShellSyntaxError, tokenize

_ansi_initialized = False


def build_prompt(ctx: ShellContext) -> str:
    """Return the working directory relative to where the shell started."""
    start_dir = os.path.abspath(ctx.start_dir)
    cwd = os.path.abspath(ctx.cwd)
    base = os.path.basename(os.path.normpath(start_dir))

    try:
        relative_path = os.path.relpath(cwd, start_dir)
    except ValueError:
        return ctx.cwd + " > "

    if relative_path == os.curdir:
        return base + " > "
    if relative_path != os.pardir and not relative_path.startswith(
        os.pardir + os.sep
    ):
        return base + os.sep + relative_path + " > "
    return ctx.cwd + " > "


def run(ctx: ShellContext) -> None:
    """Run the interactive shell until it receives an exit request or EOF."""
    global _ansi_initialized
    # An empty os.system call switches the Windows console into ANSI mode,
    # which ls colors, clear, and the Rick animation rely on.
    if os.name == "nt" and not _ansi_initialized:
        os.system("")
        _ansi_initialized = True

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
            exit_code = execute(
                command_list,
                ctx,
                sys.stdin,
                sys.stdout,
                sys.stderr,
            )
            # Unknown command (127) plays Rick until Ctrl+C. Terminal only,
            # so redirected or piped output is never affected.
            if (
                exit_code == 127
                and ctx.easter_eggs
                and _rick.is_terminal(sys.stdout)
            ):
                try:
                    time.sleep(2)
                    _rick.play_rick(sys.stdout)
                except (Exception, KeyboardInterrupt):
                    pass
        # Last line of defence: nothing typed at the prompt may end the shell.
        except ShellSyntaxError as error:
            ctx.last_exit_code = 2
            print(f"rickshell: syntax error: {error}", file=sys.stderr)
        except KeyboardInterrupt:
            sys.stdout.write("\n")
        except Exception as error:
            ctx.last_exit_code = 1
            print(f"rickshell: {error}", file=sys.stderr)
