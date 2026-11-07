"""Tests for the optional Request matrix used by deadlock detection."""

import io
import os
import tempfile
import unittest

from shell.context import ShellContext
from sim.commands import cmd_deadlock
from sim.deadlock import ResourceState, detect, recovery_suggestion, safety_check
from sim.loader import LoaderError, load_resources
from sim.scheduler import multilevel_feedback_queue
from sim.pcb import Process


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCE_DIR = os.path.join(ROOT, "data", "resources")


def run_deadlock(args: list[str], cwd: str) -> tuple[int, str, str]:
    context = ShellContext()
    context.cwd = cwd
    stdout = io.StringIO()
    stderr = io.StringIO()
    result = cmd_deadlock(args, io.StringIO(), stdout, stderr, context)
    return result, stdout.getvalue(), stderr.getvalue()


class RequestMatrixLoaderTests(unittest.TestCase):
    def test_sample_file_loads_request_rows(self) -> None:
        state = load_resources(os.path.join(RESOURCE_DIR, "detect_request.txt"))
        self.assertEqual((state.n, state.m), (3, 2))
        self.assertEqual(state.available, [0, 0])
        self.assertEqual(state.request, [[0, 0], [1, 0], [0, 0]])

    def test_files_without_request_keep_none(self) -> None:
        state = load_resources(os.path.join(RESOURCE_DIR, "safe.txt"))
        self.assertIsNone(state.request)

    def test_wrong_row_count_mentions_both_options(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "bad.txt")
            with open(path, "w", encoding="utf-8") as resource_file:
                # n=2 needs 5 rows (or 7 with Request); 6 is neither.
                resource_file.write("2 1\n0\n0\n1\n1\n1\n0\n")
            with self.assertRaisesRegex(LoaderError, "expected 5 data rows"):
                load_resources(path)

    def test_copy_keeps_request_independent(self) -> None:
        state = ResourceState(1, 1, [[0]], [[1]], [1], request=[[1]])
        copied = state.copy()
        copied.request[0][0] = 0
        self.assertEqual(state.request, [[1]])


class RequestMatrixDetectionTests(unittest.TestCase):
    def test_unsafe_but_not_deadlocked(self) -> None:
        # Need = P0 1 2, P1 2 1, P2 1 1 with Available 0 0: Banker gets stuck.
        # Requests 0 0, 1 0, 0 0 can be served: P0 -> Work 1 0,
        # P1 -> Work 1 1, P2 -> Work 2 2. So there is no deadlock.
        state = load_resources(os.path.join(RESOURCE_DIR, "detect_request.txt"))
        safe, _sequence, stuck = safety_check(state)
        self.assertFalse(safe)
        self.assertEqual(stuck, ["P0", "P1", "P2"])
        self.assertEqual(detect(state), [])

    def test_request_matrix_can_show_deadlock(self) -> None:
        # Each process holds one unit and requests the other one's unit.
        state = ResourceState(
            2, 2,
            [[1, 0], [0, 1]],
            [[1, 1], [1, 1]],
            [0, 0],
            request=[[0, 1], [1, 0]],
        )
        self.assertEqual(detect(state), ["P0", "P1"])
        order, note = recovery_suggestion(state, ["P0", "P1"])
        self.assertEqual(order, ["P0"])
        self.assertEqual(note, "Preempt R1 from P1")

    def test_detect_command_reports_request_matrix(self) -> None:
        self.assertEqual(
            run_deadlock(["detect", "detect_request.txt"], RESOURCE_DIR),
            (
                0,
                "Using the Request matrix from the file.\nNo deadlock found.\n",
                "",
            ),
        )

    def test_banker_ignores_request_matrix(self) -> None:
        self.assertEqual(
            run_deadlock(["banker", "detect_request.txt"], RESOURCE_DIR),
            (0, "UNSAFE state. Stuck processes: P0, P1, P2\n", ""),
        )


class MlfqDemotionTraceTests(unittest.TestCase):
    def test_trace_names_the_new_level(self) -> None:
        # Burst 7: 2 units at Level 0, 4 at Level 1, last unit at Level 2.
        events: list[str] = []
        multilevel_feedback_queue([Process("P1", 0, 7, 1)], events=events)
        self.assertIn("t=2 P1 demoted to Level 1", events)
        self.assertIn("t=6 P1 demoted to Level 2", events)
        self.assertEqual(
            events.index("t=2 P1 demoted to Level 1"),
            events.index("t=2 P1 Running -> Ready") + 1,
        )


if __name__ == "__main__":
    unittest.main()
