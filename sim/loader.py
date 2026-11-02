"""Load process definitions from whitespace-separated text files."""

from typing import TYPE_CHECKING

from sim.pcb import Process

if TYPE_CHECKING:
    from sim.deadlock import ResourceState


class LoaderError(Exception):
    """Raised when a process input file cannot be loaded or validated."""


def load_processes(path: str) -> list[Process]:
    """Read and validate PID, arrival, burst, and priority records."""
    processes: list[Process] = []
    seen_pids: set[str] = set()

    try:
        with open(path, "r", encoding="utf-8") as process_file:
            for line_number, line in enumerate(process_file, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue

                fields = stripped.split()
                if len(fields) != 4:
                    raise LoaderError(
                        f"line {line_number}: expected PID arrival burst priority"
                    )

                pid = fields[0]
                try:
                    arrival = int(fields[1])
                    burst = int(fields[2])
                    priority = int(fields[3])
                except ValueError as error:
                    raise LoaderError(
                        f"line {line_number}: arrival, burst, and priority must be integers"
                    ) from error

                if arrival < 0:
                    raise LoaderError(f"line {line_number}: arrival must not be negative")
                if burst <= 0:
                    raise LoaderError(f"line {line_number}: burst must be positive")
                if pid in seen_pids:
                    raise LoaderError(f"line {line_number}: duplicate PID '{pid}'")

                seen_pids.add(pid)
                processes.append(Process(pid, arrival, burst, priority))
    except FileNotFoundError as error:
        raise LoaderError(f"{path}: No such file or directory") from error

    return processes


def load_resources(path: str) -> "ResourceState":
    """Read and validate a resource-allocation state from a text file."""
    from sim.deadlock import ResourceState

    data_rows: list[tuple[int, str]] = []
    try:
        with open(path, "r", encoding="utf-8") as resource_file:
            for line_number, line in enumerate(resource_file, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                data_rows.append((line_number, stripped))
    except FileNotFoundError as error:
        raise LoaderError(f"{path}: No such file or directory") from error

    if not data_rows:
        raise LoaderError("line 1: missing resource dimensions header")

    header_line, header = data_rows[0]
    header_fields = header.split()
    if len(header_fields) != 2:
        raise LoaderError(
            f"line {header_line}: header must contain exactly n and m"
        )
    try:
        n, m = (int(value) for value in header_fields)
    except ValueError as error:
        raise LoaderError(
            f"line {header_line}: header values n and m must be integers"
        ) from error
    if n < 0 or m < 0:
        raise LoaderError(f"line {header_line}: n and m must not be negative")

    expected_rows = 2 * n + 1
    actual_rows = len(data_rows) - 1
    if actual_rows != expected_rows:
        raise LoaderError(
            f"expected {expected_rows} data rows, found {actual_rows} rows"
        )

    parsed_rows: list[list[int]] = []
    for line_number, row in data_rows[1:]:
        fields = row.split()
        if len(fields) != m:
            raise LoaderError(
                f"line {line_number}: expected {m} values, found {len(fields)}"
            )
        try:
            values = [int(value) for value in fields]
        except ValueError as error:
            raise LoaderError(
                f"line {line_number}: resource values must be integers"
            ) from error
        if any(value < 0 for value in values):
            raise LoaderError(f"line {line_number}: values must not be negative")
        parsed_rows.append(values)

    allocation = parsed_rows[:n]
    max_claim = parsed_rows[n : 2 * n]
    available = parsed_rows[2 * n]
    for process_index, (allocated, maximum) in enumerate(
        zip(allocation, max_claim)
    ):
        for resource_index, (allocated_amount, max_amount) in enumerate(
            zip(allocated, maximum)
        ):
            if allocated_amount > max_amount:
                raise LoaderError(
                    f"Allocation[P{process_index}][R{resource_index}] "
                    f"exceeds Max[P{process_index}][R{resource_index}]"
                )

    return ResourceState(n, m, allocation, max_claim, available)
