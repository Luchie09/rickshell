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
    """Pipelines and conditionals connected by ;, &&, or ||."""

    items: list[tuple[str | None, Pipeline | "IfBlock"]] = field(
        default_factory=list
    )


@dataclass
class IfBlock:
    """A single-level conditional and its parsed command branches."""

    condition: CommandList
    then_body: CommandList
    else_body: CommandList | None = None


REDIRECTION_OPERATORS = {">", ">>", "<", "2>", "2>&1"}
LIST_CONNECTORS = {";", "&&", "||"}


def _parse_pipeline(tokens: list[Token]) -> Pipeline:
    """Parse one pipeline without list connectors."""
    parsed = _parse_plain(tokens)
    if len(parsed.items) != 1 or parsed.items[0][0] is not None:
        raise ShellSyntaxError("expected a command")
    return parsed.items[0][1]


def _parse_plain(tokens: list[Token]) -> CommandList:
    """Parse tokens using the original pipeline and list grammar."""
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


def _is_word(tokens: list[Token], index: int, value: str) -> bool:
    return (
        index < len(tokens)
        and tokens[index].kind == "WORD"
        and tokens[index].value == value
    )


def _raise_if_nested(tokens: list[Token]) -> None:
    """Reject if as a command word at the start of any branch item."""
    command_position = True
    for token in tokens:
        if command_position and token.kind == "WORD" and token.value == "if":
            raise ShellSyntaxError("nested if is not supported")
        if token.kind == "OP" and token.value in LIST_CONNECTORS:
            command_position = True
        elif token.kind == "WORD" or (
            token.kind == "OP" and token.value not in REDIRECTION_OPERATORS
        ):
            command_position = False


def _parse_if_block(tokens: list[Token], start: int) -> tuple[IfBlock, int]:
    """Parse an if block and return its node and first unconsumed token index."""
    then_separator = None
    for index in range(start + 1, len(tokens) - 1):
        if (
            tokens[index].kind == "OP"
            and tokens[index].value == ";"
            and _is_word(tokens, index + 1, "then")
        ):
            then_separator = index
            break
        if (
            tokens[index].kind == "OP"
            and tokens[index].value == ";"
            and _is_word(tokens, index + 1, "fi")
        ):
            raise ShellSyntaxError("expected 'then'")

    if then_separator is None:
        raise ShellSyntaxError("expected 'then'")

    condition_tokens = tokens[start + 1 : then_separator]
    if not condition_tokens:
        raise ShellSyntaxError("expected 'then'")
    _raise_if_nested(condition_tokens)
    condition = parse(condition_tokens)

    body_start = then_separator + 2
    then_end = None
    else_end = None
    else_start = None
    block_end = None
    command_position = True
    index = body_start
    while index < len(tokens):
        token = tokens[index]
        if (
            token.kind == "OP"
            and token.value == ";"
            and _is_word(tokens, index + 1, "fi")
        ):
            if else_start is not None:
                else_end = index
            else:
                then_end = index
            block_end = index + 2
            break
        if (
            token.kind == "OP"
            and token.value == ";"
            and _is_word(tokens, index + 1, "else")
        ):
            if else_start is not None:
                raise ShellSyntaxError("expected 'fi'")
            then_end = index
            else_start = index + 2
            command_position = True
            index += 2
            continue
        if command_position and token.kind == "WORD" and token.value == "if":
            raise ShellSyntaxError("nested if is not supported")
        if token.kind == "OP" and token.value in LIST_CONNECTORS:
            command_position = True
        elif token.kind == "WORD":
            command_position = False
        index += 1

    if block_end is None:
        raise ShellSyntaxError("expected 'fi'")

    if else_start is None:
        then_tokens = tokens[body_start:then_end]
        else_body = None
    else:
        then_tokens = tokens[body_start:then_end]
        else_tokens = tokens[else_start:else_end]
        _raise_if_nested(else_tokens)
        else_body = parse(else_tokens)

    _raise_if_nested(then_tokens)
    then_body = parse(then_tokens)
    return IfBlock(condition, then_body, else_body), block_end


def parse(tokens: list[Token]) -> CommandList:
    """Parse command lists, recognizing if only at the start of an item."""
    if not tokens:
        return CommandList()

    result = CommandList()
    connector: str | None = None
    index = 0

    while index < len(tokens):
        if tokens[index].kind == "OP":
            if tokens[index].value == "|":
                raise ShellSyntaxError("pipe has no command before it")
            raise ShellSyntaxError(
                f"connector {tokens[index].value} has no command before it"
            )

        if _is_word(tokens, index, "if"):
            conditional, index = _parse_if_block(tokens, index)
            result.items.append((connector, conditional))
        else:
            start = index
            while index < len(tokens) and not (
                tokens[index].kind == "OP"
                and tokens[index].value in LIST_CONNECTORS
            ):
                index += 1
            pipeline = _parse_pipeline(tokens[start:index])
            result.items.append((connector, pipeline))

        if index == len(tokens):
            break

        separator = tokens[index]
        connector = separator.value
        index += 1
        if index == len(tokens):
            if connector == ";":
                break
            raise ShellSyntaxError(
                f"connector {connector} has no command after it"
            )

    return result


if __name__ == "__main__":
    try:
        parsed = parse(tokenize(" ".join(sys.argv[1:])))
        pprint.pprint(parsed)
    except ShellSyntaxError as error:
        print(error)
