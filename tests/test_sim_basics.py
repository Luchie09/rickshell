"""Tests for scheduler shared data, loading, metrics, and Gantt rendering."""

import os
import tempfile
import unittest

from sim.gantt import merge_segments, render_gantt
from sim.loader import LoaderError, load_processes
from sim.metrics import (
    averages,
    completion_times,
    compute_metrics,
    format_metrics_table,
)
from sim.pcb import NEW, Process, format_pcb_table


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_DIR = os.path.join(ROOT, "data", "processes")


class LoaderTests(unittest.TestCase):
    def write_input(self, contents: str) -> str:
        temporary = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
        )
        self.addCleanup(lambda: os.path.exists(temporary.name) and os.unlink(temporary.name))
        with temporary:
            temporary.write(contents)
        return temporary.name

    def test_valid_file_skips_comments_and_blank_lines(self) -> None:
        path = self.write_input(
            "# process file\n\nP1 0 4 2\n   # another comment\nP2 3 5 1\n"
        )
        processes = load_processes(path)
        self.assertEqual(
            [(p.pid, p.arrival, p.burst, p.priority) for p in processes],
            [("P1", 0, 4, 2), ("P2", 3, 5, 1)],
        )

    def test_empty_and_comment_only_files(self) -> None:
        self.assertEqual(load_processes(self.write_input("")), [])
        self.assertEqual(load_processes(self.write_input("# only a comment\n")), [])

    def test_bad_line_reports_one_based_line_number(self) -> None:
        path = self.write_input("# header\n\nP1 0 invalid 1\n")
        with self.assertRaisesRegex(LoaderError, "^line 3:"):
            load_processes(path)

    def test_validation_errors(self) -> None:
        cases = [
            ("P1 -1 1 0\n", "arrival must not be negative"),
            ("P1 0 0 0\n", "burst must be positive"),
            ("P1 0 1\n", "expected PID arrival burst priority"),
            ("P1 0 1 0\nP1 1 2 1\n", "duplicate PID"),
            ("P1 0 1 x\n", "must be integers"),
        ]
        for contents, expected in cases:
            with self.subTest(contents=contents):
                with self.assertRaisesRegex(LoaderError, expected):
                    load_processes(self.write_input(contents))

    def test_missing_file(self) -> None:
        path = os.path.join(tempfile.gettempdir(), "no-such-process-file.txt")
        with self.assertRaisesRegex(LoaderError, "No such file or directory"):
            load_processes(path)

    def test_sample_files(self) -> None:
        basic = load_processes(os.path.join(SAMPLE_DIR, "p_basic.txt"))
        self.assertEqual([process.pid for process in basic], ["P1", "P2", "P3", "P4"])
        self.assertEqual(len(load_processes(os.path.join(SAMPLE_DIR, "p_single.txt"))), 1)
        self.assertEqual(load_processes(os.path.join(SAMPLE_DIR, "p_empty.txt")), [])
        idle = load_processes(os.path.join(SAMPLE_DIR, "p_idle_gap.txt"))
        self.assertEqual([(p.arrival, p.burst) for p in idle], [(3, 4), (5, 2)])
        ties = load_processes(os.path.join(SAMPLE_DIR, "p_ties.txt"))
        self.assertEqual([p.pid for p in ties], ["P1", "P2", "P3"])
        with self.assertRaisesRegex(LoaderError, "^line 3:"):
            load_processes(os.path.join(SAMPLE_DIR, "p_bad_line.txt"))


class ProcessTests(unittest.TestCase):
    def test_process_defaults_and_reset(self) -> None:
        process = Process("P1", 0, 5, 1)
        self.assertEqual(process.state, NEW)
        self.assertEqual(process.remaining, 5)

        process.state = "Running"
        process.remaining = 1
        process.start_time = 2
        process.completion_time = 6
        process.reset()
        self.assertEqual(
            (
                process.state,
                process.remaining,
                process.start_time,
                process.completion_time,
            ),
            ("New", 5, None, None),
        )

    def test_process_table_has_header_and_one_row_each(self) -> None:
        processes = [Process("P1", 0, 5, 2), Process("P2", 1, 3, 1)]
        table = format_pcb_table(processes)
        self.assertTrue(table.startswith("PID  State       Prio  Arrival  Burst  Remaining\n"))
        self.assertEqual(len(table.splitlines()), 3)
        self.assertIn("P1", table)
        self.assertIn("P2", table)


class MetricsTests(unittest.TestCase):
    def test_basic_hand_calculated_metrics(self) -> None:
        processes = load_processes(os.path.join(SAMPLE_DIR, "p_basic.txt"))
        segments = [
            ("P1", 0, 8),
            ("P2", 8, 12),
            ("P3", 12, 21),
            ("P4", 21, 26),
        ]
        self.assertEqual(
            completion_times(segments),
            {"P1": 8, "P2": 12, "P3": 21, "P4": 26},
        )
        rows = compute_metrics(processes, segments)
        self.assertEqual(
            [row["turnaround"] for row in rows],
            [8, 11, 19, 23],
        )
        self.assertEqual([row["waiting"] for row in rows], [0, 7, 10, 18])
        self.assertEqual(averages(rows), (15.25, 8.75))
        self.assertIn("Average turnaround: 15.25   Average waiting: 8.75", format_metrics_table(rows))

    def test_idle_metrics_and_empty_averages(self) -> None:
        processes = load_processes(os.path.join(SAMPLE_DIR, "p_idle_gap.txt"))
        segments = [("IDLE", 0, 3), ("P1", 3, 7), ("IDLE", 7, 7), ("P2", 7, 9)]
        self.assertEqual(completion_times(segments), {"P1": 7, "P2": 9})
        rows = compute_metrics(processes, segments)
        self.assertEqual([row["completion"] for row in rows], [7, 9])
        self.assertEqual(averages([]), (0.0, 0.0))


class GanttTests(unittest.TestCase):
    def test_render_exact_layout(self) -> None:
        segments = [
            ("P1", 0, 4),
            ("P2", 4, 6),
            ("IDLE", 6, 8),
            ("P3", 8, 12),
        ]
        self.assertEqual(
            render_gantt(segments),
            "| P1 | P2 | IDLE | P3 |\n0    4    6      8    12",
        )

    def test_merge_contiguous_same_process(self) -> None:
        self.assertEqual(
            merge_segments([("P1", 0, 2), ("P1", 2, 4)]),
            [("P1", 0, 4)],
        )

    def test_large_times_do_not_overlap(self) -> None:
        rendered = render_gantt([("P1", 0, 100), ("P2", 100, 1000)])
        timeline = rendered.splitlines()[1]
        self.assertEqual(timeline[0:1], "0")
        self.assertEqual(timeline.index("100"), rendered.splitlines()[0].index("|", 1))
        self.assertTrue(timeline.rstrip().endswith("1000"))

    def test_empty_schedule(self) -> None:
        self.assertEqual(render_gantt([]), "(empty schedule)")


if __name__ == "__main__":
    unittest.main()
