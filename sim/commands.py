"""Shell command entry points for the scheduling simulator."""

import os
from typing import TextIO

from shell.context import ShellContext
from sim.deadlock import detect, safety_check
from sim.gantt import merge_segments, render_gantt
from sim.loader import LoaderError, load_processes, load_resources
from sim.metrics import compute_metrics, format_metrics_table
from sim.pcb import format_pcb_table
from sim.scheduler import (
    fcfs,
    multilevel_feedback_queue,
    multilevel_queue,
    priority,
    round_robin,
    sjn,
)

USAGE = (
    "sched: usage: sched <fcfs|sjn|priority|rr|mlq|mlfq> "
    "[--quantum N] [--trace] <file>"
)

ALGORITHMS = {
    "fcfs": fcfs,
    "sjn": sjn,
    "priority": priority,
    "rr": round_robin,
    "mlq": multilevel_queue,
    "mlfq": multilevel_feedback_queue,
}


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
    if algorithm_name not in ALGORITHMS:
        return _write_error(stderr, f"unknown algorithm '{algorithm_name}'")
    if len(positional) == 1:
        return _write_error(stderr, USAGE.removeprefix("sched: "))
    if len(positional) > 2:
        return _write_error(stderr, "too many arguments")

    file_path = os.path.join(ctx.cwd, positional[1])
    try:
        processes = load_processes(file_path)
    except LoaderError as error:
        stderr.write(f"sched: {error}\n")
        return 1

    if not processes:
        stdout.write("No processes to schedule.\n")
        return 0

    stdout.write("Process table (before run):\n")
    stdout.write(format_pcb_table(processes))
    stdout.write("\n\n")

    # Keep original segments for metrics and merge only for chart display.
    events: list[str] | None = (
        [] if trace and algorithm_name in {"rr", "mlq", "mlfq"} else None
    )
    if algorithm_name in {"rr", "mlq"}:
        segments = ALGORITHMS[algorithm_name](processes, quantum or 4, events)
    elif algorithm_name == "mlfq":
        segments = multilevel_feedback_queue(processes, events)
    else:
        segments = ALGORITHMS[algorithm_name](processes)
    stdout.write("Gantt chart:\n")
    stdout.write(render_gantt(merge_segments(segments)))
    stdout.write("\n")

    if events is not None:
        stdout.write("Trace:\n")
        for event in events:
            stdout.write(event + "\n")

    stdout.write("\n")

    rows = compute_metrics(processes, segments)
    stdout.write("Results:\n")
    stdout.write(format_metrics_table(rows))
    stdout.write("\n\n")

    stdout.write("Process table (after run):\n")
    stdout.write(format_pcb_table(processes))
    stdout.write("\n")
    return 0


def cmd_deadlock(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Detect deadlocked processes or check a resource state for safety."""
    usage = "usage: deadlock <detect|banker> <file>"
    if len(args) != 2 or args[0] not in {"detect", "banker"}:
        stderr.write(usage + "\n")
        return 2

    subcommand, file_name = args
    file_path = os.path.join(ctx.cwd, file_name)
    try:
        state = load_resources(file_path)
    except (LoaderError, OSError) as error:
        stderr.write(f"deadlock: {error}\n")
        return 1

    if subcommand == "detect":
        deadlocked = detect(state)
        if deadlocked:
            stdout.write(
                "Deadlock detected. Deadlocked processes: "
                + ", ".join(deadlocked)
                + "\n"
            )
        else:
            stdout.write("No deadlock found.\n")
        return 0

    safe, sequence, stuck = safety_check(state)
    if safe and not sequence:
        stdout.write("SAFE state. Safe sequence: (none, no processes)\n")
    elif safe:
        stdout.write("SAFE state. Safe sequence: " + " -> ".join(sequence) + "\n")
    else:
        stdout.write("UNSAFE state. Stuck processes: " + ", ".join(stuck) + "\n")
    return 0
