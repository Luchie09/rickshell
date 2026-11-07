"""The six CPU scheduling algorithms.

FCFS, SJN, and Priority jump from event to event. Round-Robin, MLQ, and MLFQ
advance one time unit per loop so preemption can happen at any tick. Every
function returns a list of (label, start, end) segments for the Gantt chart.
"""

from collections.abc import Callable

from sim.pcb import NEW, READY, RUNNING, TERMINATED, Process
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


# Each key ends with the input index, so remaining ties keep file order.
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


def round_robin(
    processes: list[Process],
    quantum: int = 4,
    events: list[str] | None = None,
) -> list[Segment]:
    """Run Round-Robin scheduling with arrivals admitted before requeueing."""
    if quantum < 1:
        raise ValueError("quantum must be at least 1")

    for process in processes:
        process.reset()

    segments: list[Segment] = []
    time = 0
    queue: list[Process] = []
    running: Process | None = None
    slice_used = 0
    admitted: set[str] = set()

    def admit_arrivals(at_time: int) -> None:
        for process in processes:
            if (
                process.state != TERMINATED
                and process.pid not in admitted
                and process.arrival == at_time
            ):
                if events is not None:
                    events.append(
                        f"t={at_time} {process.pid} {NEW} -> {READY}"
                    )
                process.state = READY
                admitted.add(process.pid)
                queue.append(process)

    while any(process.state != TERMINATED for process in processes):
        admit_arrivals(time)

        if running is None and queue:
            running = queue.pop(0)
            if events is not None:
                events.append(
                    f"t={time} {running.pid} {READY} -> {RUNNING}"
                )
            running.state = RUNNING
            if running.start_time is None:
                running.start_time = time
            slice_used = 0

        if running is None:
            segments.append(("IDLE", time, time + 1))
            time += 1
            continue

        running.remaining -= 1
        slice_used += 1
        segments.append((running.pid, time, time + 1))
        time += 1

        # Admit arrivals first so they enter the queue before a preempted process.
        admit_arrivals(time)

        if running.remaining == 0:
            if events is not None:
                events.append(
                    f"t={time} {running.pid} {RUNNING} -> {TERMINATED}"
                )
            running.completion_time = time
            running.state = TERMINATED
            running = None
        elif slice_used == quantum:
            if events is not None:
                events.append(f"t={time} {running.pid} {RUNNING} -> {READY}")
            running.state = READY
            queue.append(running)
            running = None

    return segments


def multilevel_queue(
    processes: list[Process],
    quantum: int = 4,
    events: list[str] | None = None,
) -> list[Segment]:
    """Run Q0 as Round-Robin and Q1 as FCFS, always favoring Q0."""
    if quantum < 1:
        raise ValueError("quantum must be at least 1")

    for process in processes:
        process.reset()

    segments: list[Segment] = []
    time = 0
    q0: list[Process] = []
    q1: list[Process] = []
    running: Process | None = None
    slice_used = 0
    admitted: set[str] = set()
    q0_pids = {
        process.pid
        for process in processes
        if process.priority in (1, 2)
    }

    def admit_arrivals(at_time: int) -> None:
        for process in processes:
            if (
                process.state != TERMINATED
                and process.pid not in admitted
                and process.arrival == at_time
            ):
                if events is not None:
                    events.append(
                        f"t={at_time} {process.pid} {NEW} -> {READY}"
                    )
                process.state = READY
                admitted.add(process.pid)
                if process.pid in q0_pids:
                    q0.append(process)
                else:
                    q1.append(process)

    # Q0 receives Round-Robin service; Q1 processes run FCFS without a quantum.
    while any(process.state != TERMINATED for process in processes):
        admit_arrivals(time)

        # A newly ready Q0 process interrupts a running Q1 process immediately.
        if (
            running is not None
            and running.pid not in q0_pids
            and q0
        ):
            if events is not None:
                events.append(
                    f"t={time} {running.pid} {RUNNING} -> {READY}"
                )
            running.state = READY
            # Resume the interrupted FCFS process before later Q1 arrivals.
            q1.insert(0, running)
            running = None

        if running is None:
            if q0:
                running = q0.pop(0)
                slice_used = 0
            elif q1:
                running = q1.pop(0)

            if running is not None:
                if events is not None:
                    events.append(
                        f"t={time} {running.pid} {READY} -> {RUNNING}"
                    )
                running.state = RUNNING
                if running.start_time is None:
                    running.start_time = time

        if running is None:
            segments.append(("IDLE", time, time + 1))
            time += 1
            continue

        running.remaining -= 1
        if running.pid in q0_pids:
            slice_used += 1
        segments.append((running.pid, time, time + 1))
        time += 1

        # Admit first so same-time arrivals join their queue before any requeue.
        admit_arrivals(time)

        if running.remaining == 0:
            if events is not None:
                events.append(
                    f"t={time} {running.pid} {RUNNING} -> {TERMINATED}"
                )
            running.completion_time = time
            running.state = TERMINATED
            running = None
        elif running.pid in q0_pids and slice_used == quantum:
            if events is not None:
                events.append(f"t={time} {running.pid} {RUNNING} -> {READY}")
            running.state = READY
            q0.append(running)
            running = None

    return segments


