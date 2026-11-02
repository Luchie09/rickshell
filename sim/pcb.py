"""Process control block data shared by scheduling algorithms."""

from dataclasses import dataclass, field

NEW = "New"
READY = "Ready"
RUNNING = "Running"
WAITING = "Waiting"
TERMINATED = "Terminated"


@dataclass
class Process:
    """Stores the input and runtime state for one process."""

    pid: str
    arrival: int
    burst: int
    priority: int
    state: str = NEW
    remaining: int = field(init=False)
    start_time: int | None = None
    completion_time: int | None = None

    def __post_init__(self) -> None:
        self.remaining = self.burst

    def reset(self) -> None:
        """Restore runtime fields so this process can be simulated again."""
        self.state = NEW
        self.remaining = self.burst
        self.start_time = None
        self.completion_time = None


def format_pcb_table(processes: list[Process]) -> str:
    """Return the process list as a consistently aligned text table."""
    header = (
        f"{'PID':<3}  {'State':<11} {'Prio':>4}  {'Arrival':>7}  "
        f"{'Burst':>5}  {'Remaining':>9}"
    )
    rows = [header]
    for process in processes:
        rows.append(
            f"{process.pid:<3}  {process.state:<11} {process.priority:>4}  "
            f"{process.arrival:>7}  {process.burst:>5}  "
            f"{process.remaining:>9}"
        )
    return "\n".join(rows)
