"""Tests for the initial shell skeleton."""

import io
import sys
import unittest
from unittest.mock import patch

from shell.builtins import REGISTRY
from shell.builtins.system import exit_command, help_command
from shell.context import ShellContext
from shell.repl import run


class ShellSkeletonTests(unittest.TestCase):
    def test_help_prints_registered_command_names_in_order(self) -> None:
        output = io.StringIO()

        result = help_command([], io.StringIO(), output, io.StringIO(), ShellContext())

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), "".join(f"{name}\n" for name in sorted(REGISTRY)))

    def test_exit_sets_running_to_false(self) -> None:
        context = ShellContext()

        result = exit_command([], io.StringIO(), io.StringIO(), io.StringIO(), context)

        self.assertEqual(result, 0)
        self.assertFalse(context.running)

    def test_unknown_command_sets_127_and_prints_message(self) -> None:
        context = ShellContext()
        stdin = io.StringIO("not-a-command\n")
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout), patch.object(
            sys, "stderr", stderr
        ):
            run(context)

        self.assertEqual(context.last_exit_code, 127)
        self.assertIn("rickshell: not-a-command: command not found\n", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
