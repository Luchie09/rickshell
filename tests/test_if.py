"""Tests for single-line if/then/else execution."""

import io
import os
import tempfile
import unittest

from shell.context import ShellContext
from shell.executor import execute
from shell.parser import parse
from shell.tokenizer import ShellSyntaxError, tokenize


class IfTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.context = ShellContext()
        self.context.cwd = self.directory.name
        with open(
            os.path.join(self.directory.name, "a.txt"),
            "w",
            encoding="utf-8",
        ):
            pass

    def run_line(self, line: str) -> tuple[int, str, str]:
        stdin = io.StringIO()
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            command_list = parse(tokenize(line))
        except ShellSyntaxError as error:
            self.context.last_exit_code = 2
            stderr.write(f"rickshell: syntax error: {error}\n")
            return 2, stdout.getvalue(), stderr.getvalue()
        result = execute(command_list, self.context, stdin, stdout, stderr)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_true_condition_runs_then_branch(self) -> None:
        result, output, error = self.run_line(
            "if cat a.txt; then echo found; else echo none; fi"
        )
        self.assertEqual((result, output, error), (0, "found\n", ""))

    def test_failed_condition_runs_else_and_keeps_stderr(self) -> None:
        result, output, error = self.run_line(
            "if cat missing.txt; then echo found; else echo none; fi"
        )
        self.assertEqual(result, 0)
        self.assertEqual(output, "none\n")
        self.assertIn("cat: missing.txt", error)

    def test_failed_condition_without_else_runs_nothing(self) -> None:
        result, output, error = self.run_line(
            "if cat missing.txt; then echo found; fi"
        )
        self.assertEqual(result, 0)
        self.assertEqual(output, "")
        self.assertIn("cat: missing.txt", error)

    def test_missing_fi_is_syntax_error(self) -> None:
        result, _output, error = self.run_line(
            "if echo test; then echo found"
        )
        self.assertEqual(result, 2)
        self.assertIn("syntax error: expected 'fi'", error)

    def test_then_as_argument_is_not_a_keyword(self) -> None:
        result, output, error = self.run_line("echo then")
        self.assertEqual((result, output, error), (0, "then\n", ""))

    def test_if_block_can_be_followed_by_list_items(self) -> None:
        result, output, error = self.run_line(
            "if echo a; then echo b; fi ; echo c"
        )
        self.assertEqual((result, output, error), (0, "a\nb\nc\n", ""))

        result, output, error = self.run_line(
            "if echo a; then echo b; fi && echo ok"
        )
        self.assertEqual((result, output, error), (0, "a\nb\nok\n", ""))

    def test_nested_if_is_rejected(self) -> None:
        result, output, error = self.run_line(
            "if echo a; then if echo b; then echo c; fi; fi"
        )
        self.assertEqual(result, 2)
        self.assertEqual(output, "")
        self.assertIn(
            "syntax error: nested if is not supported",
            error,
        )

    def test_missing_then_is_syntax_error(self) -> None:
        result, _output, error = self.run_line("if echo a; echo b; fi")
        self.assertEqual(result, 2)
        self.assertIn("syntax error: expected 'then'", error)


if __name__ == "__main__":
    unittest.main()
