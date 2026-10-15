#!/usr/bin/env python3
"""Build every table and figure from ``results/benchmark_results.csv``.

Tables  -> results/tables/*.csv and results/RESULTS.md
Figures -> results/figures/fig4..fig8 (same panels as Figs. 4-8 of the paper)

Medians, full ranges and *paired* ratios (computed only over instances that
both methods completed) are used throughout, exactly as in Section II-E.5.
"""
import csv
import json
import math
import os
import statistics as stat
import sys
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RES = os.path.join(ROOT, "results")
TAB = os.path.join(RES, "tables")
FIG = os.path.join(RES, "figures")
BUDGETS = (4, 8, 16, 32, 64)
NS = (10, 20, 30, 40, 50)
CLASS_LABEL = {"uncorrelated": "Uncorrelated", "weak": "Weakly corr.", "strong": "Strongly corr."}
COL = {"dp": "#1f77b4", "std_bnb": "#ff7f0e", "cta": "#2ca02c", "macb": "#9467bd"}
LAB = {"dp": "DP", "std_bnb": "Standard B&B", "cta": "CTA", "macb": "Memory-Aware CTA (B=4)"}

plt.rcParams.update({"font.size": 7, "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 100,
                     "axes.spines.top": False, "axes.spines.right": False})


# --------------------------------------------------------------------------- #
def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            r["n"] = int(r["n"])
            r["replicate"] = int(r["replicate"])
            r["capacity"] = int(r["capacity"])
            r["budget"] = int(r["budget"]) if r["budget"] != "" else None
            r["timed_out"] = r["timed_out"] == "True"
            for k in ("time_ms", "peak_kb"):
                r[k] = float(r[k])
            for k in ("generated", "explored", "pruned", "peak_active", "peak_deferred", "peak_logical",
                      "cascades", "children", "max_fanout", "immediate", "deferrals", "activations"):
                r[k] = int(float(r[k])) if r[k] != "" else 0
            rows.append(r)
    return rows


def key(r):
    return (r["method"], r["budget"])


def sel(rows, method, budget=None, suite=None, done=True):
    out = [r for r in rows if r["method"] == method and (budget is None or r["budget"] == budget)
           and (suite is None or r["suite"] == suite) and (not done or not r["timed_out"])]
    return out


