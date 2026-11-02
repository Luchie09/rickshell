"""Non-preemptive scheduling algorithms."""

from collections.abc import Callable

from sim.pcb import TERMINATED, Process
from sim.metrics import Segment


def _run_nonpreemptive(
    processes: list[Process],
    key: Callable[[Process, int], tuple[int, ...]],
) -> list[Segment]:
    """Run each ready process to completion, jumping over idle intervals."""
    for process in processes:
        process.reset()

    segments: list[Segment] = []
    time = 0

    # Each iteration either runs a ready process or advances to the next arrival.
    while any(process.state != TERMINATED for process in processes):
        ready = [
            (process, index)
            for index, process in enumerate(processes)
            if process.state != TERMINATED and process.arrival <= time
        ]

        if not ready:
            next_arrival = min(
                process.arrival
                for process in processes
                if process.state != TERMINATED
            )
            # Record the idle gap, then jump directly to the next arrival.
            segments.append(("IDLE", time, next_arrival))
            time = next_arrival
            continue

        chosen, chosen_index = min(
            ready,
            key=lambda item: key(item[0], item[1]),
        )
        chosen.start_time = time
        time += chosen.burst
        segments.append((chosen.pid, chosen.start_time, time))
        chosen.remaining = 0
        chosen.completion_time = time
        chosen.state = TERMINATED

    return segments


def fcfs(processes: list[Process]) -> list[Segment]:
    """Run first-come, first-served scheduling."""
    return _run_nonpreemptive(
        processes,
        lambda process, index: (process.arrival, index),
    )


def sjn(processes: list[Process]) -> list[Segment]:
    """Run non-preemptive shortest-job-next scheduling."""
    return _run_nonpreemptive(
        processes,
        lambda process, index: (process.burst, process.arrival, index),
    )


def priority(processes: list[Process]) -> list[Segment]:
    """Run non-preemptive priority scheduling; smaller values run first."""
    return _run_nonpreemptive(
        processes,
        lambda process, index: (process.priority, process.arrival, index),
    )
