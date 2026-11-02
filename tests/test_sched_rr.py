"""Tests for Round-Robin scheduling and sched command integration."""

import io
import os
import tempfile
import unittest

from shell.context import ShellContext
from sim.commands import cmd_sched
from sim.gantt import merge_segments
from sim.loader import load_processes
from sim.metrics import averages, compute_metrics
from sim.pcb import Process
from sim.scheduler import fcfs, round_robin


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESS_DIR = os.path.join(ROOT, "data", "processes")


class RoundRobinTests(unittest.TestCase):
    def load_sample(self, filename: str) -> list[Process]:
        return load_processes(os.path.join(PROCESS_DIR, filename))

    def test_three_process_schedule_and_metrics(self) -> None:
        processes = [
            Process("P1", 0, 5, 1),
            Process("P2", 1, 3, 1),
            Process("P3", 2, 1, 1),
        ]
        segments = merge_segments(round_robin(processes, quantum=2))
        self.assertEqual(
            segments,
            [
                ("P1", 0, 2),
                ("P2", 2, 4),
                ("P3", 4, 5),
                ("P1", 5, 7),
                ("P2", 7, 8),
                ("P1", 8, 9),
            ],
        )
        self.assertEqual(
            {row["pid"]: row["completion"] for row in compute_metrics(processes, segments)},
            {"P1": 9, "P2": 8, "P3": 5},
        )
        self.assertEqual(
            tuple(round(value, 2) for value in averages(compute_metrics(processes, segments))),
            (6.33, 3.33),
        )

    def test_basic_sample_quantum_four_hand_calculation(self) -> None:
        processes = self.load_sample("p_basic.txt")
        # P1 runs 0-4, P2 4-8, P3 8-12, P4 12-16, then P1 16-20,
        # P3 20-24, P4 24-25, and P3 25-26. Completions are 20, 8,
        # 26, 25; turnarounds are 20, 7, 24, 22 (average 18.25) and
        # waiting times are 12, 3, 15, 17 (average 11.75).
        segments = merge_segments(round_robin(processes, quantum=4))
        self.assertEqual(
            segments,
            [
                ("P1", 0, 4),
                ("P2", 4, 8),
                ("P3", 8, 12),
                ("P4", 12, 16),
                ("P1", 16, 20),
                ("P3", 20, 24),
                ("P4", 24, 25),
                ("P3", 25, 26),
            ],
        )
        rows = compute_metrics(processes, segments)
        self.assertEqual(
            [row["completion"] for row in rows],
            [20, 8, 26, 25],
        )
        self.assertEqual(averages(rows), (18.25, 11.75))

    def test_arrival_at_completion_time_is_admitted(self) -> None:
        processes = [Process("P1", 0, 4, 1), Process("P2", 4, 2, 1)]
        self.assertEqual(
            merge_segments(round_robin(processes, quantum=4)),
            [("P1", 0, 4), ("P2", 4, 6)],
        )

    def test_arrival_at_quantum_end_precedes_requeued_process(self) -> None:
        processes = [Process("P1", 0, 6, 1), Process("P2", 2, 2, 1)]
        self.assertEqual(
            merge_segments(round_robin(processes, quantum=2)),
            [("P1", 0, 2), ("P2", 2, 4), ("P1", 4, 8)],
        )

    def test_idle_gap_single_process_and_empty_list(self) -> None:
        self.assertEqual(
            round_robin([Process("P1", 3, 2, 1)], quantum=4),
            [("IDLE", 0, 1), ("IDLE", 1, 2), ("IDLE", 2, 3), ("P1", 3, 4), ("P1", 4, 5)],
        )
        self.assertEqual(
            merge_segments(round_robin([Process("P1", 0, 9, 1)], quantum=4)),
            [("P1", 0, 9)],
        )
        self.assertEqual(round_robin([]), [])

    def test_large_quantum_behaves_like_fcfs(self) -> None:
        rr_processes = self.load_sample("p_basic.txt")
        fcfs_processes = self.load_sample("p_basic.txt")
        self.assertEqual(
            merge_segments(round_robin(rr_processes, quantum=100)),
            fcfs(fcfs_processes),
        )

    def test_quantum_one_rotates_ready_processes(self) -> None:
        processes = [Process("P1", 0, 2, 1), Process("P2", 0, 2, 1)]
        self.assertEqual(
            merge_segments(round_robin(processes, quantum=1)),
            [
                ("P1", 0, 1),
                ("P2", 1, 2),
                ("P1", 2, 3),
                ("P2", 3, 4),
            ],
        )

    def test_invalid_quantum_raises_and_list_is_reusable(self) -> None:
        for quantum in (0, -1):
            with self.subTest(quantum=quantum):
                with self.assertRaises(ValueError):
                    round_robin([Process("P1", 0, 1, 1)], quantum)

        processes = self.load_sample("p_basic.txt")
        self.assertEqual(merge_segments(round_robin(processes, 4))[0], ("P1", 0, 4))
        self.assertEqual(fcfs(processes)[0], ("P1", 0, 8))

    def test_trace_records_state_changes(self) -> None:
        events: list[str] = []
        round_robin([Process("P1", 0, 2, 1)], quantum=4, events=events)
        self.assertIn("t=0 P1 New -> Ready", events)
        self.assertIn("t=0 P1 Ready -> Running", events)
        self.assertIn("t=2 P1 Running -> Terminated", events)


class RoundRobinCommandTests(unittest.TestCase):
    def run_sched(self, args: list[str], cwd: str) -> tuple[int, str, str]:
        context = ShellContext()
        context.cwd = cwd
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = cmd_sched(args, io.StringIO(), stdout, stderr, context)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_sched_rr_quantum_and_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "input.txt")
            with open(path, "w", encoding="utf-8") as file:
                file.write("P1 0 5 1\nP2 1 3 1\nP3 2 1 1\n")

            result, output, error = self.run_sched(
                ["rr", "--quantum", "2", "input.txt"],
                directory,
            )
            self.assertEqual((result, error), (0, ""))
            self.assertIn("| P1 | P2 | P3 | P1 | P2 | P1 |", output)
            self.assertIn(
                "Average turnaround: 6.33   Average waiting: 3.33",
                output,
            )

            result, output, error = self.run_sched(
                ["--trace", "rr", "--quantum", "2", "input.txt"],
                directory,
            )
            self.assertEqual((result, error), (0, ""))
            self.assertIn("Trace:\n", output)
            self.assertIn("Ready -> Running", output)

    def test_sched_rejects_nonpositive_rr_quantum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "input.txt")
            with open(path, "w", encoding="utf-8") as file:
                file.write("P1 0 1 1\n")
            result, output, error = self.run_sched(
                ["rr", "--quantum", "0", "input.txt"],
                directory,
            )
        self.assertEqual(result, 2)
        self.assertEqual(output, "")
        self.assertEqual(
            error,
            "sched: --quantum requires a positive integer\n",
        )


if __name__ == "__main__":
    unittest.main()
