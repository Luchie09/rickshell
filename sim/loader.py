"""Load process definitions from whitespace-separated text files."""

from sim.pcb import Process


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
