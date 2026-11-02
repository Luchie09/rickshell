"""Build command, pipeline, and command-list structures from tokens."""

import pprint
import sys
from dataclasses import dataclass, field

from shell.tokenizer import ShellSyntaxError, Token, tokenize


@dataclass
class Command:
    """One command's words and its ordered redirections."""

    words: list[Token] = field(default_factory=list)
    redirects: list[tuple[str, Token | None]] = field(default_factory=list)


@dataclass
class Pipeline:
    """Commands connected by pipes."""

    commands: list[Command] = field(default_factory=list)


@dataclass
class CommandList:
    """Pipelines connected by ;, &&, or ||."""

    items: list[tuple[str | None, Pipeline]] = field(default_factory=list)


REDIRECTION_OPERATORS = {">", ">>", "<", "2>", "2>&1"}
LIST_CONNECTORS = {";", "&&", "||"}


def parse(tokens: list[Token]) -> CommandList:
    """Parse tokens into a list of pipelines and their connectors."""
    result = CommandList()
    if not tokens:
        return result

    pipeline = Pipeline()
    command = Command()
    command_has_content = False
    connector: str | None = None
    index = 0

    while index < len(tokens):
        token = tokens[index]

        if token.kind == "WORD":
            command.words.append(token)
            command_has_content = True
            index += 1
            continue

        if token.kind != "OP":
            raise ShellSyntaxError(f"unknown token kind: {token.kind}")

        if token.value in REDIRECTION_OPERATORS:
            if token.value == "2>&1":
                command.redirects.append((token.value, None))
                command_has_content = True
                index += 1
                continue

            if index + 1 >= len(tokens):
                raise ShellSyntaxError(f"redirection {token.value} is missing a target")
            target = tokens[index + 1]
            if target.kind != "WORD":
                raise ShellSyntaxError(f"redirection {token.value} target must be a word")
            command.redirects.append((token.value, target))
            command_has_content = True
            index += 2
            continue

        if token.value == "|":
            if not command_has_content:
                raise ShellSyntaxError("pipe has no command before it")
            pipeline.commands.append(command)
            command = Command()
            command_has_content = False
            index += 1
            if index == len(tokens):
                raise ShellSyntaxError("pipe has no command after it")
            if tokens[index].kind == "OP":
                raise ShellSyntaxError("two operators in a row")
            continue

        if token.value in LIST_CONNECTORS:
            if not command_has_content:
                raise ShellSyntaxError(f"connector {token.value} has no command before it")

            pipeline.commands.append(command)
            result.items.append((connector, pipeline))
            command = Command()
            command_has_content = False
            pipeline = Pipeline()
            connector = token.value
            index += 1

            if index == len(tokens):
                if token.value == ";":
                    return result
                raise ShellSyntaxError(f"connector {token.value} has no command after it")
            if tokens[index].kind == "OP":
                raise ShellSyntaxError("two operators in a row")
            continue

        raise ShellSyntaxError(f"unexpected operator: {token.value}")

    if not command_has_content:
        raise ShellSyntaxError("expected a command")

    pipeline.commands.append(command)
    result.items.append((connector, pipeline))
    return result


if __name__ == "__main__":
    try:
        parsed = parse(tokenize(" ".join(sys.argv[1:])))
        pprint.pprint(parsed)
    except ShellSyntaxError as error:
        print(error)
