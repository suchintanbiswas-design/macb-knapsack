"""Measured execution of one (instance, method, budget) configuration.

Protocol (Section II-E.2): garbage collection, start ``tracemalloc``, run the
solver once under a wall-clock deadline (DP is exempt), stop ``tracemalloc``
immediately.  Objective values and feasibility are always recomputed from the
returned item set rather than trusted from solver state.
"""
from __future__ import annotations

import gc
import time
import tracemalloc
from typing import Dict, Optional, Sequence

from .core import dynamic_programming
from .solvers import cta, macb, standard_bnb

METHOD_LABELS = {"dp": "DP", "std_bnb": "Std. B&B", "cta": "CTA", "macb": "MACB"}


def recompute(w: Sequence[int], v: Sequence[int], cap: int, items: Sequence[int]):
    """Return ``(value, weight, feasible, valid_indices)`` computed from the item set."""
    n = len(w)
    valid = len(set(items)) == len(items) and all(0 <= i < n for i in items)
    if not valid:
        return 0, 0, False, False
    tw = sum(w[i] for i in items)
    tv = sum(v[i] for i in items)
    return tv, tw, tw <= cap, True


def run_method(
    method: str,
    w: Sequence[int],
    v: Sequence[int],
    cap: int,
    order: Sequence[int],
    ws: Sequence[int],
    vs: Sequence[int],
    budget: Optional[int] = None,
    time_limit: Optional[float] = 3.0,
) -> Dict:
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    deadline = None if (method == "dp" or time_limit is None) else t0 + time_limit
    if method == "dp":
        val, idx = dynamic_programming(ws, vs, cap)
        res = dict(value=val, items=tuple(idx), timed_out=False)
    elif method == "std_bnb":
        res = standard_bnb(ws, vs, cap, deadline)
    elif method == "cta":
        res = cta(ws, vs, cap, deadline)
    elif method == "macb":
        res = macb(ws, vs, cap, budget, deadline)
    else:
        tracemalloc.stop()
        raise ValueError(method)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    items = sorted(order[i] for i in res["items"])
    val, wt, feasible, valid = recompute(w, v, cap, items)
    out = dict(res)
    out.update(
        method=method,
        budget=budget if method == "macb" else "",
        time_ms=elapsed * 1000.0,
        peak_kb=peak / 1024.0,
        value_reported=res["value"],
        value=val,
        weight=wt,
        feasible=feasible and valid,
        items=" ".join(map(str, items)),
    )
    return out
