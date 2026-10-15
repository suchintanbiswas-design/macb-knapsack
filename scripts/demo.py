#!/usr/bin/env python3
"""Live demonstration: shows that the code works and that the graphs regenerate.

    python scripts/demo.py           # fast demo   (~1 min)
    python scripts/demo.py --full    # full re-run (~2 min): repeats the whole experiment

Everything is written to ``results_demo/`` so the files in ``results/`` are never touched.

Steps
  1. unit tests
  2. the paper's 4-item worked example (Section II-B.4 / II-C.3)
  3. exhaustive-enumeration validation: 241 instances x 8 solver configurations
  4. benchmark  (fast: small subset; --full: all 87 instances, 696 rows)
  5. tables and graphs rebuilt from the benchmark CSV
  6. (--full) deterministic counters compared with the saved run in results/
"""
import argparse
import csv
import os
import shutil
import statistics as stat
import subprocess
import sys
import time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ROOT = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "results_demo")
PY = sys.executable
T0 = time.time()
RESULTS = []


def banner(title):
    print("\n" + "=" * 74 + f"\n  {title}\n" + "=" * 74, flush=True)


def run(args):
    return subprocess.run([PY] + args, cwd=ROOT).returncode == 0


def verdict(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"\n  [{'PASS' if ok else 'FAIL'}] {name}  {detail}", flush=True)


def step_tests():
    banner("STEP 1 - unit tests")
    verdict("unit tests", run(["-m", "unittest", "discover", "-s", "tests", "-v"]))


def step_worked_example():
    banner("STEP 2 - worked example from the paper (4 items, capacity 8)")
    from macb import exhaustive, run_method, sort_items
    w, v, cap = [2, 3, 4, 5], [3, 4, 5, 8], 8
    order, ws, vs = sort_items(w, v)
    print("  items (weight, value):", list(zip(w, v)), " capacity:", cap)
    print("  ratio order (1-based item numbers):", [i + 1 for i in order])
    ref, ref_items = exhaustive(w, v, cap)
    print(f"  exhaustive optimum: value {ref}, items {[i + 1 for i in ref_items]}")
    ok = True
    for m, b in (("dp", None), ("std_bnb", None), ("cta", None), ("macb", 1), ("macb", 4)):
        r = run_method(m, w, v, cap, order, ws, vs, budget=b)
        items = [int(x) + 1 for x in r["items"].split()]
        extra = f"  deferrals={r['deferrals']}  peak_active={r['peak_active']}" if m == "macb" else ""
        print(f"  {m:8s} B={str(b or '-'):2s} -> value {r['value']}, items {items}{extra}")
        ok &= r["value"] == ref
    verdict("worked example (z* = 12, items 2 and 4; nothing deferred with B = 1)", ok)


def step_validation():
    banner("STEP 3 - exhaustive-enumeration validation (241 instances)")
    ok = run(["scripts/run_validation.py", "--outdir", OUT])
    verdict("validation: DP, B&B, CTA and MACB (B = 4..64) all equal the exhaustive optimum", ok)


def step_benchmark(full):
    banner("STEP 4 - benchmark " + ("(FULL: 87 instances, 696 runs, 3 s deadline)" if full else "(fast subset)"))
    out = os.path.join(OUT, "benchmark_results.csv" if full else "quick_results.csv")
    inst = os.path.join(OUT, "instances.csv" if full else "quick_instances.csv")
    args = ["scripts/run_benchmark.py", "--out", out, "--instances-out", inst]
    if not full:
        args.append("--quick")
    ok = run(args)
    verdict("benchmark finished and every completed run equals the DP optimum", ok)
    rows = list(csv.DictReader(open(out)))
    print("\n  median time per method over completed runs:")
    for m, b, name in (("dp", "", "DP"), ("std_bnb", "", "Standard B&B"), ("cta", "", "CTA"), ("macb", "4", "MACB (B=4)")):
        t = [float(r["time_ms"]) for r in rows if r["method"] == m and r["budget"] == b and r["timed_out"] == "False"]
        if t:
            print(f"    {name:14s} {stat.median(t):9.3f} ms   ({len(t)} runs)")
    return out


def step_graphs(full, bench_csv):
    banner("STEP 5 - tables and graphs rebuilt from the benchmark CSV")
    if not full:  # the fast subset is too small for the paper's tables -> use the saved full run
        shutil.copy(os.path.join(ROOT, "results", "benchmark_results.csv"), os.path.join(OUT, "benchmark_results.csv"))
        print("  (fast mode: graphs are rebuilt from the saved full run in results/benchmark_results.csv)")
    ok = run(["scripts/analyze.py", "--results-dir", OUT])
    figs = sorted(os.listdir(os.path.join(OUT, "figures"))) if ok else []
    verdict("graphs regenerated", ok and len(figs) == 5, f"({len(figs)} figures)")
    for f in figs:
        print("    ", os.path.join("results_demo", "figures", f))
    print("\n  tables:", os.path.join("results_demo", "tables"), " |  readable summary: results_demo/RESULTS.md")


def step_compare():
    banner("STEP 6 - reproducibility: deterministic counters vs. the saved run")
    new = {(r["instance_id"], r["method"], r["budget"]): r for r in csv.DictReader(open(os.path.join(OUT, "benchmark_results.csv")))}
    old = {(r["instance_id"], r["method"], r["budget"]): r for r in csv.DictReader(open(os.path.join(ROOT, "results", "benchmark_results.csv")))}
    both = same = 0
    for k, r in new.items():
        o = old.get(k)
        if o and r["timed_out"] == "False" and o["timed_out"] == "False":
            both += 1
            same += all(r[c] == o[c] for c in ("value", "explored", "generated", "pruned", "peak_active", "peak_logical", "items"))
    print(f"  runs completed in both: {both};  identical value / nodes / frontier sizes / items: {same}")
    print("  (wall-clock time and memory differ slightly on every machine; the search itself is deterministic)")
    verdict("search behaviour reproduces exactly", both > 0 and same == both, f"({same}/{both})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="re-run the complete experiment (about 2 minutes)")
    args = ap.parse_args()
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    step_tests()
    step_worked_example()
    step_validation()
    bench = step_benchmark(args.full)
    step_graphs(args.full, bench)
    if args.full:
        step_compare()
    banner(f"SUMMARY  ({time.time() - T0:.0f} s)")
    for name, ok, detail in RESULTS:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")
    bad = [n for n, ok, _ in RESULTS if not ok]
    print("\n  ALL CHECKS PASSED" if not bad else f"\n  {len(bad)} CHECK(S) FAILED")
    print("  Open the folder  results_demo/figures  to show the graphs.")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
