# Rick Shell 

CmpSc 123 Operating Systems project. Rick Shell is a small Bash-like shell written in Python 3 that also simulates two core OS functions: CPU process scheduling and deadlock handling. 

## Requirements and how to run

- Python 3.x, standard library only. No installs.
- Start the shell from the project root: `python main.py`
- Type `exit` to quit.

## Commands

| Command | Behavior |
|---|---|
| `pwd` | Print current directory |
| `cd [dir]` | Change directory (no argument goes to home) |
| `ls [-l] [path]` | List entries. `-l` shows permissions, size, modified time, name |
| `mkdir dir...` | Create directories |
| `rmdir dir...` | Remove empty directories |
| `touch file...` | Create a file or update its time |
| `cp src dst` | Copy a file |
| `mv src dst` | Move or rename |
| `rm [-r] path...` | Remove files, or directories with `-r` |
| `cat [file...]` | Print files, or stdin when no file is given |
| `chmod MODE file` | Numeric mode only (3 or 4 octal digits) |
| `echo words...` | Print arguments |
| `env` | List variables as NAME=value, sorted |
| `grep [-i] [-n] [-E] [--groups] PATTERN [file...]` | Search lines. Reads stdin when no file is given |
| `sched ...` | CPU scheduling simulator |
| `deadlock ...` | Deadlock simulator |
| `compare ...` | Compare all six scheduling algorithms |
| `rick [on|off|--live]` | Stream the live Rick animation (requires internet) |
| `help` | List all commands |
| `exit` | Quit the shell |

`rick` needs an internet connection and does nothing when offline.

**Redirection:** `>`, `>>`, `<`, `2>`, `2>&1` (processed left to right).
**Pipes:** `ls | grep txt`, any number of stages.
**Variables:** `NAME=value`, `echo $NAME`, `$?` for the last exit code. Single quotes are literal, double quotes expand variables.
**Conditionals:** `a && b`, `a || b`, `a ; b`, and single-line `if cmd; then cmd; else cmd; fi`.

**Exit codes:** 0 success, 1 general failure, 2 bad arguments or usage, 127 command not found.

### grep options

- Default: plain-text match. `-i` ignores case, `-n` prefixes line numbers.
- `-E`: regular expression (Python `re`). Supports `.`, `[a-z]`, `*`, `+`, `?`, backslash escapes and `( )` groups.
- `--groups`: implies `-E`, prints the captured groups of the first match after each matching line.
- A bad pattern prints `grep: invalid pattern: ...` and returns 2.

### Scheduler

```
sched <fcfs|sjn|priority|rr|mlq|mlfq> [--quantum N] [--trace] <file>
```

Default quantum is 4. Each run prints the PCB table before and after, a Gantt chart, a per-process table, and the averages. `--trace` prints every state change.

### Deadlock

```
deadlock detect <file>
deadlock banker <file>
deadlock banker <file> --request P1 1 0 2
```

`detect` lists deadlocked processes and prints a recovery suggestion and a preemption note. `banker` reports SAFE with the safe sequence, or UNSAFE with the stuck processes. `--request` runs a resource request on an in-memory copy (granted, wait, or denied). The file on disk is never modified.

### Compare

```
compare <process_file> [--quantum N] [--save <path.md>]
```

Runs all six algorithms on the same file, prints a table and bar charts, and names the best algorithm per metric. `--save` writes a Markdown table.

## Input file formats

**Process file** (`#` comments and blank lines are skipped):

```
# PID arrival burst priority
P1 0 8 2
P2 1 4 1
```

**Resource file** (n processes, m resources, then Allocation, Max, and Available):

```
5 3
0 1 0
...        (n Allocation rows)
7 5 3
...        (n Max rows)
3 3 2      (Available row)
```

Sample files are in `data/processes/` and `data/resources/`.

## Algorithm decisions

- **FCFS:** order of arrival, ties by PID.
- **SJN:** non-preemptive, shortest burst among arrived processes. Ties by arrival, then PID.
- **Priority:** non-preemptive, lower number means higher priority. Ties by arrival, then PID.
- **Round-Robin:** quantum Q. A process arriving at the same moment another is requeued enters the queue first.
- **Multilevel Queue:** Queue 0 (Round-Robin) for priority 1 or 2, Queue 1 (FCFS) for the rest. Queue 0 is always served first and preempts Queue 1. Processes never change queues.
- **Multilevel Feedback Queue:** three levels with quanta 2, 4 and FCFS. A process that uses a full quantum is demoted. A higher-level arrival preempts a lower level.
- **Idle time:** shown as IDLE until the next arrival.
- **Turnaround** = Completion - Arrival. **Waiting** = Turnaround - Burst.
- **Detection:** Work = Available, repeatedly finish any process whose Need fits in Work. Processes left over are deadlocked. Need is treated as the potential request.
- **Banker's:** the same safety loop. A request is rejected if it exceeds Need, waits if it exceeds Available, otherwise is trial-allocated and rolled back if the result is unsafe.
- **Recovery:** repeatedly suggest terminating the deadlocked process holding the most resources (ties: lowest PID) until no deadlock remains. This is a suggestion only.

## Running the tests

```
python -m unittest discover -s tests -t .
```

## Known limitations

- `if` is single-line and not nested.
- `chmod` accepts numeric modes only.
- No external programs: only the built-in commands above are available.
- Recovery picks by most resources held, a heuristic that is not guaranteed to be optimal.