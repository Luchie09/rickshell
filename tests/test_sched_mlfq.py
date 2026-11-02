"""Tests for multilevel feedback queue scheduling."""

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
from sim.scheduler import fcfs, multilevel_feedback_queue


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESS_DIR = os.path.join(ROOT, "data", "processes")


class MultilevelFeedbackQueueTests(unittest.TestCase):
    def load_sample(self, filename: str) -> list[Process]:
        return load_processes(os.path.join(PROCESS_DIR, filename))

    def test_three_process_schedule_and_metrics(self) -> None:
        processes = [
            Process("P1", 0, 7, 1),
            Process("P2", 1, 3, 1),
            Process("P3", 2, 1, 1),
        ]
        # P1 runs 0-2, P2 2-4, P3 4-5, P1 5-9, P2 9-10, P1 10-11.
        segments = merge_segments(multilevel_feedback_queue(processes))
        self.assertEqual(
            segments,
            [
                ("P1", 0, 2),
                ("P2", 2, 4),
                ("P3", 4, 5),
                ("P1", 5, 9),
                ("P2", 9, 10),
                ("P1", 10, 11),
            ],
        )
        rows = compute_metrics(processes, segments)
        self.assertEqual(
            [row["completion"] for row in rows],
            [11, 10, 5],
        )
        self.assertEqual(
            tuple(round(value, 2) for value in averages(rows)),
            (7.67, 4.0),
        )

    def test_level_zero_arrival_preempts_level_two(self) -> None:
        processes = [Process("P1", 0, 10, 1), Process("P2", 7, 2, 1)]
        events: list[str] = []
        segments = merge_segments(
            multilevel_feedback_queue(processes, events=events)
        )
        self.assertEqual(
            segments,
            [("P1", 0, 7), ("P2", 7, 9), ("P1", 9, 12)],
        )
        self.assertEqual(
            tuple(
                round(value, 2)
                for value in averages(compute_metrics(processes, segments))
            ),
            (7.0, 1.0),
        )
        self.assertLess(
            events.index("t=7 P1 Running -> Ready"),
            events.index("t=7 P2 Ready -> Running"),
        )

    def test_preemption_gives_a_fresh_quantum(self) -> None:
        processes = [Process("P1", 0, 8, 1), Process("P2", 3, 1, 1)]
        events: list[str] = []
        segments = merge_segments(
            multilevel_feedback_queue(processes, events=events)
        )
        self.assertEqual(
            segments,
            [("P1", 0, 3), ("P2", 3, 4), ("P1", 4, 9)],
        )
        self.assertEqual(
            tuple(
                round(value, 2)
                for value in averages(compute_metrics(processes, segments))
            ),
            (5.0, 0.5),
        )
        self.assertIn("t=8 P1 Running -> Ready", events)
        self.assertNotIn("t=7 P1 Running -> Ready", events)

    def test_basic_sample_schedule_and_metrics(self) -> None:
        processes = self.load_sample("p_basic.txt")
        # P1/P2/P3/P4 each take level 0 first; then level 1 is served,
        # followed by P1 and P3 finishing at level 2.
        segments = merge_segments(multilevel_feedback_queue(processes))
        self.assertEqual(
            segments,
            [
                ("P1", 0, 2),
                ("P2", 2, 4),
                ("P3", 4, 6),
                ("P4", 6, 8),
                ("P1", 8, 12),
                ("P2", 12, 14),
                ("P3", 14, 18),
                ("P4", 18, 21),
                ("P1", 21, 23),
                ("P3", 23, 26),
            ],
        )
        rows = compute_metrics(processes, segments)
        self.assertEqual(
            [row["completion"] for row in rows],
            [23, 14, 26, 21],
        )
        self.assertEqual(averages(rows), (19.5, 13.0))

    def test_priority_is_ignored_and_new_processes_keep_input_order(self) -> None:
        processes = [Process("P1", 0, 3, 5), Process("P2", 0, 3, 1)]
        self.assertEqual(
            merge_segments(multilevel_feedback_queue(processes)),
            [("P1", 0, 2), ("P2", 2, 4), ("P1", 4, 5), ("P2", 5, 6)],
        )

    def test_short_bursts_match_fcfs_and_finish_without_demotion(self) -> None:
        processes = [Process("P1", 0, 2, 1), Process("P2", 0, 2, 1)]
        events: list[str] = []
        self.assertEqual(
            merge_segments(multilevel_feedback_queue(processes, events=events)),
            [("P1", 0, 2), ("P2", 2, 4)],
        )
        self.assertNotIn("Running -> Ready", "\n".join(events))

    def test_idle_single_empty_and_reuse(self) -> None:
        self.assertEqual(
            merge_segments(
                multilevel_feedback_queue([Process("P1", 3, 2, 1)])
            ),
            [("IDLE", 0, 3), ("P1", 3, 5)],
        )
        self.assertEqual(
            merge_segments(
                multilevel_feedback_queue([Process("P1", 0, 9, 1)])
            ),
            [("P1", 0, 9)],
        )
        self.assertEqual(multilevel_feedback_queue([]), [])

        reusable = [Process("P1", 0, 5, 1), Process("P2", 1, 2, 1)]
        mlfq_segments = multilevel_feedback_queue(reusable)
        fcfs_segments = fcfs(reusable)
        self.assertEqual(merge_segments(mlfq_segments)[0], ("P1", 0, 2))
        self.assertEqual(fcfs_segments, [("P1", 0, 5), ("P2", 5, 7)])


class MultilevelFeedbackQueueCommandTests(unittest.TestCase):
    def test_sched_mlfq_trace_and_ignored_quantum(self) -> None:
        source_processes = [
            Process("P1", 0, 7, 1),
            Process("P2", 1, 3, 1),
            Process("P3", 2, 1, 1),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "input.txt")
            with open(path, "w", encoding="utf-8") as file:
                for process in source_processes:
                    file.write(
                        f"{process.pid} {process.arrival} "
                        f"{process.burst} {process.priority}\n"
                    )

            context = ShellContext()
            context.cwd = directory

            def run(args: list[str]) -> tuple[int, str, str]:
                stdout = io.StringIO()
                stderr = io.StringIO()
                result = cmd_sched(
                    args,
                    io.StringIO(),
                    stdout,
                    stderr,
                    context,
                )
                return result, stdout.getvalue(), stderr.getvalue()

            result, output, error = run(["mlfq", "input.txt"])
            self.assertEqual((result, error), (0, ""))
            self.assertIn("| P1 | P2 | P3 | P1 | P2 | P1 |", output)
            self.assertIn(
                "Average turnaround: 7.67   Average waiting: 4.00",
                output,
            )

            trace_result, trace_output, trace_error = run(
                ["mlfq", "--trace", "input.txt"]
            )
            self.assertEqual((trace_result, trace_error), (0, ""))
            self.assertIn("Trace:\n", trace_output)
            self.assertIn("Running -> Ready", trace_output)

            quantum_result, quantum_output, quantum_error = run(
                ["mlfq", "--quantum", "3", "input.txt"]
            )
            self.assertEqual((quantum_result, quantum_error), (0, ""))
            self.assertEqual(quantum_output, output)


if __name__ == "__main__":
    unittest.main()
