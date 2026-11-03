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
    successful_commands = 0
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
            if exit_code == 0:
                successful_commands += 1
            if ctx.easter_eggs and _rick.is_terminal(sys.stdout):
                try:
                    if exit_code == 127:
                        time.sleep(2)
                        _rick.play_rick(sys.stdout)
                    elif exit_code == 0 and successful_commands % 10 == 0:
                        _rick.play_silent(sys.stdout, duration=2.0)
                except (Exception, KeyboardInterrupt):
                    pass
        except ShellSyntaxError as error:
            ctx.last_exit_code = 2
            print(f"rickshell: syntax error: {error}", file=sys.stderr)
        except KeyboardInterrupt:
            sys.stdout.write("\n")
        except Exception as error:
            ctx.last_exit_code = 1
            print(f"rickshell: {error}", file=sys.stderr)
