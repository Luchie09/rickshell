"""Shell command entry points for the scheduling simulator."""

import os
from typing import TextIO

from shell.context import ShellContext
from sim.gantt import merge_segments, render_gantt
from sim.loader import LoaderError, load_processes
from sim.metrics import compute_metrics, format_metrics_table
from sim.pcb import format_pcb_table
from sim.scheduler import fcfs, priority, sjn

USAGE = (
    "sched: usage: sched <fcfs|sjn|priority|rr|mlq|mlfq> "
    "[--quantum N] [--trace] <file>"
)

ALGORITHMS = {
    "fcfs": fcfs,
    "sjn": sjn,
    "priority": priority,
}
VALID_ALGORITHMS = {"fcfs", "sjn", "priority", "rr", "mlq", "mlfq"}


def _write_error(stderr: TextIO, message: str) -> int:
    stderr.write(f"sched: {message}\n")
    return 2


def cmd_sched(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Load input, run a selected scheduler, and display its results."""
    positional: list[str] = []
    quantum: int | None = None
    trace = False

    # Parse options and positionals in one pass so options can appear anywhere.
    index = 0
    while index < len(args):
        word = args[index]
        if word == "--quantum":
            if index + 1 >= len(args):
                return _write_error(
                    stderr,
                    "--quantum requires a positive integer",
                )
            try:
                quantum = int(args[index + 1])
            except ValueError:
                return _write_error(
                    stderr,
                    "--quantum requires a positive integer",
                )
            if quantum <= 0:
                return _write_error(
                    stderr,
                    "--quantum requires a positive integer",
                )
            index += 2
            continue
        if word == "--trace":
            trace = True
            index += 1
            continue
        if word.startswith("-"):
            return _write_error(stderr, f"unknown option '{word}'")

        positional.append(word)
        index += 1

    if not positional:
        return _write_error(stderr, USAGE.removeprefix("sched: "))

    algorithm_name = positional[0]
    if algorithm_name not in VALID_ALGORITHMS:
        return _write_error(stderr, f"unknown algorithm '{algorithm_name}'")
    if len(positional) == 1:
        return _write_error(stderr, USAGE.removeprefix("sched: "))
    if len(positional) > 2:
        return _write_error(stderr, "too many arguments")

    if algorithm_name not in ALGORITHMS:
        stderr.write(f"sched: {algorithm_name} is not implemented yet\n")
        return 1

    file_path = os.path.join(ctx.cwd, positional[1])
    try:
        processes = load_processes(file_path)
    except LoaderError as error:
        stderr.write(f"sched: {error}\n")
        return 1

    if not processes:
        stdout.write("No processes to schedule.\n")
        return 0

    # These options are parsed now and will be used by the RR/MLQ/MLFQ work.
    # Prompts 9 and 10 add their behavior.
    _ = quantum, trace

    stdout.write("Process table (before run):\n")
    stdout.write(format_pcb_table(processes))
    stdout.write("\n\n")

    # Keep original segments for metrics and merge only for chart display.
    segments = ALGORITHMS[algorithm_name](processes)
    stdout.write("Gantt chart:\n")
    stdout.write(render_gantt(merge_segments(segments)))
    stdout.write("\n\n")

    rows = compute_metrics(processes, segments)
    stdout.write("Results:\n")
    stdout.write(format_metrics_table(rows))
    stdout.write("\n\n")

    stdout.write("Process table (after run):\n")
    stdout.write(format_pcb_table(processes))
    stdout.write("\n")
    return 0