def multilevel_feedback_queue(
    processes: list[Process],
    events: list[str] | None = None,
) -> list[Segment]:
    """Run three feedback levels: RR(2), RR(4), then FCFS."""
    for process in processes:
        process.reset()

    segments: list[Segment] = []
    time = 0
    queues: list[list[Process]] = [[], [], []]
    running: Process | None = None
    running_level = 0
    slice_used = 0
    admitted: set[str] = set()
    quanta = (2, 4, None)

    def admit_arrivals(at_time: int) -> None:
        for process in processes:
            if (
                process.state != TERMINATED
                and process.pid not in admitted
                and process.arrival == at_time
            ):
                if events is not None:
                    events.append(
                        f"t={at_time} {process.pid} {NEW} -> {READY}"
                    )
                process.state = READY
                admitted.add(process.pid)
                # All new work starts at the most responsive priority level.
                queues[0].append(process)

    # Each level has its own queue: RR with quanta 2 and 4, then FCFS.
    while any(process.state != TERMINATED for process in processes):
        admit_arrivals(time)

        # A process runs only while no higher-priority level has ready work.
        if running is not None and any(
            queues[level] for level in range(running_level)
        ):
            if events is not None:
                events.append(
                    f"t={time} {running.pid} {RUNNING} -> {READY}"
                )
            running.state = READY
            # Keep its current level; preemption is not a quantum demotion.
            queues[running_level].append(running)
            running = None

        if running is None:
            for level in range(3):
                if queues[level]:
                    running = queues[level].pop(0)
                    running_level = level
                    if events is not None:
                        events.append(
                            f"t={time} {running.pid} {READY} -> {RUNNING}"
                        )
                    running.state = RUNNING
                    if running.start_time is None:
                        running.start_time = time
                    # A process gets a fresh quantum whenever it is dispatched.
                    slice_used = 0
                    break

        if running is None:
            segments.append(("IDLE", time, time + 1))
            time += 1
            continue

        running.remaining -= 1
        slice_used += 1
        segments.append((running.pid, time, time + 1))
        time += 1

        # Admit boundary arrivals before finishing/demoting the running process.
        admit_arrivals(time)

        if running.remaining == 0:
            if events is not None:
                events.append(
                    f"t={time} {running.pid} {RUNNING} -> {TERMINATED}"
                )
            running.completion_time = time
            running.state = TERMINATED
            running = None
        elif (
            running_level < 2
            and slice_used == quanta[running_level]
        ):
            # Used its whole quantum, so it drops one level.
            running_level += 1
            if events is not None:
                events.append(f"t={time} {running.pid} {RUNNING} -> {READY}")
                events.append(
                    f"t={time} {running.pid} demoted to Level {running_level}"
                )
            running.state = READY
            queues[running_level].append(running)
            running = None

    return segments
