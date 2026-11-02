"""Tests for the plain-text grep builtin."""

import io
import os
import tempfile
import unittest

from shell.builtins import REGISTRY
from shell.context import ShellContext


class GrepTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.context = ShellContext()
        self.context.cwd = self.temporary_directory.name
        with open(
            os.path.join(self.context.cwd, "words.txt"),
            "w",
            encoding="utf-8",
        ) as file:
            file.write("Hello World\nhello again\nnothing here\nHELLO\n")

    def run_grep(self, args: list[str], stdin: str = "") -> tuple[int, str, str]:
        output = io.StringIO()
        error = io.StringIO()
        result = REGISTRY["grep"](
            args,
            io.StringIO(stdin),
            output,
            error,
            self.context,
        )
        return result, output.getvalue(), error.getvalue()

    def test_plain_and_case_insensitive_search(self) -> None:
        self.assertEqual(
            self.run_grep(["hello", "words.txt"]),
            (0, "hello again\n", ""),
        )
        self.assertEqual(
            self.run_grep(["-i", "hello", "words.txt"]),
            (0, "Hello World\nhello again\nHELLO\n", ""),
        )

    def test_line_numbers_and_combined_flags(self) -> None:
        self.assertEqual(
            self.run_grep(["-n", "hello", "words.txt"]),
            (0, "2:hello again\n", ""),
        )
        expected = "1:Hello World\n2:hello again\n4:HELLO\n"
        self.assertEqual(self.run_grep(["-in", "hello", "words.txt"]), (0, expected, ""))
        self.assertEqual(self.run_grep(["-ni", "hello", "words.txt"]), (0, expected, ""))

    def test_no_match_and_stdin(self) -> None:
        self.assertEqual(self.run_grep(["zzz", "words.txt"]), (1, "", ""))
        self.assertEqual(
            self.run_grep(["no"], "one\nno\nnope\n"),
            (0, "no\nnope\n", ""),
        )

    def test_multiple_files_prefix_with_filename_and_line_number(self) -> None:
        for name, content in (
            ("a.txt", "skip\nmatch a\n"),
            ("b.txt", "match b\n"),
        ):
            with open(
                os.path.join(self.context.cwd, name),
                "w",
                encoding="utf-8",
            ) as file:
                file.write(content)

        self.assertEqual(
            self.run_grep(["match", "a.txt", "b.txt"]),
            (0, "a.txt:match a\nb.txt:match b\n", ""),
        )
        self.assertEqual(
            self.run_grep(["-n", "match", "a.txt", "b.txt"]),
            (0, "a.txt:2:match a\nb.txt:1:match b\n", ""),
        )

    def test_missing_file_and_partial_success(self) -> None:
        self.assertEqual(
            self.run_grep(["hello", "missing.txt"]),
            (2, "", "grep: missing.txt: No such file or directory\n"),
        )
        result, output, error = self.run_grep(
            ["hello", "words.txt", "missing.txt"]
        )
        self.assertEqual(result, 2)
        self.assertIn("hello again\n", output)
        self.assertEqual(
            error,
            "grep: missing.txt: No such file or directory\n",
        )

    def test_invalid_option_and_missing_pattern(self) -> None:
        self.assertEqual(
            self.run_grep(["-x", "hello"]),
            (2, "", "grep: invalid option -- 'x'\n"),
        )
        self.assertEqual(
            self.run_grep(["-in"]),
            (2, "", "usage: grep [-i] [-n] PATTERN [file...]\n"),
        )
        self.assertEqual(
            self.run_grep([]),
            (2, "", "usage: grep [-i] [-n] PATTERN [file...]\n"),
        )

    def test_non_newline_terminated_last_line(self) -> None:
        with open(
            os.path.join(self.context.cwd, "last.txt"),
            "w",
            encoding="utf-8",
        ) as file:
            file.write("matching line")
        self.assertEqual(
            self.run_grep(["matching", "last.txt"]),
            (0, "matching line\n", ""),
        )

    def test_empty_file_and_help_registration(self) -> None:
        with open(os.path.join(self.context.cwd, "empty.txt"), "w", encoding="utf-8"):
            pass
        self.assertEqual(self.run_grep(["x", "empty.txt"]), (1, "", ""))
        self.assertIn("grep", REGISTRY)


if __name__ == "__main__":
    unittest.main()
