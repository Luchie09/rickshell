"""Shared resource-state and safety-check foundations for deadlock tools."""

from dataclasses import dataclass, field


@dataclass
class ResourceState:
    """Current allocation, maximum claims, and available resource counts."""

    n: int
    m: int
    allocation: list[list[int]]
    max_claim: list[list[int]]
    available: list[int]
    process_states: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.process_states:
            self.process_states = ["Ready"] * self.n

    def need(self) -> list[list[int]]:
        """Return each process's remaining maximum resource requirement."""
        return [
            [
                self.max_claim[process][resource]
                - self.allocation[process][resource]
                for resource in range(self.m)
            ]
            for process in range(self.n)
        ]

    def copy(self) -> "ResourceState":
        """Return an independent copy of the complete resource state."""
        return ResourceState(
            self.n,
            self.m,
            [row.copy() for row in self.allocation],
            [row.copy() for row in self.max_claim],
            self.available.copy(),
            self.process_states.copy(),
        )

    def pid(self, index: int) -> str:
        """Format a process index as its display identifier."""
        return f"P{index}"


def safety_check(
    state: ResourceState,
) -> tuple[bool, list[str], list[str]]:
    """Check whether all processes can finish without changing state."""
    work = state.available.copy()
    finished = [False] * state.n
    sequence: list[str] = []
    needed = state.need()

    # Safety checking and deadlock detection share this Work/Finish loop:
    # each process that can proceed releases its allocation back into Work.
    while not all(finished):
        made_progress = False
        # Continue forward through the same pass after a process can finish.
        for process in range(state.n):
            if finished[process]:
                continue
            if all(
                needed[process][resource] <= work[resource]
                for resource in range(state.m)
            ):
                for resource in range(state.m):
                    work[resource] += state.allocation[process][resource]
                finished[process] = True
                sequence.append(state.pid(process))
                made_progress = True
        if not made_progress:
            break

    stuck = [
        state.pid(process)
        for process in range(state.n)
        if not finished[process]
    ]
    return all(finished), sequence, stuck


def detect(state: ResourceState) -> list[str]:
    """Return processes that cannot finish when Need is their request."""
    work = state.available.copy()
    finished = [False] * state.n
    needed = state.need()

    while not all(finished):
        made_progress = False
        # Detection uses Need as the outstanding request and releases each
        # completed process's allocation, just like the safety-check loop.
        for process in range(state.n):
            if finished[process]:
                continue
            if all(
                needed[process][resource] <= work[resource]
                for resource in range(state.m)
            ):
                for resource in range(state.m):
                    work[resource] += state.allocation[process][resource]
                finished[process] = True
                made_progress = True
        if not made_progress:
            break

    return [
        state.pid(process)
        for process in range(state.n)
        if not finished[process]
    ]


def request_resources(
    state: ResourceState,
    pid: str,
    vector: list[int],
) -> tuple[str, list[str]]:
    """Try a resource request and return its outcome and safe sequence.

    The input state is changed only for a granted request. A waiting process
    is marked Waiting; exceeded and denied requests leave resources unchanged.
    """
    try:
        process = int(pid[1:]) if pid.startswith("P") else -1
    except ValueError:
        process = -1
    if process < 0 or process >= state.n or len(vector) != state.m:
        return "invalid", []

    needed = state.need()
    if any(vector[j] > needed[process][j] for j in range(state.m)):
        return "exceeded", []

    if any(vector[j] > state.available[j] for j in range(state.m)):
        state.process_states[process] = "Waiting"
        return "wait", []

    trial = state.copy()
    for resource in range(state.m):
        trial.available[resource] -= vector[resource]
        trial.allocation[process][resource] += vector[resource]

    safe, sequence, _stuck = safety_check(trial)
    if not safe:
        return "denied", []

    state.available = trial.available
    state.allocation = trial.allocation
    state.process_states = trial.process_states
    state.process_states[process] = "Ready"
    return "granted", sequence
