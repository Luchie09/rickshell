"""Tests for multilevel queue scheduling and its sched command integration."""

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
from sim.scheduler import fcfs, multilevel_queue


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESS_DIR = os.path.join(ROOT, "data", "processes")


class MultilevelQueueTests(unittest.TestCase):
    def test_arriving_q0_process_preempts_q1(self) -> None:
        processes = [
            Process("P1", 0, 6, 3),
            Process("P2", 2, 3, 1),
            Process("P3", 3, 5, 2),
        ]
        segments = merge_segments(multilevel_queue(processes))
        self.assertEqual(
            segments,
            [
                ("P1", 0, 2),
                ("P2", 2, 5),
                ("P3", 5, 10),
                ("P1", 10, 14),
            ],
        )
        rows = compute_metrics(processes, segments)
        self.assertEqual(
            [row["completion"] for row in rows],
            [14, 5, 10],
        )
        self.assertEqual(
            [row["waiting"] for row in rows],
            [8, 0, 2],
        )
        self.assertEqual(
            tuple(round(value, 2) for value in averages(rows)),
            (8.0, 3.33),
        )

    def test_round_robin_quantum_and_boundary_requeue_order(self) -> None:
        processes = [
            Process("P1", 0, 6, 1),
            Process("P2", 0, 5, 2),
        ]
        default_segments = merge_segments(multilevel_queue(processes))
        self.assertEqual(
            default_segments,
            [
                ("P1", 0, 4),
                ("P2", 4, 8),
                ("P1", 8, 10),
                ("P2", 10, 11),
            ],
        )
        default_rows = compute_metrics(processes, default_segments)
        self.assertEqual(
            [row["completion"] for row in default_rows],
            [10, 11],
        )
        self.assertEqual(
            [row["waiting"] for row in default_rows],
            [4, 6],
        )
        self.assertEqual(averages(default_rows), (10.5, 5.0))

        # With quantum 2, each newly ready Q0 process queues ahead of a
        # process whose quantum just expired at that same boundary.
        short_segments = merge_segments(multilevel_queue(processes, quantum=2))
        self.assertEqual(
            short_segments,
            [
                ("P1", 0, 2),
                ("P2", 2, 4),
                ("P1", 4, 6),
                ("P2", 6, 8),
                ("P1", 8, 10),
                ("P2", 10, 11),
            ],
        )

    def test_basic_sample_schedule_and_metrics(self) -> None:
        processes = load_processes(
            os.path.join(PROCESS_DIR, "p_basic.txt")
        )
        segments = merge_segments(multilevel_queue(processes))
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
        rows = compute_metrics(processes, segments)
        self.assertEqual(
            [row["completion"] for row in rows],
            [16, 8, 26, 17],
        )
        self.assertEqual(
            [row["waiting"] for row in rows],
            [8, 3, 15, 9],
        )
        self.assertEqual(averages(rows), (15.25, 8.75))

    def test_single_empty_idle_gap_and_q1_fcfs(self) -> None:
        self.assertEqual(
            merge_segments(multilevel_queue([Process("P1", 0, 3, 2)])),
            [("P1", 0, 3)],
        )
        self.assertEqual(multilevel_queue([]), [])

        self.assertEqual(
            merge_segments(multilevel_queue([Process("P1", 3, 2, 1)])),
            [("IDLE", 0, 3), ("P1", 3, 5)],
        )

        q1_processes = [
            Process("P1", 0, 3, 3),
            Process("P2", 1, 2, 4),
            Process("P3", 2, 1, 7),
        ]
        self.assertEqual(
            merge_segments(multilevel_queue(q1_processes)),
            fcfs(q1_processes),
        )

    def test_trace_records_transitions_in_order(self) -> None:
        processes = [
            Process("P1", 0, 4, 3),
            Process("P2", 1, 2, 1),
        ]
        events: list[str] = []
        multilevel_queue(processes, events=events)
        self.assertLess(
            events.index("t=1 P1 Running -> Ready"),
            events.index("t=1 P2 Ready -> Running"),
        )
        self.assertIn("t=0 P1 New -> Ready", events)
        self.assertIn("t=1 P2 New -> Ready", events)
        self.assertIn("t=3 P2 Running -> Terminated", events)


class MultilevelQueueCommandTests(unittest.TestCase):
    def run_sched(self, args: list[str], cwd: str) -> tuple[int, str, str]:
        context = ShellContext()
        context.cwd = cwd
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = cmd_sched(args, io.StringIO(), stdout, stderr, context)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_sched_mlq_output_trace_and_empty_input(self) -> None:
        result, output, error = self.run_sched(
            ["mlq", "data/processes/p_basic.txt"], ROOT
        )
        self.assertEqual((result, error), (0, ""))
        self.assertIn("| P1 | P2 | P4 | P1 | P4 | P3 |", output)
        self.assertIn(
            "0    4    8    12   16   17   26",
            output,
        )
        self.assertIn(
            "Average turnaround: 15.25   Average waiting: 8.75",
            output,
        )

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "q0.txt")
            with open(path, "w", encoding="utf-8") as process_file:
                process_file.write("P1 0 6 1\nP2 0 5 2\n")

            traced = self.run_sched(
                ["mlq", "--quantum", "2", "--trace", "q0.txt"],
                directory,
            )
            self.assertEqual((traced[0], traced[2]), (0, ""))
            self.assertIn("Trace:\n", traced[1])
            self.assertIn("Running -> Ready", traced[1])
            self.assertIn("| P1 | P2 | P1 | P2 | P1 | P2 |", traced[1])

            empty_path = os.path.join(directory, "empty.txt")
            with open(empty_path, "w", encoding="utf-8") as process_file:
                process_file.write("# no processes\n")
            self.assertEqual(
                self.run_sched(["mlq", "empty.txt"], directory),
                (0, "No processes to schedule.\n", ""),
            )


if __name__ == "__main__":
    unittest.main()
