"""Tests for parsing shell tokens into command structures."""

import unittest

from shell.parser import Command, CommandList, Pipeline, parse
from shell.tokenizer import ShellSyntaxError, Token, tokenize


def parse_line(line: str) -> CommandList:
    """Tokenize and parse a line for concise test setup."""
    return parse(tokenize(line))


class ParserTests(unittest.TestCase):
    def test_empty_input(self) -> None:
        self.assertEqual(parse([]), CommandList())
        self.assertEqual(parse_line("  \t"), CommandList())

    def test_simple_command(self) -> None:
        self.assertEqual(
            parse_line("echo hello"),
            CommandList([
                (
                    None,
                    Pipeline([
                        Command(words=[Token("WORD", "echo"), Token("WORD", "hello")])
                    ]),
                )
            ]),
        )

    def test_redirect_order_is_preserved(self) -> None:
        output_first = parse_line("cmd > f 2>&1")
        self.assertEqual(
            output_first.items[0][1].commands[0].redirects,
            [(">", Token("WORD", "f")), ("2>&1", None)],
        )

        stderr_first = parse_line("cmd 2>&1 > f")
        self.assertEqual(
            stderr_first.items[0][1].commands[0].redirects,
            [("2>&1", None), (">", Token("WORD", "f"))],
        )

    def test_three_stage_pipeline(self) -> None:
        parsed = parse_line("a | b | c")
        self.assertEqual(
            parsed,
            CommandList([
                (
                    None,
                    Pipeline([
                        Command(words=[Token("WORD", "a")]),
                        Command(words=[Token("WORD", "b")]),
                        Command(words=[Token("WORD", "c")]),
                    ]),
                )
            ]),
        )

    def test_connectors(self) -> None:
        parsed = parse_line("a ; b && c || d")
        self.assertEqual(
            [connector for connector, _ in parsed.items],
            [None, ";", "&&", "||"],
        )
        self.assertEqual(
            [
                item.commands[0].words[0].value
                for _, item in parsed.items
            ],
            ["a", "b", "c", "d"],
        )

    def test_trailing_semicolon_is_allowed(self) -> None:
        self.assertEqual(len(parse_line("a ;").items), 1)

    def test_syntax_errors(self) -> None:
        cases = [
            ("| a", "pipe has no command before it"),
            ("&& a", "connector && has no command before it"),
            ("|| a", "connector || has no command before it"),
            ("; a", "connector ; has no command before it"),
            ("a &&", "connector && has no command after it"),
            ("a ||", "connector || has no command after it"),
            ("a |", "pipe has no command after it"),
            ("a | | b", "two operators in a row"),
            ("cat >", "redirection > is missing a target"),
            ("cat > | next", "redirection > target must be a word"),
        ]
        for line, message in cases:
            with self.subTest(line=line), self.assertRaisesRegex(
                ShellSyntaxError, message.replace("|", r"\|")
            ):
                parse_line(line)


if __name__ == "__main__":
    unittest.main()
