"""Core utilities shared by every solver.

Contents
--------
* ``generate_instance``  - CTA-style generator (uncorrelated / weak / strong correlation)
* ``sort_items``         - ratio ordering (non-increasing v/w, ties broken by original index)
* ``evaluate_node``      - Dantzig relaxation + greedy integer heuristic for a node with fixings
* ``dynamic_programming``- exact O(nC) DP with item reconstruction
* ``exhaustive``         - brute-force optimum (used only for validation, n <= ~20)
"""
from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence, Tuple

CLASSES = ("uncorrelated", "weak", "strong")
R_DEFAULT = 100  # coefficient range used by the paper


# --------------------------------------------------------------------------- #
# Instance generation
# --------------------------------------------------------------------------- #
def instance_seed(correlation: str, n: int, replicate: int, base: int = 20260914) -> int:
    """Deterministic seed that varies by class, size and replicate (Section II-E.1)."""
    return base + CLASSES.index(correlation) * 1_000_000 + n * 1_000 + replicate


def generate_instance(
    n: int,
    correlation: str,
    seed: int,
    R: int = R_DEFAULT,
    capacity_fraction: float = 0.5,
) -> Tuple[List[int], List[int], int]:
    """Return ``(weights, values, capacity)``.

    uncorrelated : w, v ~ U[1, R]
    weak         : v ~ U[max(1, w - R/10), w + R/10]
    strong       : v = w + R/10
    capacity     : floor(capacity_fraction * sum(w)), clipped so that 0 < C < sum(w)
    """
    if correlation not in CLASSES:
        raise ValueError(f"unknown correlation class: {correlation}")
    rng = random.Random(seed)
    w = [rng.randint(1, R) for _ in range(n)]
    d = R // 10
    if correlation == "uncorrelated":
        v = [rng.randint(1, R) for _ in range(n)]
    elif correlation == "weak":
        v = [rng.randint(max(1, wi - d), wi + d) for wi in w]
    else:
        v = [wi + d for wi in w]
    total = sum(w)
    cap = int(math.floor(capacity_fraction * total))
    cap = max(1, min(cap, total - 1))
    return w, v, cap


def sort_items(w: Sequence[int], v: Sequence[int]):
    """Order items by non-increasing v/w, ties broken by original index.

    Returns ``(order, ws, vs)`` where ``order[k]`` is the original index of the
    k-th sorted item.
    """
    order = sorted(range(len(w)), key=lambda i: (-v[i] / w[i], i))
    return order, [w[i] for i in order], [v[i] for i in order]


# --------------------------------------------------------------------------- #
# Node evaluation (Dantzig relaxation + greedy heuristic)
# --------------------------------------------------------------------------- #
class NodeEval:
    """Result of evaluating a node (all fields are plain Python objects).

    ub        integer upper bound = floor(Dantzig bound)  (values are integers)
    hv        value of the feasible integer heuristic solution
    selected  indices of *unfixed* items chosen by the heuristic (ascending)
    brk       index of the fractional (break) item, or None when relaxation is integral
    """

    __slots__ = ("ub", "hv", "selected", "brk", "fixed_ones")

    def __init__(self, ub, hv, selected, brk, fixed_ones):
        self.ub = ub
        self.hv = hv
        self.selected = selected
        self.brk = brk
        self.fixed_ones = fixed_ones

    @property
    def integral(self) -> bool:
        return self.brk is None


def evaluate_node(ws: Sequence[int], vs: Sequence[int], cap: int, fixed) -> Optional[NodeEval]:
    """Solve the Dantzig relaxation and build the greedy heuristic for ``fixed``.

    ``fixed[i]`` is 1 (forced in), 0 (forced out) or None (free).  Returns None
    when the fixed-one items alone exceed the capacity (infeasible node).

    The heuristic keeps every whole item of the relaxation, sets the break item
    to zero and then keeps scanning later free items, taking each that still
    fits.  The resulting set is *maximal*, which is what makes the cascade
    partition of Property 1 exact.
    """
    n = len(ws)
    fw = 0
    fv = 0
    ones = []
    for i in range(n):
        if fixed[i] == 1:
            fw += ws[i]
            fv += vs[i]
            ones.append(i)
    if fw > cap:
        return None
    rem = cap - fw
    ub = fv
    hv = fv
    selected = []
    brk = None
    for i in range(n):
        if fixed[i] is not None:
            continue
        if ws[i] <= rem:
            rem -= ws[i]
            ub += vs[i]
            hv += vs[i]
            selected.append(i)
        else:
            brk = i
            ub += (vs[i] * rem) // ws[i]  # floor of fractional part (integer data)
            # heuristic continues with later free items
            for j in range(i + 1, n):
                if fixed[j] is None and ws[j] <= rem:
                    rem -= ws[j]
                    hv += vs[j]
                    selected.append(j)
            break
    return NodeEval(ub, hv, tuple(selected), brk, tuple(ones))


# --------------------------------------------------------------------------- #
# Dynamic programming (reconstruction-capable, two-dimensional table)
# --------------------------------------------------------------------------- #
def dynamic_programming(ws: Sequence[int], vs: Sequence[int], cap: int):
    """Exact DP in O(nC) time and space. Returns ``(value, selected_indices)``."""
    n = len(ws)
    table = [[0] * (cap + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        wi, vi = ws[i - 1], vs[i - 1]
        prev = table[i - 1]
        cur = table[i]
        for c in range(cap + 1):
            best = prev[c]
            if wi <= c:
                cand = vi + prev[c - wi]
                if cand > best:
                    best = cand
            cur[c] = best
    c = cap
    chosen = []
    for i in range(n, 0, -1):
        if table[i][c] != table[i - 1][c]:
            chosen.append(i - 1)
            c -= ws[i - 1]
    chosen.sort()
    return table[n][cap], chosen


# --------------------------------------------------------------------------- #
# Exhaustive enumeration (validation reference)
# --------------------------------------------------------------------------- #
def exhaustive(ws: Sequence[int], vs: Sequence[int], cap: int):
    """Brute-force optimum over all 2^n subsets. Returns ``(value, indices)``."""
    n = len(ws)
    best_val, best_mask = 0, 0
    for mask in range(1 << n):
        tw = tv = 0
        for i in range(n):
            if mask >> i & 1:
                tw += ws[i]
                tv += vs[i]
        if tw <= cap and tv > best_val:
            best_val, best_mask = tv, mask
    return best_val, [i for i in range(n) if best_mask >> i & 1]
