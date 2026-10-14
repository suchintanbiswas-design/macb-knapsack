"""Exact tree-search solvers compared in the paper.

* ``standard_bnb``  - Algorithm 2: best-bound branch and bound with binary branching
* ``cta``           - Algorithm 3: Cascading-Tree Algorithm (Moeini, Schermer & Wendt, 2024)
* ``macb``          - Algorithm 4: Memory-Aware Cascading Branch and Bound (this paper)

All solvers expect items already sorted by non-increasing v/w (see
``core.sort_items``) and return a plain ``dict`` of results and counters.
Item indices in the result refer to the *sorted* order; ``runner.run_method``
maps them back to original indices.

Tie-breaking inside every heap is first-in-first-out among equal bounds, which
keeps traversal order deterministic (Section II-C.2).
"""
from __future__ import annotations

import heapq
import time
from typing import Optional

from .core import evaluate_node


class _Incumbent:
    __slots__ = ("z", "items")

    def __init__(self):
        self.z = 0
        self.items = ()

    def update(self, ev) -> None:
        if ev.hv > self.z:
            self.z = ev.hv
            self.items = ev.fixed_ones + ev.selected


def _new_stats() -> dict:
    return dict(
        generated=0, explored=0, pruned=0, infeasible=0,
        peak_active=0, peak_deferred=0, peak_logical=0,
        immediate=0, deferrals=0, activations=0,
        cascades=0, children=0, max_fanout=0,
    )


def _finish(inc: _Incumbent, st: dict, timed_out: bool) -> dict:
    out = dict(st)
    out["value"] = inc.z
    out["items"] = tuple(sorted(inc.items))
    out["timed_out"] = timed_out
    return out


def _cascade_children(fixed, ev):
    """Yield the r cascade children of a node (Section II-B.3).

    With heuristic-selected free items i_1..i_r, child t fixes i_1..i_{t-1}=1
    and i_t=0.  Together with the heuristic's own all-ones region the children
    partition the parent's feasible set (Property 1).
    """
    cur = list(fixed)
    for idx in ev.selected:
        child = cur[:]
        child[idx] = 0
        yield tuple(child)
        cur[idx] = 1


# --------------------------------------------------------------------------- #
# Algorithm 2 - standard best-bound B&B with binary branching
# --------------------------------------------------------------------------- #
def standard_bnb(ws, vs, cap, deadline: Optional[float] = None) -> dict:
    n = len(ws)
    st = _new_stats()
    inc = _Incumbent()
    root_fixed = (None,) * n
    root = evaluate_node(ws, vs, cap, root_fixed)
    st["generated"] = 1
    inc.update(root)
    heap, counter = [], 0
    if not root.integral and root.ub > inc.z:
        heapq.heappush(heap, (-root.ub, counter, root_fixed, root))
        counter += 1
    st["peak_active"] = st["peak_logical"] = len(heap)
    timed_out = False
    while heap:
        if deadline is not None and time.perf_counter() > deadline:
            timed_out = True
            break
        neg_ub, _, fixed, ev = heapq.heappop(heap)
        if -neg_ub <= inc.z:
            st["pruned"] += 1
            continue
        st["explored"] += 1
        k = ev.brk
        for d in (1, 0):
            fx = list(fixed)
            fx[k] = d
            fx = tuple(fx)
            child = evaluate_node(ws, vs, cap, fx)
            if child is None:
                st["infeasible"] += 1
                continue
            st["generated"] += 1
            inc.update(child)
            if child.integral:
                continue
            if child.ub <= inc.z:
                st["pruned"] += 1
                continue
            heapq.heappush(heap, (-child.ub, counter, fx, child))
            counter += 1
        if len(heap) > st["peak_active"]:
            st["peak_active"] = st["peak_logical"] = len(heap)
    return _finish(inc, st, timed_out)


