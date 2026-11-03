# Test Cases

This document describes the test inputs, expected results, and edge cases used to verify Rick Shell.

## Running the Tests

```
python -m unittest discover -s tests -t .
```

The suite uses `unittest` and lives in `tests/`. Shell commands are tested by calling them with in-memory streams (`io.StringIO`) and comparing the output text and exit code. Tests that touch the file system use temporary directories.

## Test Inputs

### Scheduler (`data/processes/`)

| File | Contents | Purpose |
|---|---|---|
| `p_basic.txt` | P1 0 8 2, P2 1 4 1, P3 2 9 3, P4 3 5 2 | Standard workload used for all six algorithms |
| `p_single.txt` | One process | Edge case: a single process |
| `p_empty.txt` | Comments only | Edge case: empty input |
| `p_idle_gap.txt` | P1 3 4 1, P2 5 2 2 | Edge case: CPU idle before the first arrival |
| `p_ties.txt` | P1 0 4 2, P2 0 4 2, P3 0 3 1 | Equal arrival, burst, and priority values |
| `p_bad_line.txt` | A malformed line | Error reporting with a line number |

### Deadlock (`data/resources/`)

| File | Contents | Purpose |
|---|---|---|
| `safe.txt` | 5 processes, 3 resources | Safe state with a safe sequence |
| `unsafe.txt` | 2 processes, 2 resources, Available 0 0 | Both processes deadlocked |
| `deadlock_chain.txt` | 3 processes, 1 resource, Available 0 | Recovery needing two terminations |
| `single.txt` | One process | Edge case: a single process |
| `empty.txt` | n = 0 | Edge case: no processes |
| `bad_dims.txt` | Wrong number of rows | Validation error |

## Scheduler Expected Results

### `p_basic.txt` (quantum 4)

Expected values were calculated by hand and checked against the program output.

| Algorithm | Completion times | Avg waiting | Avg turnaround |
|---|---|---|---|
| FCFS | P1 8, P2 12, P3 21, P4 26 | 8.75 | 15.25 |
| SJN | P1 8, P2 12, P4 17, P3 26 | 7.75 | 14.25 |
| Priority | P1 8, P2 12, P4 17, P3 26 | 7.75 | 14.25 |
| Round-Robin | P1 20, P2 8, P3 26, P4 25 | 11.75 | 18.25 |
| Multilevel Queue | P1 16, P2 8, P4 17, P3 26 | 8.75 | 15.25 |
| Multilevel Feedback Queue | P1 23, P2 14, P3 26, P4 21 | 13.00 | 19.50 |

Gantt charts:

```
FCFS   | P1 | P2 | P3 | P4 |
       0    8    12   21   26

RR     | P1 | P2 | P3 | P4 | P1 | P3 | P4 | P3 |
       0    4    8    12   16   20   24   25   26

MLFQ   | P1 | P2 | P3 | P4 | P1 | P2 | P3 | P4 | P1 | P3 |
       0    2    4    6    8    12   14   18   21   23   26
```

### Other scheduler inputs

| Input | Expected result |
|---|---|
| `p_idle_gap.txt` | Gantt `\| IDLE \| P1 \| P2 \|` with boundaries 0, 3, 7, 9. Completions 7 and 9. Average turnaround 4.00, average waiting 1.00, identical for all six algorithms |
| `p_ties.txt` | FCFS 4.00 / 7.67. SJN and Priority 3.33 / 7.00 (P3 first, then P1, P2). Ties are broken by input order |
| `p_single.txt` | All six algorithms give the same result. Waiting time 0 |
| `p_empty.txt` | `No processes to schedule.` and a clean return |
| `p_bad_line.txt` | An error that names the line number and the problem |

## Deadlock Expected Results

| Input | Command | Expected result |
|---|---|---|
| `safe.txt` | `deadlock banker` | Safe, sequence `P1 -> P3 -> P4 -> P0 -> P2` |
| `safe.txt` | `deadlock detect` | No deadlock found, no recovery output |
| `unsafe.txt` | `deadlock detect` | Deadlocked: P0, P1. Recovery suggestion `Terminate P0`. Preemption note `Preempt R1 from P1` |
| `deadlock_chain.txt` | `deadlock detect` | All three deadlocked. Recovery order P0, then P1 |

### Resource request cases (`safe.txt`)

| Request | Expected result |
|---|---|
| `P1 1 0 2` | Granted, with safe sequence `P1 -> P3 -> P4 -> P0 -> P2` |
| A request larger than the process's Need | Error: exceeds maximum claim |
| A request larger than Available | The process must wait and is marked Waiting |
| A request that leaves an unsafe state | Denied, original state unchanged (rollback) |
| Unknown process or wrong vector length | Usage error, no exception |

