"""Tests for the sched shell command."""

import io
import os
import unittest

from shell.builtins import REGISTRY
from shell.builtins.system import help_command
from shell.context import ShellContext
from sim.commands import cmd_sched


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESS_DIR = os.path.join(ROOT, "data", "processes")


class SchedulerCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ShellContext()
        self.context.cwd = ROOT

    def run_sched(self, args: list[str]) -> tuple[int, str, str]:
        stdin = io.StringIO()
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = cmd_sched(args, stdin, stdout, stderr, self.context)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_fcfs_output_and_process_states(self) -> None:
        result, output, error = self.run_sched(
            ["fcfs", "data/processes/p_basic.txt"]
        )
        self.assertEqual((result, error), (0, ""))
        self.assertIn("| P1 | P2 | P3 | P4 |", output)
        self.assertIn("0    8    12   21   26", output)
        self.assertIn(
            "Average turnaround: 15.25   Average waiting: 8.75",
            output,
        )
        before, after = output.split("Process table (after run):\n")
        first_table = before.split("Process table (before run):\n", 1)[1].split(
            "\n\n", 1
        )[0]
        self.assertEqual(first_table.count("New"), 4)
        self.assertEqual(after.count("Terminated"), 4)

    def test_sjn_output(self) -> None:
        result, output, error = self.run_sched(
            ["sjn", "data/processes/p_basic.txt"]
        )
        self.assertEqual((result, error), (0, ""))
        self.assertIn("| P1 | P2 | P4 | P3 |", output)
        self.assertIn("0    8    12   17   26", output)
        self.assertIn(
            "Average turnaround: 14.25   Average waiting: 7.75",
            output,
        )

    def test_priority_output_with_idle_gap(self) -> None:
        result, output, error = self.run_sched(
            ["priority", "data/processes/p_idle_gap.txt"]
        )
        self.assertEqual((result, error), (0, ""))
        self.assertIn("| IDLE | P1 | P2 |", output)
        self.assertIn("Average turnaround: 4.00", output)
        self.assertIn("Average waiting: 1.00", output)

    def test_empty_and_single_process_inputs(self) -> None:
        self.assertEqual(
            self.run_sched(["fcfs", "data/processes/p_empty.txt"]),
            (0, "No processes to schedule.\n", ""),
        )
        result, output, error = self.run_sched(
            ["fcfs", "data/processes/p_single.txt"]
        )
        self.assertEqual((result, error), (0, ""))
        self.assertIn("| P1 |", output)
        self.assertIn("0    5", output)

    def assert_usage_error(self, args: list[str], expected_message: str) -> None:
        result, output, error = self.run_sched(args)
        self.assertEqual(result, 2)
        self.assertEqual(output, "")
        self.assertEqual(error, f"sched: {expected_message}\n")

    def test_usage_and_argument_errors(self) -> None:
        usage = (
            "usage: sched <fcfs|sjn|priority|rr|mlq|mlfq> "
            "[--quantum N] [--trace] <file>"
        )
        self.assert_usage_error([], usage)
        self.assert_usage_error(["fcfs"], usage)
        self.assert_usage_error(["fifo"], "unknown algorithm 'fifo'")
        self.assert_usage_error(["--bogus"], "unknown option '--bogus'")
        self.assert_usage_error(
            ["--quantum", "0", "fcfs", "p_basic.txt"],
            "--quantum requires a positive integer",
        )
        self.assert_usage_error(
            ["--quantum", "abc", "fcfs", "p_basic.txt"],
            "--quantum requires a positive integer",
        )
        self.assert_usage_error(
            ["fcfs", "--quantum"],
            "--quantum requires a positive integer",
        )
        self.assert_usage_error(
            ["fcfs", "p_basic.txt", "extra"],
            "too many arguments",
        )

    def test_load_errors(self) -> None:
        result, output, error = self.run_sched(
            ["fcfs", "data/processes/missing.txt"]
        )
        self.assertEqual(result, 1)
        self.assertEqual(output, "")
        self.assertEqual(len(error.splitlines()), 1)
        self.assertIn("No such file or directory", error)

        result, output, error = self.run_sched(
            ["fcfs", "data/processes/p_bad_line.txt"]
        )
        self.assertEqual(result, 1)
        self.assertEqual(output, "")
        self.assertEqual(len(error.splitlines()), 1)
        self.assertIn("line 3:", error)

    def test_options_are_accepted_in_any_order(self) -> None:
        first = self.run_sched(
            ["fcfs", "--trace", "data/processes/p_single.txt"]
        )
        second = self.run_sched(
            ["--trace", "fcfs", "data/processes/p_single.txt"]
        )
        self.assertEqual(first, second)
        self.assertEqual(first[0], 0)
        self.assertEqual(first[2], "")

    def test_relative_path_from_process_directory(self) -> None:
        self.context.cwd = PROCESS_DIR
        result, output, error = self.run_sched(["fcfs", "p_single.txt"])
        self.assertEqual((result, error), (0, ""))
        self.assertIn("| P1 |", output)

    def test_help_lists_sched(self) -> None:
        output = io.StringIO()
        result = help_command(
            [],
            io.StringIO(),
            output,
            io.StringIO(),
            self.context,
        )
        self.assertEqual(result, 0)
        self.assertIn("sched\n", output.getvalue())
        self.assertIn("sched", REGISTRY)


if __name__ == "__main__":
    unittest.main()
