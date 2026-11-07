# Rick Shell

A Bash-like command-line shell written in Python 3, with built-in simulators for CPU process scheduling and deadlock handling.

A project requirement in CMPSC 123: Operating Systems.

## Table of Contents

1. [Overview](#overview)
2. [Requirements](#requirements)
3. [Libraries Used](#libraries-used)
4. [Getting Started](#getting-started)
5. [Project Structure](#project-structure)
6. [Shell Reference](#shell-reference)
7. [Process Scheduling Simulator](#process-scheduling-simulator)
8. [Deadlock Simulator](#deadlock-simulator)
9. [Algorithm Comparison](#algorithm-comparison)
10. [Input File Formats](#input-file-formats)
11. [Algorithm Conventions](#algorithm-conventions)
12. [Testing](#testing)
13. [Known Limitations](#known-limitations)
14. [Rick Shell Animation (Easter Egg)](#rick-shell-animation-easter-egg)

## Overview

Rick Shell provides four modules:

| Module | Description |
|---|---|
| Shell core | File and directory commands, permissions, redirection, pipes, variables, conditionals, and a grep-style search with regular expressions |
| Scheduler | Six CPU scheduling algorithms with a PCB table, Gantt chart, and average times |
| Deadlock | Deadlock detection, Banker's algorithm, resource request handling, and recovery suggestions |
| Comparison | Runs one workload through all six schedulers and reports the best performer per metric |

All algorithms are implemented from scratch. No scheduling or deadlock library is used.

## Requirements

- Python 3.10 or newer
- Standard library only. No packages to install.
- An internet connection only for the optional Rick animation

## Libraries Used

Every module comes from the Python standard library. None of them implements a scheduling or deadlock algorithm; those are all written by hand in `sim/`.

| Module | Used for | Where |
|---|---|---|
| `os`, `shutil` | Paths, directory listing, copying, moving, removing files, terminal size | `shell/builtins/files.py`, `shell/repl.py` |
| `errno` | Turning OS errors into short messages such as `No such file or directory` | `shell/builtins/files.py` |
| `re` | `grep -E` pattern matching, `$NAME` expansion, `NAME=value` detection, `chmod` mode check | `shell/builtins/search.py`, `shell/executor.py`, `shell/builtins/perms.py` |
| `io` | In-memory `StringIO` buffers that carry text between pipeline stages | `shell/executor.py` |
| `sys` | Standard input, output, and error for the prompt loop | `shell/repl.py` |
| `dataclasses` | Tokens, parsed commands, the PCB, and the resource state | `shell/tokenizer.py`, `shell/parser.py`, `sim/pcb.py`, `sim/deadlock.py` |
| `copy` | Fresh copies of the process list for each algorithm in `compare` | `compare/compare.py` |
| `datetime`, `getpass` | Modified time and owner name in `ls -l` | `shell/builtins/perms.py` |
| `typing`, `collections.abc` | Type hints only | Throughout |
| `urllib.request` | Streaming the Rick animation from `ascii.live` | `shell/easter/rick.py` |
| `time` | Animation timing and the pause before it starts | `shell/easter/rick.py`, `shell/repl.py` |
| `unittest` | The test suite | `tests/` |

## Getting Started

From the project root:

```
python main.py
```

The prompt shows the current directory, for example `rickshell >` or `rickshell\demo >`. Type `help` to list all commands and `exit` to quit.

## Project Structure

```
rickshell/
  main.py          Entry point
  shell/           Tokenizer, parser, executor, REPL, and built-in commands
    easter/        The Rick animation (easter egg)
  sim/             PCB, loader, schedulers, metrics, Gantt chart, deadlock simulator
  compare/         The compare command
  data/
    processes/     Sample process files
    resources/     Sample resource files
  tests/           Unit tests and test case descriptions
```

Every command is a function with the same signature, `cmd(args, stdin, stdout, stderr, ctx) -> exit_code`. Redirection swaps the stream objects before a command runs, and pipes pass one command's output as the next command's input.

## Shell Reference

### Commands

| Command | Description |
|---|---|
| `pwd` | Print the current directory |
| `cd [dir]` | Change directory (no argument goes to home) |
| `ls [-l] [-R] [path...]` | List entries. `-l` shows permissions, size, modified time, and name. `-R` lists subdirectories recursively |
| `dir [-l] [-R] [path...]` | Alias for `ls` |
| `mkdir dir...` | Create directories |
| `rmdir dir...` | Remove empty directories |
| `touch file...` | Create a file or update its modified time |
| `cp src dst` | Copy a file |
| `mv src dst` | Move or rename |
| `rm [-r] path...` | Remove files, or directories with `-r` |
| `cat [file...]` | Print files, or standard input when no file is given |
| `chmod MODE file` | Change permissions using a numeric mode (3 or 4 octal digits) |
| `echo words...` | Print arguments |
| `clear` | Clear the terminal screen |
| `env` | List variables as `NAME=value`, sorted |
| `grep [-i] [-n] [-E] [--groups] PATTERN [file...]` | Search lines of text |
| `sched ...` | CPU scheduling simulator |
| `deadlock ...` | Deadlock simulator |
| `compare ...` | Scheduling algorithm comparison |
| `rick [on\|off]` | Terminal animation (see [Rick Shell Animation](#rick-shell-animation-easter-egg)) |
| `true`, `false` | Return exit code 0 or 1, useful for testing `&&`, `\|\|`, and `if` |
| `help` | List all commands |
| `exit` | Quit the shell |

### Redirection and Pipes

| Syntax | Effect |
|---|---|
| `cmd > file` | Write standard output to a file, replacing its contents |
| `cmd >> file` | Append standard output to a file |
| `cmd < file` | Read standard input from a file |
| `cmd 2> file` | Write standard error to a file |
| `cmd 2>&1` | Send standard error to the same place as standard output |
| `cmd1 \| cmd2` | Pass the output of `cmd1` to `cmd2` (any number of stages) |

Redirections are processed left to right, so `cmd > f 2>&1` sends both streams to `f`, while `cmd 2>&1 > f` does not. The exit code of a pipeline is the exit code of its last command.

### Variables and Quoting

- Assign with `NAME=value` and read with `$NAME`.
- Single quotes keep text literal. Double quotes group words and still expand variables.
- An unset variable expands to an empty string.
- `$?` expands to the exit code of the last command.
- Expansion happens at run time, so `X=5 ; echo $X` works on one line.

### Conditional Execution

| Syntax | Effect |
|---|---|
| `a && b` | Run `b` only if `a` succeeded |
| `a \|\| b` | Run `b` only if `a` failed |
| `a ; b` | Always run `b` |
| `if a; then b; else c; fi` | Run `b` if `a` succeeds, otherwise `c`. The `else` part is optional |

A command succeeds when its exit code is 0. The `if` form is written on a single line and cannot be nested.

### Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General failure (for example, a missing file) |
| 2 | Bad arguments, usage, or syntax error |
| 127 | Command not found |

Every error prints a single clear message to standard error. The shell does not terminate on invalid input.

### grep

```
grep [-i] [-n] [-E] [--groups] PATTERN [file...]
```

| Option | Description |
|---|---|
| (none) | Match the pattern as plain text |
| `-i` | Ignore case |
| `-n` | Prefix each line with its line number |
| `-E` | Treat the pattern as a regular expression. Supports `.`, `[a-z]`, `*`, `+`, `?`, backslash escapes, and `( )` groups |
| `--groups` | Implies `-E`. Print the captured groups of the first match after each matching line |

Options may appear before or after the file names. With no file, `grep` reads standard input. It returns 0 when a line matches, 1 when none match, and 2 for a usage error or an invalid pattern.

```
rickshell > grep -E 'h(e)l+o' a.txt --groups
hello
  groups: 1=e
```

## Process Scheduling Simulator

```
sched <fcfs|sjn|priority|rr|mlq|mlfq> [--quantum N] [--trace] <file>
```

| Option | Description |
|---|---|
| `--quantum N` | Time quantum for `rr` and for the top queue of `mlq` (default 4) |
| `--trace` | Print every process state change, for example `t=4 P2 Ready -> Running` |

Each run prints the PCB table before and after the run, a text Gantt chart, a per-process table, and the average turnaround and waiting times. Process states are New, Ready, Running, Waiting, and Terminated.

```
rickshell > sched fcfs data/processes/p_idle_gap.txt

Gantt chart:
| IDLE | P1 | P2 |
0      3    7    9

Results:
PID  Arr  Burst  Prio  Completion  Turnaround  Waiting
P1     3      4     1           7           4        0
P2     5      2     2           9           4        2
Average turnaround: 4.00   Average waiting: 1.00
```

An empty file prints `No processes to schedule.` A malformed line is reported with its line number and the problem.

## Deadlock Simulator

```
deadlock detect <file>
deadlock banker <file>
deadlock banker <file> --request P1 1 0 2
```

| Command | Description |
|---|---|
| `detect` | List the deadlocked processes, or report that none were found. Uses the file's Request matrix when present, otherwise Need. When a deadlock exists, also print a recovery suggestion and a preemption note |
| `banker` | Report whether the state is safe and print the safe sequence, for example `P1 -> P3 -> P4 -> P0 -> P2`. An unsafe state lists the stuck processes |
| `banker --request` | Test a resource request for a process. The result is granted, exceeds the maximum claim, must wait, or is denied because the state would be unsafe |

Requests are evaluated on an in-memory copy, so input files are never modified. The loader rejects wrong dimensions, negative values, and Allocation greater than Max.

```
rickshell > deadlock detect data/resources/unsafe.txt
Deadlock detected. Deadlocked processes: P0, P1
Recovery suggestion: Terminate P0
Preemption note: Preempt R1 from P1
```

## Algorithm Comparison

```
compare <process_file> [--quantum N] [--save <path.md>]
```

Runs all six scheduling algorithms on the same file with the same quantum (default 4). The output contains a table of average waiting and turnaround times, a text bar chart for each metric, and the best algorithm per metric. When several algorithms tie, all are listed. `--save` writes the table as Markdown and creates the target folder if needed.

```
rickshell > compare data/processes/p_basic.txt
Algorithm | Avg waiting | Avg turnaround
----------|-------------|---------------
FCFS      |        8.75 |         15.25
SJN       |        7.75 |         14.25
Priority  |        7.75 |         14.25
RR        |       11.75 |         18.25
MLQ       |        8.75 |         15.25
MLFQ      |       13.00 |         19.50

Best avg waiting: SJN, Priority
Best avg turnaround: SJN, Priority
```

The bar charts are omitted above for brevity.

## Input File Formats

### Process File

One process per line: PID, arrival time, burst time, priority. Blank lines and lines starting with `#` are ignored.

```
# PID arrival burst priority
P1 0 8 2
P2 1 4 1
P3 2 9 3
P4 3 5 2
```

### Resource File

The first line gives the number of processes `n` and resources `m`. It is followed by the Allocation matrix (`n` rows), the Max matrix (`n` rows), and the Available vector (one row). An optional Request matrix (`n` rows) may follow Available; only `deadlock detect` uses it. Processes are named P0, P1, and so on.

```
# n m
5 3
# Allocation
0 1 0
2 0 0
3 0 2
2 1 1
0 0 2
# Max
7 5 3
3 2 2
9 0 2
2 2 2
4 3 3
# Available
3 3 2
```

With a Request matrix (`data/resources/detect_request.txt`), the state is unsafe for Banker's algorithm but not deadlocked:

```
rickshell > deadlock banker data/resources/detect_request.txt
UNSAFE state. Stuck processes: P0, P1, P2
rickshell > deadlock detect data/resources/detect_request.txt
Using the Request matrix from the file.
No deadlock found.
```

### Sample Data

| Folder | Files |
|---|---|
| `data/processes/` | `p_basic`, `p_single`, `p_empty`, `p_idle_gap`, `p_ties`, `p_bad_line` |
| `data/resources/` | `safe`, `unsafe`, `single`, `empty`, `bad_dims`, `deadlock_chain`, `detect_request` |

## Algorithm Conventions

### Scheduling

| Algorithm | Rules |
|---|---|
| FCFS | Run in order of arrival. Ties by input order |
| SJN | Non-preemptive. Pick the arrived process with the shortest burst. Ties by arrival, then input order |
| Priority | Non-preemptive. A lower number means higher priority. Ties by arrival, then input order |
| Round-Robin | A process runs for the quantum or its remaining time, then returns to the back of the queue. If an arrival and a requeue occur at the same moment, the arrival is queued first |
| Multilevel Queue | Priority 1 or 2 goes to Queue 0 (Round-Robin), all others to Queue 1 (FCFS). Queue 0 is always served first and preempts Queue 1, whose process returns to the head of its queue. Processes never change queues |
| Multilevel Feedback Queue | Three levels with quanta 2, 4, and FCFS. New processes start at Level 0. Using a full quantum demotes a process one level. An arrival at a higher level preempts a lower one, which goes to the back of its own queue |

When no process is ready, the CPU is shown as IDLE until the next arrival.

Turnaround time is Completion - Arrival. Waiting time is Turnaround - Burst. Averages are printed to two decimal places.

### Deadlock

- **Need matrix:** Need = Max - Allocation.
- **Detection:** Start with Work = Available. Repeatedly finish any process whose Need fits in Work, adding its Allocation back to Work. Processes that can never finish are deadlocked. The Request matrix is used when the file has one. Otherwise Need is treated as each process's potential request, which makes detection give the same answer as the safety check.
- **Safety check:** The same loop. If every process finishes, the state is safe and the finishing order is the safe sequence.
- **Resource request:** Reject if the request exceeds Need. Wait if it exceeds Available. Otherwise allocate on a copy, run the safety check, and grant only if the result is safe.
- **Recovery suggestion:** Repeatedly suggest terminating the deadlocked process that holds the most resources (ties: lowest PID), release its resources, and run detection again until no deadlock remains. This is a heuristic and is not guaranteed to be optimal.

## Testing

```
python -m unittest discover -s tests -t .
```

The suite covers the tokenizer, redirection, pipes, variables, conditionals, error handling, grep (plain and regular expression), all six schedulers with hand-calculated expected values, deadlock detection, Banker's algorithm, request handling, recovery suggestions, and the compare command. Each simulator is tested with at least three inputs, including an empty or single-process edge case.

The test inputs and their expected results are described in `tests/test_cases.md`.

## Known Limitations

- `if` statements are single-line and cannot be nested.
- `chmod` accepts numeric modes only. Modes are simulated and last for the current session.
- Only the built-in commands listed above are available. External programs cannot be run.
- Pipelines run one stage at a time. Each stage finishes before the next begins, so stages do not run concurrently.
- The comparison samples are small, so their conclusions may not generalize to larger workloads.

## Rick Shell Animation (Easter Egg)

Rick Shell includes an easter egg: the classic "Rickroll" ASCII-art animation, streamed live from [ascii.live](https://ascii.live/rick). 

### Commands

| Command | Description |
|---|---|
| `rick` | Play the animation now, until Ctrl+C is pressed |
| `rick off` | Turn off the animation after unknown commands |
| `rick on` | Turn on the animation after unknown commands (default) |

### When it plays

The animation triggers only after entering any bad command and can be stop by clicking crtl + c command.

```
rickshell > foo
rickshell: foo: command not found
Press Ctrl+C to stop
```

### How it works

- `shell/easter/rick.py` opens `https://ascii.live/rick` with the standard-library `urllib.request` module. No third-party package is used.
- The service streams frames as text separated by the "cursor home" terminal code. The shell buffers the stream, splits it into whole frames, and strips any other escape codes.
- Each frame is shrunk to fit the current terminal window, then drawn on the terminal's alternate screen. On exit or Ctrl+C the original screen and cursor are restored, so earlier output is not lost.
