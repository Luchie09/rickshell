"""Tests for deadlock recovery suggestions."""

import io
import os
import unittest

from shell.context import ShellContext
from sim.commands import cmd_deadlock
from sim.deadlock import recovery_suggestion
from sim.loader import load_resources


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCE_DIR = os.path.join(ROOT, "data", "resources")


class DeadlockRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ShellContext()
        self.context.cwd = RESOURCE_DIR

    def run_detect(self, filename: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = cmd_deadlock(
            ["detect", filename],
            io.StringIO(),
            stdout,
            stderr,
            self.context,
        )
        return result, stdout.getvalue(), stderr.getvalue()

    def test_unsafe_sample_recovery_and_preemption(self) -> None:
        state = load_resources(os.path.join(RESOURCE_DIR, "unsafe.txt"))
        before = state.copy()
        order, note = recovery_suggestion(state, ["P0", "P1"])
        self.assertEqual(order, ["P0"])
        self.assertEqual(note, "Preempt R1 from P1")
        self.assertEqual(state, before)

        unsafe_path = os.path.join(RESOURCE_DIR, "unsafe.txt")
        with open(unsafe_path, "rb") as resource_file:
            original_file = resource_file.read()
        result, output, error = self.run_detect("unsafe.txt")
        self.assertEqual(result, 0)
        self.assertEqual(error, "")
        self.assertEqual(
            output,
            "Deadlock detected. Deadlocked processes: P0, P1\n"
            "Recovery suggestion: Terminate P0\n"
            "Preemption note: Preempt R1 from P1\n",
        )
        with open(unsafe_path, "rb") as resource_file:
            self.assertEqual(resource_file.read(), original_file)

    def test_chain_requires_two_terminations(self) -> None:
        state = load_resources(os.path.join(RESOURCE_DIR, "deadlock_chain.txt"))
        deadlocked = ["P0", "P1", "P2", "P3"]
        order, _note = recovery_suggestion(state, deadlocked)
        self.assertEqual(order, ["P0", "P1"])

        result, output, error = self.run_detect("deadlock_chain.txt")
        self.assertEqual(result, 0)
        self.assertEqual(error, "")
        self.assertIn("Recovery suggestion: Terminate P0, then P1\n", output)

    def test_safe_state_has_no_recovery_lines_or_mutation(self) -> None:
        path = os.path.join(RESOURCE_DIR, "safe.txt")
        state = load_resources(path)
        before = state.copy()
        with open(path, "rb") as resource_file:
            original_file = resource_file.read()

        result, output, error = self.run_detect("safe.txt")
        self.assertEqual((result, error), (0, ""))
        self.assertEqual(output, "No deadlock found.\n")
        self.assertEqual(state, before)
        with open(path, "rb") as resource_file:
            self.assertEqual(resource_file.read(), original_file)

    def test_single_and_empty_states_do_not_raise(self) -> None:
        for filename in ("single.txt", "empty.txt"):
            with self.subTest(filename=filename):
                result, output, error = self.run_detect(filename)
                self.assertEqual((result, error), (0, ""))
                self.assertEqual(output, "No deadlock found.\n")


if __name__ == "__main__":
    unittest.main()
