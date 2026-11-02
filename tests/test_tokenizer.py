"""Tests for shell tokenization."""

import unittest

from shell.tokenizer import ShellSyntaxError, Token, tokenize


class TokenizerTests(unittest.TestCase):
    def test_empty_and_whitespace_only_lines(self) -> None:
        self.assertEqual(tokenize(""), [])
        self.assertEqual(tokenize(" \t  \n"), [])

    def test_simple_command_and_arguments(self) -> None:
        self.assertEqual(
            tokenize("echo hello world"),
            [Token("WORD", "echo"), Token("WORD", "hello"), Token("WORD", "world")],
        )

    def test_quotes_and_adjacent_pieces(self) -> None:
        self.assertEqual(tokenize('echo "two words"'), [
            Token("WORD", "echo"),
            Token("WORD", "two words"),
        ])
        self.assertEqual(tokenize("echo '$HOME'"), [
            Token("WORD", "echo"),
            Token("WORD", "$HOME", False),
        ])
        self.assertEqual(tokenize('echo a"b c"d'), [
            Token("WORD", "echo"),
            Token("WORD", "ab cd"),
        ])

    def test_unclosed_quote_raises_syntax_error(self) -> None:
        with self.assertRaisesRegex(ShellSyntaxError, "^unclosed quote$"):
            tokenize('echo "unfinished')

    def test_operators_are_split_with_or_without_spaces(self) -> None:
        cases = {
            "ls|grep txt": ["ls", "|", "grep", "txt"],
            "a&&b": ["a", "&&", "b"],
            "a ;b": ["a", ";", "b"],
            "x>f": ["x", ">", "f"],
            "x>>f": ["x", ">>", "f"],
            "x<f": ["x", "<", "f"],
        }
        for line, expected in cases.items():
            with self.subTest(line=line):
                self.assertEqual([token.value for token in tokenize(line)], expected)

    def test_file_descriptor_redirects(self) -> None:
        self.assertEqual(
            tokenize("cmd 2>errors.txt 2>&1"),
            [
                Token("WORD", "cmd"),
                Token("OP", "2>"),
                Token("WORD", "errors.txt"),
                Token("OP", "2>&1"),
            ],
        )
        self.assertEqual(
            tokenize("abc2 > f"),
            [Token("WORD", "abc2"), Token("OP", ">"), Token("WORD", "f")],
        )

    def test_lone_ampersand_is_not_supported(self) -> None:
        with self.assertRaisesRegex(
            ShellSyntaxError, "^background jobs are not supported$"
        ):
            tokenize("command &")


if __name__ == "__main__":
    unittest.main()