# --------------------------------------------------------------------------- #
# Algorithm 3 - Cascading-Tree Algorithm
# --------------------------------------------------------------------------- #
def cta(ws, vs, cap, deadline: Optional[float] = None) -> dict:
    n = len(ws)
    st = _new_stats()
    inc = _Incumbent()
    root_fixed = (None,) * n
    root = evaluate_node(ws, vs, cap, root_fixed)
    st["generated"] = 1
    inc.update(root)
    heap, counter = [], 0
    if not root.integral and root.ub > inc.z:
        heapq.heappush(heap, (-root.ub, counter, root_fixed, root))
        counter += 1
    st["peak_active"] = st["peak_logical"] = len(heap)
    timed_out = False
    while heap:
        if deadline is not None and time.perf_counter() > deadline:
            timed_out = True
            break
        neg_ub, _, fixed, ev = heapq.heappop(heap)
        if -neg_ub <= inc.z:
            st["pruned"] += 1
            continue
        st["explored"] += 1
        st["cascades"] += 1
        r = len(ev.selected)
        st["children"] += r
        st["max_fanout"] = max(st["max_fanout"], r)
        for fx in _cascade_children(fixed, ev):
            child = evaluate_node(ws, vs, cap, fx)
            if child is None:
                st["infeasible"] += 1
                continue
            st["generated"] += 1
            inc.update(child)
            if child.integral:
                continue
            if child.ub <= inc.z:
                st["pruned"] += 1
                continue
            heapq.heappush(heap, (-child.ub, counter, fx, child))
            counter += 1
        if len(heap) > st["peak_active"]:
            st["peak_active"] = st["peak_logical"] = len(heap)
    return _finish(inc, st, timed_out)


# --------------------------------------------------------------------------- #
# Algorithm 4 - Memory-Aware Cascading Branch and Bound (MACB)
# --------------------------------------------------------------------------- #
def macb(ws, vs, cap, budget: int, deadline: Optional[float] = None) -> dict:
    """CTA with an active-node budget ``budget`` (B >= 1).

    * Active heap ``A``   : fully evaluated nodes, never more than B at once (Eq. 2).
    * Deferred heap ``D`` : lightweight descriptors (fixings, inherited parent bound).
      A descriptor's stored bound is the parent's UB, which is admissible because
      F(child) is a subset of F(parent) (Property 3).
    """
    if budget < 1:
        raise ValueError("budget must be >= 1")
    n = len(ws)
    st = _new_stats()
    inc = _Incumbent()
    A, D = [], []            # max-heaps via negated keys
    counter = 0
    root_fixed = (None,) * n
    root = evaluate_node(ws, vs, cap, root_fixed)
    st["generated"] = 1
    inc.update(root)
    if not root.integral and root.ub > inc.z:
        heapq.heappush(A, (-root.ub, counter, root_fixed, root))
        counter += 1

    def record():
        a, d = len(A), len(D)
        if a > st["peak_active"]:
            st["peak_active"] = a
        if d > st["peak_deferred"]:
            st["peak_deferred"] = d
        if a + d > st["peak_logical"]:
            st["peak_logical"] = a + d

    record()
    timed_out = False
    while A or (D and -D[0][0] > inc.z):
        if deadline is not None and time.perf_counter() > deadline:
            timed_out = True
            break
        # discard descriptors whose admissible stored bound cannot beat the incumbent
        if D and -D[0][0] <= inc.z:
            st["pruned"] += len(D)
            D.clear()
        # activate deferred descriptors while slots are free and they can compete
        while len(A) < budget and D and -D[0][0] > inc.z and (not A or -D[0][0] >= -A[0][0]):
            neg_ub, _, fixed = heapq.heappop(D)
            st["activations"] += 1
            ev = evaluate_node(ws, vs, cap, fixed)
            if ev is None:
                st["infeasible"] += 1
                continue
            st["generated"] += 1
            inc.update(ev)
            if ev.integral:
                continue
            if ev.ub <= inc.z:
                st["pruned"] += 1
                continue
            heapq.heappush(A, (-ev.ub, counter, fixed, ev))
            counter += 1
        if not A:
            record()
            continue
        neg_ub, _, fixed, ev = heapq.heappop(A)
        if -neg_ub <= inc.z:
            st["pruned"] += 1
            continue
        st["explored"] += 1
        st["cascades"] += 1
        r = len(ev.selected)
        st["children"] += r
        st["max_fanout"] = max(st["max_fanout"], r)
        parent_ub = ev.ub
        for fx in _cascade_children(fixed, ev):
            if len(A) < budget:                      # an active slot exists
                child = evaluate_node(ws, vs, cap, fx)
                st["immediate"] += 1
                if child is None:
                    st["infeasible"] += 1
                    continue
                st["generated"] += 1
                inc.update(child)
                if child.integral:
                    continue
                if child.ub <= inc.z:
                    st["pruned"] += 1
                    continue
                heapq.heappush(A, (-child.ub, counter, fx, child))
            else:                                    # defer with the inherited bound
                st["deferrals"] += 1
                heapq.heappush(D, (-parent_ub, counter, fx))
            counter += 1
        record()
    return _finish(inc, st, timed_out)
