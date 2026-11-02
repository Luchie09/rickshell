"""Compare the scheduler algorithms using a shared process input file."""

import copy
import os
from typing import TextIO

from shell.context import ShellContext
from sim.loader import LoaderError, load_processes
from sim.metrics import averages, compute_metrics
from sim.scheduler import (
    fcfs,
    multilevel_feedback_queue,
    multilevel_queue,
    priority,
    round_robin,
    sjn,
)

ALGORITHMS = (
    ("FCFS", fcfs),
    ("SJN", sjn),
    ("Priority", priority),
    ("RR", round_robin),
    ("MLQ", multilevel_queue),
    ("MLFQ", multilevel_feedback_queue),
)


def _report_lines(results: list[tuple[str, float, float]]) -> list[str]:
    """Build the comparison table, bar charts, and best-algorithm summaries."""
    lines = [
        "Algorithm | Avg waiting | Avg turnaround",
        "----------|-------------|---------------",
    ]
    for name, waiting, turnaround in results:
        lines.append(f"{name:<9} | {waiting:>11.2f} | {turnaround:>13.2f}")

    lines.append("")
    lines.append("Avg waiting:")
    for name, waiting, _turnaround in results:
        bar = "#" * max(1, round(waiting))
        lines.append(f"{name:<8} {bar} {waiting:.2f}")

    lines.append("")
    lines.append("Avg turnaround:")
    for name, _waiting, turnaround in results:
        bar = "#" * max(1, round(turnaround))
        lines.append(f"{name:<8} {bar} {turnaround:.2f}")

    best_waiting = min(result[1] for result in results)
    best_turnaround = min(result[2] for result in results)
    waiting_winners = [
        name for name, waiting, _turnaround in results if waiting == best_waiting
    ]
    turnaround_winners = [
        name for name, _waiting, turnaround in results
        if turnaround == best_turnaround
    ]
    lines.append("")
    lines.append("Best avg waiting: " + ", ".join(waiting_winners))
    lines.append("Best avg turnaround: " + ", ".join(turnaround_winners))
    return lines


def _markdown_lines(results: list[tuple[str, float, float]]) -> list[str]:
    """Build the requested Markdown table and best-algorithm lines."""
    lines = [
        "| Algorithm | Avg waiting | Avg turnaround |",
        "|---|---:|---:|",
    ]
    for name, waiting, turnaround in results:
        lines.append(f"| {name} | {waiting:.2f} | {turnaround:.2f} |")

    best_waiting = min(result[1] for result in results)
    best_turnaround = min(result[2] for result in results)
    waiting_winners = [
        name for name, waiting, _turnaround in results if waiting == best_waiting
    ]
    turnaround_winners = [
        name for name, _waiting, turnaround in results
        if turnaround == best_turnaround
    ]
    lines.extend(
        [
            "",
            "**Best avg waiting:** " + ", ".join(waiting_winners),
            "**Best avg turnaround:** " + ", ".join(turnaround_winners),
        ]
    )
    return lines


def cmd_compare(
    args: list[str],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    ctx: ShellContext,
) -> int:
    """Run all six schedulers on copies and display their average metrics."""
    usage = "usage: compare <process_file> [--quantum N] [--save <path.md>]"
    if not args:
        stderr.write(f"compare: {usage}\n")
        return 2

    process_file: str | None = None
    save_path: str | None = None
    quantum = 4
    index = 0
    while index < len(args):
        word = args[index]
        if word == "--quantum":
            if index + 1 >= len(args):
                stderr.write("compare: --quantum requires a positive integer\n")
                return 2
            try:
                quantum = int(args[index + 1])
            except ValueError:
                stderr.write("compare: --quantum requires a positive integer\n")
                return 2
            if quantum <= 0:
                stderr.write("compare: --quantum requires a positive integer\n")
                return 2
            index += 2
        elif word == "--save":
            if index + 1 >= len(args):
                stderr.write("compare: --save requires a path\n")
                return 2
            save_path = args[index + 1]
            index += 2
        elif word.startswith("-"):
            stderr.write(f"compare: unknown option '{word}'\n")
            return 2
        elif process_file is None:
            process_file = word
            index += 1
        else:
            stderr.write(f"compare: {usage}\n")
            return 2

    if process_file is None or (save_path is not None and not save_path):
        stderr.write(f"compare: {usage}\n")
        return 2

    try:
        processes = load_processes(os.path.join(ctx.cwd, process_file))
    except (LoaderError, OSError) as error:
        stderr.write(f"compare: {error}\n")
        return 1

    if not processes:
        stdout.write("No processes to schedule.\n")
        return 0

    results: list[tuple[str, float, float]] = []
    for name, algorithm in ALGORITHMS:
        run_processes = copy.deepcopy(processes)
        if name in {"RR", "MLQ"}:
            segments = algorithm(run_processes, quantum)
        else:
            segments = algorithm(run_processes)
        turnaround, waiting = averages(compute_metrics(run_processes, segments))
        results.append((name, waiting, turnaround))

    if save_path is not None:
        resolved_save_path = os.path.join(ctx.cwd, save_path)
        try:
            parent = os.path.dirname(resolved_save_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(resolved_save_path, "w", encoding="utf-8") as report_file:
                report_file.write("\n".join(_markdown_lines(results)) + "\n")
        except (OSError, ValueError) as error:
            stderr.write(f"compare: {error}\n")
            return 1

    stdout.write("\n".join(_report_lines(results)) + "\n")
    return 0
