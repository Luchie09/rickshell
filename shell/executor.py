"""Expand and run parsed commands, pipelines, and command lists."""

import io
import os
import re
from typing import TextIO

from shell.builtins import REGISTRY
from shell.builtins import system as _system
from shell.builtins import vars as _vars
from shell.context import ShellContext
from shell.parser import Command, CommandList, IfBlock, Pipeline
from shell.tokenizer import Token

EXPANSION_PATTERN = re.compile(r"\$(\?|[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})")
ASSIGNMENT_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _expand(value: str, ctx: ShellContext) -> str:
    """Replace supported variable references using the current shell state."""
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name == "?":
            return str(ctx.last_exit_code)
        if name.startswith("{"):
            name = name[1:-1]
        return ctx.variables.get(name, "")

    return EXPANSION_PATTERN.sub(replace, value)


def _word_value(token: Token, ctx: ShellContext) -> str:
    # Single-quoted words are marked expand=False by the tokenizer.
    if token.expand:
        return _expand(token.value, ctx)
    return token.value


def _run_command(
    command: Command,
    ctx: ShellContext,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Run one command and close any files opened by its redirects."""
    opened_files: list[TextIO] = []
    current_stdin = stdin
    current_stdout = stdout
    current_stderr = stderr
    words = [_word_value(word, ctx) for word in command.words]
    name = words[0] if words else ""
    exit_code = 0
    redirect_failed = False

    try:
        # Apply redirects left to right, like Bash: "2>&1" points stderr at
        # whatever stdout is at that moment, so its position matters.
        for operator, target_token in command.redirects:
            if operator == "2>&1":
                current_stderr = current_stdout
                continue

            if target_token is None:
                continue

            target = _word_value(target_token, ctx)
            path = target if os.path.isabs(target) else os.path.join(ctx.cwd, target)
            mode = {
                ">": "w",
                ">>": "a",
                "<": "r",
                "2>": "w",
            }[operator]
            try:
                redirected_file = open(path, mode)
            except OSError as error:
                print(f"rickshell: {target}: {error}", file=current_stderr)
                exit_code = 1
                redirect_failed = True
                break

            opened_files.append(redirected_file)
            if operator == "<":
                current_stdin = redirected_file
            elif operator == "2>":
                current_stderr = redirected_file
            else:
                current_stdout = redirected_file

        if not redirect_failed and words:
            # NAME=value on its own is an assignment; otherwise look up a command.
            assignment = (
                ASSIGNMENT_PATTERN.fullmatch(words[0])
                if len(words) == 1
                else None
            )
            if assignment is not None:
                ctx.variables[assignment.group(1)] = assignment.group(2)
            else:
                function = REGISTRY.get(name)
                if function is None:
                    print(
                        f"rickshell: {name}: command not found",
                        file=current_stderr,
                    )
                    exit_code = 127
                else:
                    exit_code = function(
                        words[1:],
                        current_stdin,
                        current_stdout,
                        current_stderr,
                        ctx,
                    )
    except Exception as error:
        exit_code = 1
        try:
            print(
                f"rickshell: {name}: internal error: {error}",
                file=current_stderr,
            )
        except Exception:
            if current_stderr is not stderr:
                try:
                    print(
                        f"rickshell: {name}: internal error: {error}",
                        file=stderr,
                    )
                except Exception:
                    pass
    finally:
        for opened_file in opened_files:
            try:
                opened_file.close()
            except Exception as error:
                exit_code = 1
                try:
                    print(
                        f"rickshell: {name}: internal error: {error}",
                        file=stderr,
                    )
                except Exception:
                    pass

    return exit_code


def _run_pipeline(
    pipeline: Pipeline,
    ctx: ShellContext,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Run pipeline stages in order, passing each output buffer forward."""
    next_stdin = stdin
    exit_code = 0

    for index, command in enumerate(pipeline.commands):
        is_last = index == len(pipeline.commands) - 1
        stage_stdout: TextIO
        if is_last:
            stage_stdout = stdout
            output_buffer = None
        else:
            output_buffer = io.StringIO()
            stage_stdout = output_buffer

        exit_code = _run_command(command, ctx, next_stdin, stage_stdout, stderr)
        if output_buffer is not None:
            next_stdin = io.StringIO(output_buffer.getvalue())

    return exit_code


def execute(
    command_list: CommandList,
    ctx: ShellContext,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Run eligible pipelines and update the last exit code after each one."""
    for connector, pipeline in command_list.items:
        # && and || only look at the exit code of whatever ran last.
        should_run = (
            connector is None
            or connector == ";"
            or (connector == "&&" and ctx.last_exit_code == 0)
            or (connector == "||" and ctx.last_exit_code != 0)
        )
        if not should_run:
            continue

        if isinstance(pipeline, IfBlock):
            condition_code = execute(
                pipeline.condition,
                ctx,
                stdin,
                stdout,
                stderr,
            )
            if condition_code == 0:
                ctx.last_exit_code = execute(
                    pipeline.then_body,
                    ctx,
                    stdin,
                    stdout,
                    stderr,
                )
            elif pipeline.else_body is not None:
                ctx.last_exit_code = execute(
                    pipeline.else_body,
                    ctx,
                    stdin,
                    stdout,
                    stderr,
                )
            else:
                ctx.last_exit_code = 0
        else:
            ctx.last_exit_code = _run_pipeline(
                pipeline,
                ctx,
                stdin,
                stdout,
                stderr,
            )

    return ctx.last_exit_code
