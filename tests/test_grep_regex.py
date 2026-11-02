"""Tests for grep extended regular expressions and capture groups."""

import io
import os
import tempfile
import unittest

from shell.context import ShellContext
from shell.executor import execute
from shell.parser import parse
from shell.tokenizer import tokenize
from shell.builtins.search import cmd_grep


class GrepRegexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.context = ShellContext()
        self.context.cwd = self.temporary_directory.name
        self.path = os.path.join(self.context.cwd, "a.txt")
        with open(self.path, "w", encoding="utf-8") as file:
            file.write("hello\nHELLO\nhelp\na.b\naxb\ncolor\ncolour\n")

    def run_grep(self, args: list[str], stdin: str = "") -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = cmd_grep(
            args,
            io.StringIO(stdin),
            stdout,
            stderr,
            self.context,
        )
        return result, stdout.getvalue(), stderr.getvalue()

    def test_group_matching_and_flag_after_file(self) -> None:
        self.assertEqual(
            self.run_grep(["-E", "h(e)l+o", "a.txt"]),
            (0, "hello\n", ""),
        )
        self.assertEqual(
            self.run_grep(["-E", "h(e)l+o", "a.txt", "--groups"]),
            (0, "hello\n  groups: 1=e\n", ""),
        )

    def test_ignore_case_quantifiers_escapes_and_character_classes(self) -> None:
        self.assertEqual(
            self.run_grep(["-E", "-i", "h.llo", "a.txt"]),
            (0, "hello\nHELLO\n", ""),
        )
        self.assertEqual(
            self.run_grep(["-E", "colou?r", "a.txt"]),
            (0, "color\ncolour\n", ""),
        )
        self.assertEqual(
            self.run_grep(["-E", r"a\.b", "a.txt"]),
            (0, "a.b\n", ""),
        )
        self.assertEqual(
            self.run_grep(["-E", "[a-z]+p", "a.txt"]),
            (0, "help\n", ""),
        )

    def test_invalid_pattern_reports_error(self) -> None:
        result, output, error = self.run_grep(["-E", "h(e", "a.txt"])
        self.assertEqual(result, 2)
        self.assertEqual(output, "")
        self.assertIn("grep: invalid pattern:", error)

    def test_plain_pattern_remains_literal(self) -> None:
        self.assertEqual(
            self.run_grep(["a.b", "a.txt"]),
            (0, "a.b\n", ""),
        )

    def test_extended_regex_reads_stdin_through_pipe(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = execute(
            parse(tokenize("echo hello | grep -E 'l+'")),
            self.context,
            io.StringIO(),
            stdout,
            stderr,
        )
        self.assertEqual((result, stdout.getvalue(), stderr.getvalue()), (0, "hello\n", ""))

    def test_line_numbers_work_with_regex(self) -> None:
        self.assertEqual(
            self.run_grep(["-n", "-E", "h(e)l+o", "a.txt"]),
            (0, "1:hello\n", ""),
        )


if __name__ == "__main__":
    unittest.main()
