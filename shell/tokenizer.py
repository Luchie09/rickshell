"""Split shell input into words and operators."""

from dataclasses import dataclass


class ShellSyntaxError(Exception):
    """Raised when shell input has invalid syntax."""


@dataclass
class Token:
    """A shell word or operator; expand is false for single-quoted words."""

    kind: str
    value: str
    expand: bool = True


OPERATORS = ("2>&1", "&&", "||", ">>", "2>", "|", ";", ">", "<")


def tokenize(line: str) -> list[Token]:
    """Convert a line into word and operator tokens without interpreting it."""
    tokens: list[Token] = []
    word: list[str] = []
    word_started = False
    expand = True
    quote: str | None = None

    def finish_word() -> None:
        nonlocal word_started, expand
        if word_started:
            tokens.append(Token("WORD", "".join(word), expand))
            word.clear()
            word_started = False
            expand = True

    index = 0
    while index < len(line):
        char = line[index]

        if quote is not None:
            if char == quote:
                quote = None
            else:
                word.append(char)
            index += 1
            continue

        if char in ("'", '"'):
            word_started = True
            if char == "'":
                expand = False
            quote = char
            index += 1
            continue

        if char.isspace():
            finish_word()
            index += 1
            continue

        if char == "&":
            if line.startswith("&&", index):
                finish_word()
                tokens.append(Token("OP", "&&"))
                index += 2
                continue
            raise ShellSyntaxError("background jobs are not supported")

        # File-descriptor redirects are operators only when the token starts with 2.
        if not word_started and line.startswith("2>&1", index):
            tokens.append(Token("OP", "2>&1"))
            index += 4
            continue
        if not word_started and line.startswith("2>", index):
            tokens.append(Token("OP", "2>"))
            index += 2
            continue

        operator = next(
            (candidate for candidate in OPERATORS[1:4] + OPERATORS[5:] if line.startswith(candidate, index)),
            None,
        )
        if operator is not None:
            finish_word()
            tokens.append(Token("OP", operator))
            index += len(operator)
            continue

        word_started = True
        word.append(char)
        index += 1

    if quote is not None:
        raise ShellSyntaxError("unclosed quote")

    finish_word()
    return tokens
