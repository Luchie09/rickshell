"""Tests for the clear builtin."""

import io
import unittest

from shell.builtins import REGISTRY
from shell.builtins.system import cmd_clear, help_command
from shell.context import ShellContext


class ClearTests(unittest.TestCase):
    def test_stringio_stdout_is_left_empty(self) -> None:
        output = io.StringIO()
        result = cmd_clear([], io.StringIO(), output, io.StringIO(), ShellContext())
        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), "")

    def test_terminal_receives_exact_escape_codes_and_flushes(self) -> None:
        class FakeTerminal:
            def __init__(self) -> None:
                self.writes: list[str] = []
                self.flushed = False

            def isatty(self) -> bool:
                return True

            def write(self, text: str) -> int:
                self.writes.append(text)
                return len(text)

            def flush(self) -> None:
                self.flushed = True

        terminal = FakeTerminal()
        result = cmd_clear([], io.StringIO(), terminal, io.StringIO(), ShellContext())
        self.assertEqual(result, 0)
        self.assertEqual("".join(terminal.writes), "\033[H\033[2J\033[3J")
        self.assertTrue(terminal.flushed)

    def test_argument_returns_usage_error(self) -> None:
        output = io.StringIO()
        error = io.StringIO()
        result = cmd_clear(
            ["extra"],
            io.StringIO(),
            output,
            error,
            ShellContext(),
        )
        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(error.getvalue(), "clear: usage: clear\n")

    def test_stream_without_isatty_is_not_terminal(self) -> None:
        class StreamWithoutIsatty:
            def __init__(self) -> None:
                self.writes: list[str] = []

            def write(self, text: str) -> int:
                self.writes.append(text)
                return len(text)

        output = StreamWithoutIsatty()
        result = cmd_clear([], io.StringIO(), output, io.StringIO(), ShellContext())
        self.assertEqual(result, 0)
        self.assertEqual(output.writes, [])

    def test_help_lists_clear(self) -> None:
        output = io.StringIO()
        result = help_command(
            [],
            io.StringIO(),
            output,
            io.StringIO(),
            ShellContext(),
        )
        self.assertEqual(result, 0)
        self.assertIn("clear\n", output.getvalue())
        self.assertIn("clear", REGISTRY)


if __name__ == "__main__":
    unittest.main()
