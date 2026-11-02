"""Tests for comparing the scheduling algorithms."""

import io
import os
import tempfile
import unittest

from shell.builtins import REGISTRY
from shell.context import ShellContext
from compare.compare import cmd_compare


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESS_DIR = os.path.join(ROOT, "data", "processes")


class CompareCommandTests(unittest.TestCase):
    def run_compare(
        self,
        args: list[str],
        cwd: str = ROOT,
    ) -> tuple[int, str, str]:
        context = ShellContext()
        context.cwd = cwd
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = cmd_compare(args, io.StringIO(), stdout, stderr, context)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_p_basic_metrics_and_best_algorithms(self) -> None:
        result, output, error = self.run_compare(
            ["data/processes/p_basic.txt"]
        )
        self.assertEqual((result, error), (0, ""))
        for expected in (
            "FCFS      |        8.75 |         15.25",
            "SJN       |        7.75 |         14.25",
            "Priority  |        7.75 |         14.25",
            "RR        |       11.75 |         18.25",
            "MLQ       |        8.75 |         15.25",
            "MLFQ      |       13.00 |         19.50",
            "Best avg waiting: SJN, Priority",
            "Best avg turnaround: SJN, Priority",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, output)
        self.assertIn("FCFS     ######### 8.75", output)

    def test_empty_and_single_process(self) -> None:
        self.assertEqual(
            self.run_compare(["data/processes/p_empty.txt"]),
            (0, "No processes to schedule.\n", ""),
        )

        result, output, error = self.run_compare(
            ["data/processes/p_single.txt"]
        )
        self.assertEqual((result, error), (0, ""))
        self.assertIn("FCFS      |        0.00 |          5.00", output)
        self.assertIn("MLFQ      |        0.00 |          5.00", output)

    def test_save_markdown_creates_parent_and_lists_algorithms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result, output, error = self.run_compare(
                [
                    os.path.join(PROCESS_DIR, "p_basic.txt"),
                    "--save",
                    os.path.join("reports", "comparison.md"),
                ],
                directory,
            )
            self.assertEqual((result, error), (0, ""))
            report_path = os.path.join(directory, "reports", "comparison.md")
            with open(report_path, "r", encoding="utf-8") as report_file:
                report = report_file.read()
            for name in ("FCFS", "SJN", "Priority", "RR", "MLQ", "MLFQ"):
                self.assertIn(name, report)
            self.assertIn("Best avg waiting", report)
            self.assertIn("Best avg turnaround", report)

    def test_missing_file_bad_quantum_save_error_and_registration(self) -> None:
        result, output, error = self.run_compare(["missing.txt"])
        self.assertNotEqual(result, 0)
        self.assertEqual(output, "")
        self.assertTrue(error.startswith("compare: "))

        result, output, error = self.run_compare(
            ["data/processes/p_basic.txt", "--quantum", "0"]
        )
        self.assertNotEqual(result, 0)
        self.assertEqual(output, "")
        self.assertTrue(error.startswith("compare: "))

        result, output, error = self.run_compare(
            [
                os.path.join(PROCESS_DIR, "p_basic.txt"),
                "--save",
                "C:\\invalid\\\0.md",
            ]
        )
        self.assertNotEqual(result, 0)
        self.assertEqual(output, "")
        self.assertTrue(error.startswith("compare: "))
        self.assertIn("compare", REGISTRY)


if __name__ == "__main__":
    unittest.main()
