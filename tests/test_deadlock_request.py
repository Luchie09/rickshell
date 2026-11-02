"""Tests for in-memory banker resource requests."""

import io
import os
import unittest
from unittest.mock import patch

from shell.context import ShellContext
from sim.commands import cmd_deadlock
from sim.deadlock import request_resources
from sim.loader import load_resources


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCE_DIR = os.path.join(ROOT, "data", "resources")


class DeadlockRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ShellContext()
        self.context.cwd = RESOURCE_DIR
        self.safe_path = os.path.join(RESOURCE_DIR, "safe.txt")
        with open(self.safe_path, "rb") as resource_file:
            self.original_file = resource_file.read()

    def run_deadlock(self, args: list[str]):
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = cmd_deadlock(
            args,
            io.StringIO(),
            stdout,
            stderr,
            self.context,
        )
        return result, stdout.getvalue(), stderr.getvalue()

    def assert_file_unchanged(self) -> None:
        with open(self.safe_path, "rb") as resource_file:
            self.assertEqual(resource_file.read(), self.original_file)

    def test_request_granted_and_state_updated(self) -> None:
        state = load_resources(self.safe_path)
        outcome, sequence = request_resources(state, "P1", [1, 0, 2])
        self.assertEqual(
            (outcome, sequence),
            ("granted", ["P1", "P3", "P4", "P0", "P2"]),
        )
        self.assertEqual(state.allocation[1], [3, 0, 2])
        self.assertEqual(state.available, [2, 3, 0])

        result, output, error = self.run_deadlock(
            ["banker", "safe.txt", "--request", "P1", "1", "0", "2"]
        )
        self.assertEqual(result, 0)
        self.assertEqual(
            output,
            "Request granted. Safe sequence: P1 -> P3 -> P4 -> P0 -> P2\n",
        )
        self.assertEqual(error, "")
        self.assert_file_unchanged()

    def test_exceeded_request(self) -> None:
        result, output, error = self.run_deadlock(
            ["banker", "safe.txt", "--request", "P1", "2", "0", "0"]
        )
        self.assertEqual(result, 1)
        self.assertEqual(output, "")
        self.assertEqual(error, "error: P1 exceeded its maximum claim\n")
        self.assert_file_unchanged()

    def test_wait_request_marks_process_waiting(self) -> None:
        state = load_resources(self.safe_path)
        outcome, sequence = request_resources(state, "P2", [4, 0, 0])
        self.assertEqual((outcome, sequence), ("wait", []))
        self.assertEqual(state.process_states[2], "Waiting")
        self.assertEqual(state.available, [3, 3, 2])

        result, output, error = self.run_deadlock(
            ["banker", "safe.txt", "--request", "P2", "4", "0", "0"]
        )
        self.assertEqual(result, 0)
        self.assertEqual(
            output,
            "P2 must wait: request exceeds available resources. State: Waiting\n",
        )
        self.assertEqual(error, "")
        self.assert_file_unchanged()

    def test_unsafe_trial_is_denied_and_rolled_back(self) -> None:
        state = load_resources(self.safe_path)
        original_available = state.available.copy()
        original_allocation = [row.copy() for row in state.allocation]
        original_need = state.need()
        outcome, _sequence = request_resources(state, "P4", [3, 3, 0])
        self.assertEqual(outcome, "denied")
        self.assertEqual(state.available, original_available)
        self.assertEqual(state.allocation, original_allocation)
        self.assertEqual(state.need(), original_need)

        result, output, error = self.run_deadlock(
            ["banker", "safe.txt", "--request", "P4", "3", "3", "0"]
        )
        self.assertEqual(result, 0)
        self.assertEqual(
            output,
            "Request denied: granting it would leave the system in an "
            "UNSAFE state. Rolled back.\n",
        )
        self.assertEqual(error, "")
        self.assert_file_unchanged()

    def test_zero_vector_is_granted(self) -> None:
        result, output, error = self.run_deadlock(
            ["banker", "safe.txt", "--request", "P0", "0", "0", "0"]
        )
        self.assertEqual(result, 0)
        self.assertEqual(
            output,
            "Request granted. Safe sequence: P1 -> P3 -> P4 -> P0 -> P2\n",
        )
        self.assertEqual(error, "")
        self.assert_file_unchanged()

    def test_invalid_requests_return_usage_error(self) -> None:
        invalid_requests = [
            ["banker", "safe.txt", "--request", "P1", "1", "0"],
            ["banker", "safe.txt", "--request", "P1", "-1", "0", "0"],
            ["banker", "safe.txt", "--request", "P1", "x", "0", "0"],
            ["banker", "safe.txt", "--request", "P9", "0", "0", "0"],
        ]
        for args in invalid_requests:
            with self.subTest(args=args):
                result, output, error = self.run_deadlock(args)
                self.assertEqual(result, 2)
                self.assertEqual(output, "")
                self.assertTrue(error.startswith("deadlock: ") or error.startswith("usage:"))
                self.assertEqual(len(error.splitlines()), 1)
                self.assert_file_unchanged()

    def test_unsafe_file_request_does_not_raise(self) -> None:
        result, output, error = self.run_deadlock(
            ["banker", "unsafe.txt", "--request", "P0", "0", "0"]
        )
        self.assertEqual(result, 0)
        self.assertIn("Request denied:", output)
        self.assertEqual(error, "")

    def test_plain_banker_output_remains_unchanged(self) -> None:
        result, output, error = self.run_deadlock(["banker", "safe.txt"])
        self.assertEqual(result, 0)
        self.assertEqual(
            output,
            "SAFE state. Safe sequence: P1 -> P3 -> P4 -> P0 -> P2\n",
        )
        self.assertEqual(error, "")

    def test_request_handler_uses_only_loaded_state(self) -> None:
        state = load_resources(self.safe_path)
        with patch("sim.commands.load_resources", return_value=state):
            result, output, error = self.run_deadlock(
                ["banker", "safe.txt", "--request", "P1", "1", "0", "2"]
            )
        self.assertEqual(result, 0)
        self.assertIn("Request granted.", output)
        self.assertEqual(error, "")
        self.assertEqual(state.allocation[1], [3, 0, 2])
        self.assert_file_unchanged()


if __name__ == "__main__":
    unittest.main()