def write_csv(name, header, body):
    with open(os.path.join(TAB, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(body)


def md_table(title, header, body):
    s = [f"### {title}", "", "| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for b in body:
        s.append("| " + " | ".join(str(x) for x in b) + " |")
    return "\n".join(s) + "\n"


def fmt(x, d=3):
    return f"{x:.{d}f}"


def mean_sd(xs):
    if not xs:
        return float("nan"), 0.0
    return stat.mean(xs), (stat.stdev(xs) if len(xs) > 1 else 0.0)


# --------------------------------------------------------------------------- #
def tables(rows):
    md = []
    repro = [r for r in rows if r["suite"] == "reproduction"]
    n_rep = len({r["instance_id"] for r in repro})
    n_ext = len({r["instance_id"] for r in rows if r["suite"] == "extended"})

    # ---- Table II: completion counts -------------------------------------- #
    body = []
    for suite, tot in (("reproduction", n_rep), ("extended", n_ext)):
        for m, b in [("dp", None), ("std_bnb", None), ("cta", None)] + [("macb", x) for x in BUDGETS]:
            rr = [r for r in rows if r["suite"] == suite and r["method"] == m and r["budget"] == b]
            if not rr:
                continue
            done = sum(not r["timed_out"] for r in rr)
            name = {"dp": "DP", "std_bnb": "Std. B&B", "cta": "CTA"}.get(m, f"MACB B={b}")
            body.append([suite, name, f"{done}/{tot}", tot - done])
    write_csv("table2_completion.csv", ["suite", "method", "completed", "timeouts"], body)
    md.append(md_table("Table II - completion counts by suite and method", ["Suite", "Method", "Completed", "Timeouts"], body))

    # ---- Table III: execution-time distribution -------------------------- #
    body = []
    for m, b, name in (("dp", None, "DP"), ("std_bnb", None, "Std. B&B"), ("cta", None, "CTA"), ("macb", 4, "MACB B=4")):
        t = [r["time_ms"] for r in sel(repro, m, b)]
        if t:
            body.append([name, len(t), fmt(stat.mean(t)), fmt(stat.median(t)),
                         fmt(stat.stdev(t) if len(t) > 1 else 0), f"{min(t):.3f} / {max(t):.3f}"])
    write_csv("table3_time_distribution.csv", ["method", "N", "mean_ms", "median_ms", "sd_ms", "min_max_ms"], body)
    md.append(md_table("Table III - execution-time distribution, completed reproduction runs",
                       ["Method", "N", "Mean (ms)", "Median (ms)", "SD (ms)", "Min/Max (ms)"], body))

    # ---- Table IV: memory and evaluated frontier -------------------------- #
    body = []
    for m, b, name in [("std_bnb", None, "Std. B&B"), ("cta", None, "CTA")] + [("macb", x, f"MACB B={x}") for x in BUDGETS]:
        rr = sel(repro, m, b)
        if rr:
            body.append([name, fmt(stat.median(r["peak_kb"] for r in rr), 1), fmt(max(r["peak_kb"] for r in rr), 1),
                         fmt(stat.median(r["peak_active"] for r in rr), 1), max(r["peak_active"] for r in rr)])
    write_csv("table4_memory_frontier.csv", ["method", "median_kb", "max_kb", "median_active", "max_active"], body)
    md.append(md_table("Table IV - memory and evaluated-frontier statistics, completed reproduction runs",
                       ["Method", "Median (KB)", "Max (KB)", "Med. active", "Max active"], body))

    # ---- Table V: paired ratios by class ---------------------------------- #
    cta_by = {r["instance_id"]: r for r in sel(repro, "cta")}
    mac_by = {r["instance_id"]: r for r in sel(repro, "macb", 4)}
    body, pair_all = [], []
    for cls in ("uncorrelated", "weak", "strong"):
        ids = [i for i in cta_by if i in mac_by and cta_by[i]["correlation"] == cls]
        if not ids:
            continue
        tr = [mac_by[i]["time_ms"] / cta_by[i]["time_ms"] for i in ids]
        mr = [mac_by[i]["peak_kb"] / cta_by[i]["peak_kb"] for i in ids]
        pair_all += ids
        body.append([CLASS_LABEL[cls], len(ids), fmt(stat.median(tr)), fmt(stat.median(mr)),
                     fmt(stat.median(cta_by[i]["peak_active"] for i in ids), 1),
                     fmt(stat.median(mac_by[i]["peak_active"] for i in ids), 1)])
    write_csv("table5_paired_ratios_by_class.csv",
              ["class", "pairs", "time_ratio", "mem_ratio", "cta_med_active", "b4_med_active"], body)
    md.append(md_table("Table V - paired median MACB(B=4)/CTA ratios by correlation class",
                       ["Class", "Pairs", "Time ratio", "Mem. ratio", "CTA med. active", "B=4 med. active"], body))

    # ---- Table VI: budget sensitivity ------------------------------------- #
    body = []
    for b in BUDGETS:
        rr = sel(repro, "macb", b)
        body.append([b, fmt(stat.median(r["time_ms"] for r in rr)), fmt(stat.median(r["peak_kb"] for r in rr), 1),
                     fmt(stat.median(r["peak_active"] for r in rr), 1), fmt(stat.median(r["peak_logical"] for r in rr), 1)])
    write_csv("table6_budget_sensitivity.csv", ["B", "median_time_ms", "median_mem_kb", "median_active", "median_logical"], body)
    md.append(md_table("Table VI - aggregate budget sensitivity, completed reproduction runs",
                       ["B", "Median time (ms)", "Median mem. (KB)", "Med. active", "Med. logical"], body))

    # ---- extended suite --------------------------------------------------- #
    body = []
    for iid in sorted({r["instance_id"] for r in rows if r["suite"] == "extended"}):
        line = [iid]
        for m, b in [("dp", None), ("std_bnb", None), ("cta", None), ("macb", 4)]:
            r = [x for x in rows if x["instance_id"] == iid and x["method"] == m and x["budget"] == b][0]
            line.append("timeout" if r["timed_out"] else f"{r['time_ms']:.1f} ms")
        body.append(line)
    write_csv("table7_extended_suite.csv", ["instance", "DP", "Std. B&B", "CTA", "MACB B=4"], body)
    md.append(md_table("Extended suite (n = 100, 200) - wall-clock time or timeout",
                       ["Instance", "DP", "Std. B&B", "CTA", "MACB B=4"], body))

    # ---- headline numbers -------------------------------------------------- #
    cta_t = [cta_by[i]["time_ms"] for i in pair_all]
    ov = [mac_by[i]["time_ms"] / cta_by[i]["time_ms"] for i in pair_all]
    mr_all = [mac_by[i]["peak_kb"] / cta_by[i]["peak_kb"] for i in pair_all]
    strong = [i for i in pair_all if cta_by[i]["correlation"] == "strong"]
    mr_strong = [mac_by[i]["peak_kb"] / cta_by[i]["peak_kb"] for i in strong]
    fr = [mac_by[i]["peak_active"] / cta_by[i]["peak_active"] for i in pair_all if cta_by[i]["peak_active"] > 0]
    head = {
        "paired_instances": len(pair_all),
        "cta_median_time_ms": stat.median(cta_t) if cta_t else None,
        "macb4_median_time_ms": stat.median(mac_by[i]["time_ms"] for i in pair_all) if pair_all else None,
        "median_time_overhead_pct": (stat.median(ov) - 1) * 100 if ov else None,
        "median_mem_ratio_all": stat.median(mr_all) if mr_all else None,
        "median_mem_ratio_strong": stat.median(mr_strong) if mr_strong else None,
        "median_frontier_ratio": stat.median(fr) if fr else None,
        "cta_max_active": max((r["peak_active"] for r in sel(repro, "cta")), default=None),
        "cta_max_kb": max((r["peak_kb"] for r in sel(repro, "cta")), default=None),
        "macb4_max_kb": max((r["peak_kb"] for r in sel(repro, "macb", 4)), default=None),
        "macb4_max_active": max((r["peak_active"] for r in sel(repro, "macb", 4)), default=None),
        "cta_median_explored": stat.median(r["explored"] for r in sel(repro, "cta")),
        "macb4_median_explored": stat.median(r["explored"] for r in sel(repro, "macb", 4)),
        "std_bnb_median_explored": stat.median(r["explored"] for r in sel(repro, "std_bnb")),
        "total_rows": len(rows),
        "completed_rows": sum(not r["timed_out"] for r in rows),
        "timeout_rows": sum(r["timed_out"] for r in rows),
        "wrong_vs_dp": sum(1 for r in rows if r["correct_vs_dp"] == "False"),
    }
    with open(os.path.join(TAB, "headline_metrics.json"), "w") as f:
        json.dump(head, f, indent=2)
    md.append("### Headline metrics\n\n```json\n" + json.dumps(head, indent=2) + "\n```\n")
    with open(os.path.join(RES, "RESULTS.md"), "w") as f:
        f.write("# Benchmark results (auto-generated by scripts/analyze.py)\n\n" + "\n".join(md))
    return head


# --------------------------------------------------------------------------- #
def curve(ax, rows, method, budget, field, color, label, marker="o", ls="-", ns=NS, transform=None):
    xs, ms, sds = [], [], []
    for n in ns:
        vals = [(transform(r) if transform else r[field]) for r in rows
                if r["method"] == method and r["budget"] == budget and r["n"] == n and not r["timed_out"]]
        if vals:
            m, s = mean_sd(vals)
            xs.append(n); ms.append(m); sds.append(s)
    ax.errorbar(xs, ms, yerr=sds, color=color, marker=marker, ms=3, lw=1.4, capsize=2, label=label, ls=ls)


def figures(rows):
    repro = [r for r in rows if r["suite"] == "reproduction"]
    legend_items = [("dp", None, "DP"), ("std_bnb", None, "Standard B&B"), ("cta", None, "CTA"), ("macb", 4, "Memory-Aware CTA (B=4)")]

    # ---- Fig 4: time and memory vs n -------------------------------------- #
    fig, axs = plt.subplots(2, 1, figsize=(3.5, 5.3))
    for m, b, lab in legend_items:
        curve(axs[0], repro, m, b, "time_ms", COL[m], lab, transform=lambda r: r["time_ms"] / 1000)
        curve(axs[1], repro, m, b, "peak_kb", COL[m], lab, transform=lambda r: r["peak_kb"] * 1024)
    axs[0].set_yscale("log"); axs[1].set_yscale("log")
    axs[0].set_ylabel("Execution time (s)"); axs[1].set_ylabel("Peak traced memory (bytes)")
    axs[0].set_title("(a) execution time vs items", loc="left", fontsize=7)
    axs[1].set_title("(b) peak memory vs items", loc="left", fontsize=7)
    for a in axs:
        a.set_xlabel("Number of items n"); a.set_xticks(NS)
    axs[0].legend(ncol=2, fontsize=7, frameon=True)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig4_time_memory_vs_n.png"), dpi=300); plt.close(fig)

    # ---- Fig 5: open-list size and explored nodes -------------------------- #
    fig, axs = plt.subplots(2, 1, figsize=(3.5, 5.3))
    for m, b, lab in legend_items:
        if m != "dp":
            curve(axs[0], repro, m, b, "peak_active", COL[m], lab)
        if m == "dp":
            xs, ms = [], []
            for n in NS:
                v = [r["n"] * (r["capacity"] + 1) for r in repro if r["method"] == "dp" and r["n"] == n]
                xs.append(n); ms.append(stat.mean(v))
            axs[1].plot(xs, ms, color=COL[m], marker="o", ms=3, label=lab)
        else:
            curve(axs[1], repro, m, b, "explored", COL[m], lab)
    axs[0].set_yscale("log"); axs[1].set_yscale("log")
    axs[0].set_ylabel("Peak evaluated open-list nodes"); axs[1].set_ylabel("Nodes or DP states explored")
    axs[0].set_title("(a) peak open list (active) vs items", loc="left", fontsize=7)
    axs[1].set_title("(b) nodes explored vs items (DP states for scale only)", loc="left", fontsize=7)
    for a in axs:
        a.set_xlabel("Number of items n"); a.set_xticks(NS)
    axs[0].legend(fontsize=6)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig5_open_list_and_explored.png"), dpi=300); plt.close(fig)

    # ---- Fig 6: pruning rate and time by correlation class ---------------- #
    fig = plt.figure(figsize=(3.5, 5.0))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.15, 1, 1])
    ax = fig.add_subplot(gs[0, :])

    def prune_rate(r):
        t = r["pruned"] + r["explored"]
        return r["pruned"] / t if t else 0.0
    for m, b, lab in legend_items:
        if m == "dp":
            ax.plot(NS, [0] * len(NS), color=COL[m], marker="o", ms=3, label=lab)
        else:
            curve(ax, repro, m, b, None, COL[m], lab, transform=prune_rate)
    ax.set_ylabel("Pruning rate"); ax.set_xlabel("Number of items n"); ax.set_xticks(NS)
    ax.set_title("(a) pruning rate vs items", loc="left", fontsize=7); ax.set_ylim(-0.05, 1.1); ax.legend(fontsize=5.5, ncol=2, loc="upper center")
    handles = None
    for j, cls in enumerate(("strong", "uncorrelated", "weak")):
        a = fig.add_subplot(gs[1 + j // 2, j % 2])
        sub = [r for r in repro if r["correlation"] == cls]
        for m, b, lab in legend_items:
            xs, ys = [], []
            for n in NS:
                v = [r["time_ms"] / 1000 for r in sub if r["method"] == m and r["budget"] == b and r["n"] == n and not r["timed_out"]]
                if v:
                    xs.append(n); ys.append(stat.median(v))
            a.plot(xs, ys, color=COL[m], marker="o", ms=2.5, label=lab)
        a.set_yscale("log")
        a.set_title(("(b) " if j == 0 else "") + CLASS_LABEL[cls].replace("corr.", "correlated"), fontsize=7, loc="left")
        a.set_xlabel("n"); a.set_xticks(NS); a.tick_params(labelsize=6)
        if j % 2 == 0:
            a.set_ylabel("Median time (s)")
        handles = a.get_legend_handles_labels()
    la = fig.add_subplot(gs[2, 1]); la.axis("off")
    la.legend(*handles, fontsize=6, loc="center", frameon=False)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig6_pruning_and_class_structure.png"), dpi=300); plt.close(fig)

    # ---- Fig 7: budget sensitivity ---------------------------------------- #
    med_t = [stat.median(r["time_ms"] / 1000 for r in sel(repro, "macb", b)) for b in BUDGETS]
    med_a = [stat.median(r["peak_active"] for r in sel(repro, "macb", b)) for b in BUDGETS]
    med_l = [stat.median(r["peak_logical"] for r in sel(repro, "macb", b)) for b in BUDGETS]
    fig, axs = plt.subplots(2, 1, figsize=(3.5, 5.3))
    axs[0].plot(BUDGETS, med_t, color=COL["macb"], marker="o"); axs[0].set_ylabel("Median execution time (s)")
    axs[0].set_title("(a) budget vs time", loc="left", fontsize=7)
    axs[1].plot(BUDGETS, med_a, color=COL["macb"], marker="o", label="Evaluated frontier")
    axs[1].plot(BUDGETS, med_l, color="#3b8a2e", marker="s", label="Logical frontier")
    axs[1].set_ylabel("Median peak nodes"); axs[1].legend()
    axs[1].set_title("(b) budget vs peak frontier", loc="left", fontsize=7)
    for a in axs:
        a.set_xlabel("Active-node budget B")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig7_budget_sensitivity.png"), dpi=300); plt.close(fig)

    # ---- Fig 8: time-memory positions -------------------------------------- #
    mem = [stat.median(r["peak_kb"] * 1024 for r in sel(repro, "macb", b)) for b in BUDGETS]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    sc = ax.scatter(mem, med_t, c=range(len(BUDGETS)), cmap="viridis", s=45)
    for b, x, y in zip(BUDGETS, mem, med_t):
        ax.annotate(f"B={b}", (x, y), textcoords="offset points", xytext=(5, 4), fontsize=7)
    ax.set_xlabel("Median peak traced memory (bytes)"); ax.set_ylabel("Median execution time (s)")
    ax.set_title("time-memory positions of completed-run medians", loc="left", fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig8_time_memory_positions.png"), dpi=300); plt.close(fig)


def main():
    global RES, TAB, FIG
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default=RES, help="folder holding benchmark_results.csv (default: results/)")
    args = ap.parse_args()
    RES = os.path.abspath(args.results_dir)
    TAB = os.path.join(RES, "tables")
    FIG = os.path.join(RES, "figures")
    path = os.path.join(RES, "benchmark_results.csv")
    if not os.path.exists(path):
        sys.exit("run scripts/run_benchmark.py first")
    os.makedirs(TAB, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    rows = load(path)
    head = tables(rows)
    figures(rows)
    print(json.dumps(head, indent=2))


if __name__ == "__main__":
    main()
