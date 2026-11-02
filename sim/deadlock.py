"""Shared resource-state and safety-check foundations for deadlock tools."""

from dataclasses import dataclass


@dataclass
class ResourceState:
    """Current allocation, maximum claims, and available resource counts."""

    n: int
    m: int
    allocation: list[list[int]]
    max_claim: list[list[int]]
    available: list[int]

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
