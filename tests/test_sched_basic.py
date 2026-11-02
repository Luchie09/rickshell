"""Tests for FCFS, SJN, and non-preemptive priority scheduling."""

import os
import unittest

from sim.loader import load_processes
from sim.metrics import averages, compute_metrics
from sim.metrics import Segment
from sim.pcb import Process, TERMINATED
from sim.scheduler import fcfs, priority, sjn


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESS_DIR = os.path.join(ROOT, "data", "processes")


class BasicSchedulingTests(unittest.TestCase):
    def load_sample(self, filename: str):
        return load_processes(os.path.join(PROCESS_DIR, filename))

    def assert_schedule(
        self,
        processes: list[Process],
        run,
        expected: list[Segment],
        expected_averages: tuple[float, float] | None = None,
    ) -> list[Segment]:
        segments = run(processes)
        self.assertEqual(segments, expected)
        if expected_averages is not None:
            self.assertEqual(
                tuple(
                    round(value, 2)
                    for value in averages(compute_metrics(processes, segments))
                ),
                expected_averages,
            )
        return segments

    def test_basic_sample_algorithms_and_metrics(self) -> None:
        expected = {
            "fcfs": [
                ("P1", 0, 8),
                ("P2", 8, 12),
                ("P3", 12, 21),
                ("P4", 21, 26),
            ],
            "sjn": [
                ("P1", 0, 8),
                ("P2", 8, 12),
                ("P4", 12, 17),
                ("P3", 17, 26),
            ],
            "priority": [
                ("P1", 0, 8),
                ("P2", 8, 12),
                ("P4", 12, 17),
                ("P3", 17, 26),
            ],
        }
        cases = (
            (fcfs, (15.25, 8.75)),
            (sjn, (14.25, 7.75)),
            (priority, (14.25, 7.75)),
        )
        for algorithm, expected_average in cases:
            with self.subTest(algorithm=algorithm.__name__):
                self.assert_schedule(
                    self.load_sample("p_basic.txt"),
                    algorithm,
                    expected[algorithm.__name__],
                    expected_average,
                )

    def test_idle_gap_sample(self) -> None:
        self.assert_schedule(
            self.load_sample("p_idle_gap.txt"),
            fcfs,
            [("IDLE", 0, 3), ("P1", 3, 7), ("P2", 7, 9)],
            (4.0, 1.0),
        )

    def test_tied_processes_keep_input_order(self) -> None:
        processes = self.load_sample("p_ties.txt")
        self.assert_schedule(
            processes,
            fcfs,
            [("P1", 0, 4), ("P2", 4, 8), ("P3", 8, 11)],
            (7.67, 4.0),
        )

        for algorithm in (sjn, priority):
            with self.subTest(algorithm=algorithm.__name__):
                self.assert_schedule(
                    self.load_sample("p_ties.txt"),
                    algorithm,
                    [("P3", 0, 3), ("P1", 3, 7), ("P2", 7, 11)],
                    (7.0, 3.33),
                )

    def test_single_process_all_algorithms(self) -> None:
        for algorithm in (fcfs, sjn, priority):
            with self.subTest(algorithm=algorithm.__name__):
                processes = self.load_sample("p_single.txt")
                segments = self.assert_schedule(
                    processes,
                    algorithm,
                    [("P1", 0, 5)],
                    (5.0, 0.0),
                )
                self.assertEqual(
                    compute_metrics(processes, segments)[0]["waiting"],
                    0,
                )

    def test_empty_process_list(self) -> None:
        for algorithm in (fcfs, sjn, priority):
            with self.subTest(algorithm=algorithm.__name__):
                self.assertEqual(algorithm([]), [])

    def test_process_runtime_fields_after_run(self) -> None:
        processes = self.load_sample("p_basic.txt")
        fcfs(processes)
        for process in processes:
            self.assertEqual(process.state, TERMINATED)
            self.assertEqual(process.remaining, 0)
            self.assertIsNotNone(process.start_time)
            self.assertIsNotNone(process.completion_time)

        p2 = next(process for process in processes if process.pid == "P2")
        self.assertEqual((p2.start_time, p2.completion_time), (8, 12))

    def test_same_process_list_can_be_reused(self) -> None:
        processes = self.load_sample("p_basic.txt")
        fcfs_segments = fcfs(processes)
        sjn_segments = sjn(processes)
        self.assertEqual(fcfs_segments[0], ("P1", 0, 8))
        self.assertEqual(sjn_segments, [
            ("P1", 0, 8),
            ("P2", 8, 12),
            ("P4", 12, 17),
            ("P3", 17, 26),
        ])

    def test_idle_gap_in_middle_of_schedule(self) -> None:
        processes = [Process("P1", 0, 2, 1), Process("P2", 10, 3, 1)]
        self.assertEqual(
            fcfs(processes),
            [("P1", 0, 2), ("IDLE", 2, 10), ("P2", 10, 13)],
        )

    def test_fcfs_tie_uses_input_order_not_pid_sort(self) -> None:
        processes = [Process("P10", 0, 2, 1), Process("P2", 0, 2, 1)]
        self.assertEqual(
            fcfs(processes),
            [("P10", 0, 2), ("P2", 2, 4)],
        )


if __name__ == "__main__":
    unittest.main()
