"""Scheduling completion, turnaround, waiting, and display helpers."""

from sim.pcb import Process

Segment = tuple[str, int, int]
MetricRow = dict[str, str | int]


def completion_times(segments: list[Segment]) -> dict[str, int]:
    """Return the end time of each process's last segment."""
    completions: dict[str, int] = {}
    for label, _, end in segments:
        if label != "IDLE":
            completions[label] = end
    return completions


def compute_metrics(
    processes: list[Process],
    segments: list[Segment],
) -> list[MetricRow]:
    """Calculate turnaround and waiting in the original process order."""
    completions = completion_times(segments)
    rows: list[MetricRow] = []
    for process in processes:
        completion = completions.get(process.pid, 0)
        turnaround = completion - process.arrival
        rows.append(
            {
                "pid": process.pid,
                "arrival": process.arrival,
                "burst": process.burst,
                "priority": process.priority,
                "completion": completion,
                "turnaround": turnaround,
                "waiting": turnaround - process.burst,
            }
        )
    return rows


def averages(rows: list[MetricRow]) -> tuple[float, float]:
    """Return average turnaround and waiting, or zeroes for no rows."""
    if not rows:
        return 0.0, 0.0
    turnaround = sum(int(row["turnaround"]) for row in rows) / len(rows)
    waiting = sum(int(row["waiting"]) for row in rows) / len(rows)
    return turnaround, waiting


def format_metrics_table(rows: list[MetricRow]) -> str:
    """Return aligned metric columns and their two-decimal averages."""
    header = "PID  Arr  Burst  Prio  Completion  Turnaround  Waiting"
    formatted_rows = [header]
    for row in rows:
        formatted_rows.append(
            f"{str(row['pid']):<3}  {int(row['arrival']):>3}  "
            f"{int(row['burst']):>5}  {int(row['priority']):>4}  "
            f"{int(row['completion']):>10}  "
            f"{int(row['turnaround']):>10}  {int(row['waiting']):>7}"
        )
    average_turnaround, average_waiting = averages(rows)
    formatted_rows.append(
        f"Average turnaround: {average_turnaround:.2f}   "
        f"Average waiting: {average_waiting:.2f}"
    )
    return "\n".join(formatted_rows)
