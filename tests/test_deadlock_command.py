"""Tests for the deadlock shell command."""

import io
import os
import unittest
from unittest.mock import patch

from shell.builtins import REGISTRY
from shell.builtins.system import help_command
from shell.context import ShellContext
from sim.commands import cmd_deadlock
from sim.deadlock import ResourceState
from sim.loader import load_resources


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCE_DIR = os.path.join(ROOT, "data", "resources")


class DeadlockCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ShellContext()
        self.context.cwd = RESOURCE_DIR

    def run_deadlock(self, args: list[str]) -> tuple[int, str, str]:
        stdin = io.StringIO()
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = cmd_deadlock(args, stdin, stdout, stderr, self.context)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_detect_outputs(self) -> None:
        self.assertEqual(
            self.run_deadlock(["detect", "safe.txt"]),
            (0, "No deadlock found.\n", ""),
        )
        self.assertEqual(
            self.run_deadlock(["detect", "unsafe.txt"]),
            (
                0,
                "Deadlock detected. Deadlocked processes: P0, P1\n"
                "Recovery suggestion: Terminate P0\n"
                "Preemption note: Preempt R1 from P1\n",
                "",
            ),
        )
        self.assertEqual(
            self.run_deadlock(["detect", "empty.txt"]),
            (0, "No deadlock found.\n", ""),
        )

    def test_banker_outputs(self) -> None:
        self.assertEqual(
            self.run_deadlock(["banker", "safe.txt"]),
            (
                0,
                "SAFE state. Safe sequence: P1 -> P3 -> P4 -> P0 -> P2\n",
                "",
            ),
        )
        self.assertEqual(
            self.run_deadlock(["banker", "unsafe.txt"]),
            (0, "UNSAFE state. Stuck processes: P0, P1\n", ""),
        )
        self.assertEqual(
            self.run_deadlock(["banker", "single.txt"]),
            (0, "SAFE state. Safe sequence: P0\n", ""),
        )
        self.assertEqual(
            self.run_deadlock(["banker", "empty.txt"]),
            (0, "SAFE state. Safe sequence: (none, no processes)\n", ""),
        )

    def test_load_errors(self) -> None:
        result, output, error = self.run_deadlock(["detect", "missing.txt"])
        self.assertEqual(result, 1)
        self.assertEqual(output, "")
        self.assertTrue(error.startswith("deadlock: "))
        self.assertEqual(len(error.splitlines()), 1)

        result, output, error = self.run_deadlock(["banker", "bad_dims.txt"])
        self.assertEqual(result, 1)
        self.assertEqual(output, "")
        self.assertIn("rows", error)
        self.assertEqual(len(error.splitlines()), 1)

    def test_usage_errors(self) -> None:
        usage = "usage: deadlock <detect|banker> <file>\n"
        for args in ([], ["unknown", "safe.txt"], ["detect"], ["detect", "safe.txt", "extra"]):
            with self.subTest(args=args):
                result, output, error = self.run_deadlock(args)
                self.assertEqual(result, 2)
                self.assertEqual(output, "")
                self.assertEqual(error, usage)

        result, output, error = self.run_deadlock(
            ["detect", "safe.txt", "--request"]
        )
        self.assertEqual((result, output, error), (2, "", usage))

    def test_commands_do_not_mutate_loaded_state(self) -> None:
        for subcommand in ("detect", "banker"):
            with self.subTest(subcommand=subcommand):
                state = load_resources(os.path.join(RESOURCE_DIR, "safe.txt"))
                before_available = state.available.copy()
                before_allocation = [row.copy() for row in state.allocation]
                with patch("sim.commands.load_resources", return_value=state):
                    result, output, error = self.run_deadlock(
                        [subcommand, "safe.txt"]
                    )
                self.assertEqual(result, 0)
                self.assertTrue(output)
                self.assertEqual(error, "")
                self.assertEqual(state.available, before_available)
                self.assertEqual(state.allocation, before_allocation)

    def test_help_lists_deadlock(self) -> None:
        output = io.StringIO()
        result = help_command(
            [],
            io.StringIO(),
            output,
            io.StringIO(),
            self.context,
        )
        self.assertEqual(result, 0)
        self.assertIn("deadlock\n", output.getvalue())
        self.assertIn("deadlock", REGISTRY)


if __name__ == "__main__":
    unittest.main()
