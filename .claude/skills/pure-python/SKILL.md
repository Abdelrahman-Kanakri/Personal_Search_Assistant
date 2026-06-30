---
name: pure-python
description: Use when writing standalone Python logic — a module, script, CLI, function, class, or data structure — in plain Python with the standard library. Triggers "write a python script", "a function/class to…", "a small CLI", "parse this file", "implement X in python". NOT for ML/DL (use ml-experiment / pytorch-training), data wrangling (use data-prep / eda), or LangGraph (use langgraph-node).
---

# Skill: Idiomatic Pure Python

Reach for the standard library before adding a dependency. Most "I need a package"
moments are already solved by `collections`, `itertools`, `functools`, `dataclasses`,
`enum`, `pathlib`, or `contextlib`. (Baseline rules — type hints, `uv`, ruff, no bare
except — come from rules/python.md and still apply.)

## Pick the right shape for data
- **`@dataclass`** — a record with behavior or defaults. Use `slots=True` for many
  instances, `frozen=True` for immutable values.
- **`enum.Enum`** — a fixed set of named choices. Replaces magic strings/ints.
- **`NamedTuple`** — a small immutable, unpacking-friendly return value.
- **plain `dict`** — only for truly dynamic keys. If keys are known, use a dataclass.

```python
from dataclasses import dataclass
from enum import Enum

class Status(Enum):
    PENDING = "pending"
    DONE = "done"

@dataclass(slots=True)
class Task:
    title: str
    status: Status = Status.PENDING
```

## Reach for these instead of hand-rolling
- `collections.Counter` — counting/frequency. `defaultdict` — grouping.
- `collections.deque` — a queue/stack (O(1) ends; a list is O(n) at the front).
- `itertools` — `chain`, `groupby`, `islice`, `product`, `pairwise` (3.10+).
- `functools` — `@cache`/`@lru_cache` for memoization, `partial`, `reduce`.
- `pathlib.Path` — paths, globbing, read/write text. Never string-concat paths.

```python
from collections import Counter, defaultdict

Counter(words).most_common(3)            # top-3 in one line

groups: dict[str, list[int]] = defaultdict(list)
for item in items:
    groups[item.key].append(item.value)  # no "if key not in" dance
```

## Style that reads as native Python
- **EAFP, not LBYL** — try the operation, catch the specific error; don't pre-check.
- **Comprehensions** for map/filter; a generator (`(... for ...)`) when you don't need
  the whole list in memory. Stop nesting them past two levels — use a loop.
- **Unpacking** over indexing: `first, *rest = seq`; `a, b = b, a` to swap.
- **`with`** for anything that opens/closes (files, locks). Write a context manager
  with `@contextlib.contextmanager` for your own setup/teardown pairs.
- **Truthiness**: `if items:` not `if len(items) > 0:`; `is None` for None checks.

```python
# EAFP: attempt, then handle the one error that matters
try:
    value = config["timeout"]
except KeyError:
    value = DEFAULT_TIMEOUT
```

## CLI / script entry
```python
def main() -> int:
    ...
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```
Use `argparse` for flags before reaching for a CLI framework.

End by naming any anti-pattern avoided (e.g. mutable default arg, manual file close)
and why the idiomatic form is safer — that's the teaching part.
