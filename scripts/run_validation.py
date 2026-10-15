#!/usr/bin/env python3
"""Exhaustive-enumeration validation (Section II-E.3).

241 instances = the working five-item example + 240 random instances with
n <= 12 (80 per correlation class).  DP, standard B&B, CTA and MACB at every
budget must return the exhaustive optimum with a feasible, valid item set, and
every MACB run must respect the resource invariant |A_t| <= B and
(later activations) <= (deferrals).

Outputs
-------
data/validation_instances.csv
results/validation_results.csv
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from macb import CLASSES, exhaustive, generate_instance, run_method, sort_items  # noqa: E402

BUDGETS = (4, 8, 16, 32, 64)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")


def validation_instances():
    # the small working example (five items) used while developing the solvers
    yield "five_item_example", "example", 5, [2, 3, 4, 5, 6], [3, 4, 5, 8, 9], 10, ""
    k = 0
    for cls in CLASSES:
        for j in range(80):
            n = 5 + (j % 8)                       # n in 5..12
            frac = (0.25, 0.5, 0.75)[j % 3]       # vary capacity tightness
            seed = 31_000_000 + CLASSES.index(cls) * 10_000 + j
            w, v, cap = generate_instance(n, cls, seed, capacity_fraction=frac)
            k += 1
            yield f"val_{k:03d}", cls, n, w, v, cap, seed


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=None, help="write both CSVs here instead of data/ and results/")
    args = ap.parse_args()
    data_dir = args.outdir or os.path.join(ROOT, "data")
    res_dir = args.outdir or os.path.join(ROOT, "results")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(res_dir, exist_ok=True)
    inst_rows, res_rows = [], []
    failures = 0
    n_inst = 0
    for iid, cls, n, w, v, cap, seed in validation_instances():
        n_inst += 1
        inst_rows.append(dict(instance_id=iid, correlation=cls, n=n, seed=seed, capacity=cap,
                              weights=" ".join(map(str, w)), values=" ".join(map(str, v))))
        ref_val, _ = exhaustive(w, v, cap)
        order, ws, vs = sort_items(w, v)
        configs = [("dp", None), ("std_bnb", None), ("cta", None)] + [("macb", b) for b in BUDGETS]
        for method, b in configs:
            r = run_method(method, w, v, cap, order, ws, vs, budget=b, time_limit=None)
            ok = (r["value"] == ref_val) and r["feasible"] and r["value_reported"] == r["value"]
            inv_ok = True
            if method == "macb":
                inv_ok = r["peak_active"] <= b and r["activations"] <= r["deferrals"]
            passed = ok and inv_ok and not r["timed_out"]
            failures += (not passed)
            res_rows.append(dict(
                instance_id=iid, correlation=cls, n=n, method=method, budget=b if b else "",
                reference_value=ref_val, value=r["value"], feasible=r["feasible"],
                peak_active=r.get("peak_active", ""), activations=r.get("activations", ""),
                deferrals=r.get("deferrals", ""), invariant_ok=inv_ok, passed=passed))
    for path, rows in ((os.path.join(data_dir, "validation_instances.csv"), inst_rows),
                       (os.path.join(res_dir, "validation_results.csv"), res_rows)):
        with open(path, "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
    print(f"instances: {n_inst}   checks: {len(res_rows)}   failures: {failures}")
    if failures:
        sys.exit(1)
    print("ALL VALIDATION CHECKS PASSED")


if __name__ == "__main__":
    main()