## Shell Test Coverage

| Area | Test files | Cases covered |
|---|---|---|
| Tokenizer | `test_tokenizer.py` | Empty and whitespace-only lines, quotes, operators with and without spaces, descriptor redirects, unclosed quote (syntax error), lone `&` |
| Parser | `test_parser.py` | Simple commands, redirect order, three-stage pipelines, connectors, trailing semicolon, syntax errors |
| Executor | `test_executor.py` | Variables and expansion, quoting rules, `$?`, `&&` / `\|\|` / `;`, two- and three-stage pipes, `>`, `>>`, `<`, `2>`, `2>&1` ordering, unknown command, unset variables |
| File commands | `test_files.py` | `pwd`, `cd`, `ls` (plain, long, recursive, hidden entries), `mkdir`, `rmdir`, `touch`, `cp`, `mv`, `rm`, `cat` (file, missing file, stdin), missing operands |
| Permissions | `test_perms.py` | `chmod 755` and `644`, four-digit modes, invalid mode, missing file, `ls -l` display |
| grep | `test_grep.py` | Plain match, `-i`, `-n`, no match returns 1, stdin, multiple files, missing file, invalid option, empty file |
| Regex grep | `test_grep_regex.py` | `-E` features, `--groups`, escaped characters, character classes, invalid pattern returns 2, pipe input, line numbers |
| if/then/else | `test_if.py` | True and false conditions, no `else`, missing `fi` or `then`, nested `if` rejected, `then` as an ordinary argument, `if` followed by more items |
| Prompt and REPL | `test_repl.py`, `test_skeleton.py` | Prompt format at each directory depth, `help`, `exit`, unknown command returns 127 |
| Easter egg | `test_rick.py` | Terminal-only output, screen restored after interruption, offline behavior, automatic triggers, on/off toggle, window scaling |

### Error cases

None of these may raise an exception. Each prints one line to standard error.

| Input | Expected message |
|---|---|
| `foo` | `rickshell: foo: command not found` (exit 127) |
| `cat missing.txt` | `cat: missing.txt: No such file or directory` |
| `chmod abc file` | Invalid mode message (3 or 4 octal digits) |
| `grep -E 'h(e' a.txt` | `grep: invalid pattern: ...` (exit 2) |
| `\| ls` | Syntax error |
| `if cat a.txt; then echo found` | `syntax error: expected 'fi'` (exit 2) |
| `compare file --quantum 0` | `compare: --quantum requires a positive integer` |

## Simulator Test Coverage

Each simulator is tested with more than three inputs, including empty and single-process cases.

| Area | Test files | Cases covered |
|---|---|---|
| Loaders, PCB, metrics, Gantt | `test_sim_basics.py` | Comments and blank lines, empty file, bad line number, validation errors, missing file, process defaults, exact Gantt layout, merging adjacent segments, idle metrics |
| FCFS, SJN, Priority | `test_sched_basic.py`, `test_sched_command.py` | Hand-calculated metrics, idle gap, ties, single process, empty list, list reuse, option order, usage and load errors |
| Round-Robin | `test_sched_rr.py` | Hand-calculated schedules, arrival at completion time, arrival at quantum end before the requeued process, quantum 1, large quantum, invalid quantum, trace |
| Multilevel Queue | `test_mlq.py`, `test_sched_mlq.py` | Queue 0 preempts Queue 1, preempted process returns to the head, Queue 1 is FCFS, Queue 0 matches Round-Robin, idle gap, single and empty input, trace order |
| Multilevel Feedback Queue | `test_sched_mlfq.py` | Demotion after a full quantum, level 0 preempts level 2, fresh quantum after preemption, short jobs finish without demotion, trace |
| Deadlock loader and detection | `test_deadlock_basics.py`, `test_deadlock_command.py` | Sample files, invalid inputs, wrong row width, negative values, partial deadlock, state never modified, usage errors |
| Banker's requests | `test_deadlock_request.py` | Granted, exceeded, wait, unsafe denied with rollback, zero vector, invalid requests, plain `banker` output unchanged |
| Recovery | `test_deadlock_recovery.py` | Unsafe sample, two-step chain, safe state prints nothing, single and empty states |
| Compare | `test_compare.py` | Averages and best algorithms on `p_basic.txt`, empty and single process, `--save` creates the folder and lists all six names, missing file and bad quantum |