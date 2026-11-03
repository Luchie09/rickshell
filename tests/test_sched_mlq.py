"""Tests for multilevel queue scheduling."""

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
from sim.scheduler import fcfs, multilevel_queue, round_robin


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESS_DIR = os.path.join(ROOT, "data", "processes")


class MultilevelQueueTests(unittest.TestCase):
    def load_sample(self, filename: str) -> list[Process]:
        return load_processes(os.path.join(PROCESS_DIR, filename))

    def test_preemption_queue_order_and_metrics(self) -> None:
        processes = [
            Process("P1", 0, 4, 3),
            Process("P2", 1, 3, 1),
            Process("P3", 2, 2, 2),
            Process("P4", 3, 2, 4),
        ]
        segments = merge_segments(multilevel_queue(processes, quantum=2))
        self.assertEqual(
            segments,
            [
                ("P1", 0, 1),
                ("P2", 1, 3),
                ("P3", 3, 5),
                ("P2", 5, 6),
                ("P1", 6, 9),
                ("P4", 9, 11),
            ],
        )
        rows = compute_metrics(processes, segments)
        self.assertEqual(
            [row["completion"] for row in rows],
            [9, 6, 5, 11],
        )
        self.assertEqual(averages(rows), (6.25, 3.5))

    def test_preemption_trace_order_and_start_time(self) -> None:
        processes = [
            Process("P1", 0, 4, 3),
            Process("P2", 1, 3, 1),
            Process("P3", 2, 2, 2),
            Process("P4", 3, 2, 4),
        ]
        events: list[str] = []
        multilevel_queue(processes, quantum=2, events=events)
        preempted = events.index("t=1 P1 Running -> Ready")
        dispatched = events.index("t=1 P2 Ready -> Running")
        self.assertLess(preempted, dispatched)
        self.assertEqual(processes[0].start_time, 0)

    def test_basic_sample_and_metrics(self) -> None:
        processes = self.load_sample("p_basic.txt")
        segments = merge_segments(multilevel_queue(processes, quantum=4))
        self.assertEqual(
            segments,
            [
                ("P1", 0, 4),
                ("P2", 4, 8),
                ("P4", 8, 12),
                ("P1", 12, 16),
                ("P4", 16, 17),
                ("P3", 17, 26),
            ],
        )
        self.assertEqual(
            tuple(
                round(value, 2)
                for value in averages(compute_metrics(processes, segments))
            ),
            (15.25, 8.75),
        )

    def test_q1_is_fcfs(self) -> None:
        processes = [Process("P1", 0, 3, 3), Process("P2", 1, 2, 4)]
        self.assertEqual(
            merge_segments(multilevel_queue(processes)),
            [("P1", 0, 3), ("P2", 3, 5)],
        )

    def test_q0_matches_round_robin(self) -> None:
        mlq_processes = [
            Process("P1", 0, 5, 1),
            Process("P2", 1, 3, 1),
            Process("P3", 2, 1, 1),
        ]
        rr_processes = [
            Process("P1", 0, 5, 1),
            Process("P2", 1, 3, 1),
            Process("P3", 2, 1, 1),
        ]
        self.assertEqual(
            merge_segments(multilevel_queue(mlq_processes, quantum=2)),
            merge_segments(round_robin(rr_processes, quantum=2)),
        )

    def test_q1_waits_until_q0_is_empty(self) -> None:
        processes = [Process("P1", 0, 2, 3), Process("P2", 0, 2, 1)]
        self.assertEqual(
            merge_segments(multilevel_queue(processes)),
            [("P2", 0, 2), ("P1", 2, 4)],
        )

    def test_preempted_q1_process_returns_to_head(self) -> None:
        processes = [
            Process("P1", 0, 5, 3),
            Process("P2", 1, 2, 3),
            Process("P3", 2, 1, 1),
        ]
        # P1 is interrupted at 2; Q0's P3 runs 2-3, then P1 resumes
        # 3-6 before P2 runs 6-8 because the interrupted task heads Q1.
        self.assertEqual(
            merge_segments(multilevel_queue(processes, quantum=2)),
            [("P1", 0, 2), ("P3", 2, 3), ("P1", 3, 6), ("P2", 6, 8)],
        )

    def test_idle_single_empty_invalid_quantum_and_reuse(self) -> None:
        self.assertEqual(
            merge_segments(
                multilevel_queue([Process("P1", 3, 2, 1)], quantum=4)
            ),
            [("IDLE", 0, 3), ("P1", 3, 5)],
        )
        self.assertEqual(
            merge_segments(multilevel_queue([Process("P1", 0, 5, 4)])),
            [("P1", 0, 5)],
        )
        self.assertEqual(multilevel_queue([]), [])

        for quantum in (0, -1):
            with self.subTest(quantum=quantum), self.assertRaises(ValueError):
                multilevel_queue([Process("P1", 0, 1, 1)], quantum)

        reusable = [Process("P1", 0, 4, 1), Process("P2", 1, 2, 3)]
        mlq_segments = multilevel_queue(reusable, quantum=2)
        fcfs_segments = fcfs(reusable)
        self.assertEqual(mlq_segments[0], ("P1", 0, 1))
        self.assertEqual(fcfs_segments[0], ("P1", 0, 4))


class MultilevelQueueCommandTests(unittest.TestCase):
    def test_sched_command_runs_mlq_with_quantum_and_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "input.txt")
            with open(path, "w", encoding="utf-8") as file:
                file.write(
                    "P1 0 4 3\n"
                    "P2 1 3 1\n"
                    "P3 2 2 2\n"
                    "P4 3 2 4\n"
                )

            context = ShellContext()
            context.cwd = directory
            stdout = io.StringIO()
            stderr = io.StringIO()
            result = cmd_sched(
                ["mlq", "--quantum", "2", "input.txt"],
                io.StringIO(),
                stdout,
                stderr,
                context,
            )
            self.assertEqual((result, stderr.getvalue()), (0, ""))
            self.assertIn("| P1 | P2 | P3 | P2 | P1 | P4 |", stdout.getvalue())
            self.assertIn(
                "Average turnaround: 6.25   Average waiting: 3.50",
                stdout.getvalue(),
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            result = cmd_sched(
                ["--trace", "mlq", "--quantum", "2", "input.txt"],
                io.StringIO(),
                stdout,
                stderr,
                context,
            )
            self.assertEqual(result, 0)
            self.assertIn("Trace:\n", stdout.getvalue())
            self.assertIn("Running -> Ready", stdout.getvalue())

if __name__ == "__main__":
    unittest.main()
