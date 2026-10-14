#!/usr/bin/env python3
"""Run the full benchmark of the paper (Section II-E).

* Reproduction suite : 3 classes x n in {10,20,30,40,50} x 5 seeds = 75 instances
* Extended suite     : 3 classes x n in {100,200}       x 2 seeds = 12 instances
* Methods            : DP, standard B&B, CTA, MACB with B in {4,8,16,32,64}
* Deadline           : 3 s inside every tree-search loop (DP is exempt)
* Each configuration is executed once; peak memory is the tracemalloc peak.

Outputs
-------
data/instances.csv              every generated instance (weights, values, capacity, seed)
results/benchmark_results.csv   one row per (instance, method, budget) = 696 rows
"""
import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from macb import CLASSES, generate_instance, instance_seed, run_method, sort_items  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BUDGETS = (4, 8, 16, 32, 64)
REPRO_N = (10, 20, 30, 40, 50)
EXT_N = (100, 200)

FIELDS = ["instance_id", "suite", "correlation", "n", "replicate", "seed", "capacity",
          "method", "budget", "value", "value_reported", "weight", "feasible", "correct_vs_dp",
          "timed_out", "time_ms", "peak_kb",
          "generated", "explored", "pruned", "infeasible",
          "peak_active", "peak_deferred", "peak_logical",
          "cascades", "children", "max_fanout", "immediate", "deferrals", "activations", "items"]


def instances(quick=False):
    reps_repro = 2 if quick else 5
    for n in REPRO_N:
        if quick and n > 30:
            continue
        for cls in CLASSES:
            for r in range(reps_repro):
                yield "reproduction", cls, n, r
    if not quick:
        for n in EXT_N:
            for cls in CLASSES:
                for r in range(2):
                    yield "extended", cls, n, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--time-limit", type=float, default=3.0)
    ap.add_argument("--quick", action="store_true", help="small smoke-test subset")
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "benchmark_results.csv"))
    ap.add_argument("--instances-out", default=os.path.join(ROOT, "data", "instances.csv"))
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    os.makedirs(os.path.dirname(args.instances_out), exist_ok=True)

    rows, inst_rows = [], []
    t_start = time.time()
    for suite, cls, n, rep in instances(args.quick):
        seed = instance_seed(cls, n, rep)
        w, v, cap = generate_instance(n, cls, seed)
        iid = f"{'rep' if suite == 'reproduction' else 'ext'}_{cls}_n{n:03d}_r{rep}"
        inst_rows.append(dict(instance_id=iid, suite=suite, correlation=cls, n=n, replicate=rep, seed=seed,
                              capacity=cap, weights=" ".join(map(str, w)), values=" ".join(map(str, v))))
        order, ws, vs = sort_items(w, v)
        dp = run_method("dp", w, v, cap, order, ws, vs, time_limit=None)
        configs = [("dp", None), ("std_bnb", None), ("cta", None)] + [("macb", b) for b in BUDGETS]
        for method, b in configs:
            r = dp if method == "dp" else run_method(method, w, v, cap, order, ws, vs, budget=b, time_limit=args.time_limit)
            row = {k: r.get(k, "") for k in FIELDS}
            row.update(instance_id=iid, suite=suite, correlation=cls, n=n, replicate=rep, seed=seed, capacity=cap,
                       method=method, budget=b if b else "",
                       correct_vs_dp=(r["value"] == dp["value"]) if not r["timed_out"] else "",
                       time_ms=round(r["time_ms"], 4), peak_kb=round(r["peak_kb"], 3))
            rows.append(row)
        print(f"[{time.time() - t_start:7.1f}s] {iid}", flush=True)

    with open(args.out, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS)
        wr.writeheader()
        wr.writerows(rows)
    with open(args.instances_out, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(inst_rows[0].keys()))
        wr.writeheader()
        wr.writerows(inst_rows)
    done = [r for r in rows if not r["timed_out"]]
    bad = [r for r in done if r["correct_vs_dp"] is False]
    print(f"rows: {len(rows)}  completed: {len(done)}  timeouts: {len(rows) - len(done)}  wrong: {len(bad)}")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
