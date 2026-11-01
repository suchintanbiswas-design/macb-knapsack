#!/usr/bin/env python3
"""Rebuild the two data figures of the journal manuscript from results/benchmark_results.csv.

    python scripts/make_manuscript_figures.py [--results results/benchmark_results.csv] [--out docs/manuscript_figures]

Fig. 3  peak evaluated frontier, peak traced memory and execution time against n
        (CTA and MACB with B = 4; means with sample-SD bars; completed reproduction runs)
Fig. 4  effect of the active-node budget B (medians over completed reproduction runs of MACB)
Figs. 1 and 2 of the manuscript are diagrams (docs/manuscript_figures/fig1_cascade.*, fig2_macb_flow.*).
"""
import argparse
import csv
import os
import statistics as stat

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
NS = (10, 20, 30, 40, 50)
BUDGETS = (4, 8, 16, 32, 64)
GRN, PUR = "#2E8B57", "#7B4FA6"
plt.rcParams.update({"font.family": "DejaVu Sans", "pdf.fonttype": 42, "axes.grid": False})


def load(path):
    rows = []
    for r in csv.DictReader(open(path)):
        if r["suite"] != "reproduction" or r["timed_out"] == "True":
            continue
        r["n"] = int(r["n"])
        r["budget"] = int(r["budget"]) if r["budget"] != "" else None
        for k in ("time_ms", "peak_kb", "peak_active", "peak_logical"):
            r[k] = float(r[k]) if r[k] != "" else 0.0
        rows.append(r)
    return rows


def mean_sd(xs):
    return stat.mean(xs), (stat.stdev(xs) if len(xs) > 1 else 0.0)


def fig3(rows, out):
    panels = [("peak_active", "Peak evaluated frontier (nodes)", (0.3, 6000)),
              ("peak_kb", "Peak traced memory (KB)", (1.5, 6000)),
              ("time_ms", "Execution time (ms)", (0.1, 1500))]
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.6))
    for ax, (field, lab, yl), letter in zip(axs, panels, "abc"):
        for method, b, col, mk, name in (("cta", None, GRN, "s", "CTA"), ("macb", 4, PUR, "o", "MACB ($B$ = 4)")):
            ms, sds = [], []
            for n in NS:
                m, s = mean_sd([r[field] for r in rows if r["method"] == method and r["budget"] == b and r["n"] == n])
                ms.append(m); sds.append(s)
            ms, sds = np.array(ms), np.array(sds)
            lo = np.minimum(sds, ms - yl[0] * 0.999)  # bars that pass below the axis are drawn to its bottom
            ax.errorbar(NS, ms, yerr=[lo, sds], color=col, marker=mk, ms=4, lw=1.4, capsize=2.5, elinewidth=1.0, label=name)
        ax.set_yscale("log"); ax.set_ylim(*yl); ax.set_xticks(NS); ax.set_xlim(7, 53)
        ax.set_xlabel("Number of items $n$", fontsize=7.5); ax.set_ylabel(lab, fontsize=7.5); ax.tick_params(labelsize=7)
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)
        ax.grid(alpha=0.25, lw=0.6)
        ax.text(-0.22, 1.07, letter, transform=ax.transAxes, fontsize=11, fontweight="bold", va="bottom")
    axs[0].legend(frameon=False, fontsize=7, loc="upper left", handlelength=1.6)
    fig.tight_layout(w_pad=1.2)
    fig.savefig(os.path.join(out, "fig3_scaling.pdf")); fig.savefig(os.path.join(out, "fig3_scaling.png"), dpi=300)
    plt.close(fig)


def fig4(rows, out):
    t, mem, act, logi = [], [], [], []
    for b in BUDGETS:
        sel = [r for r in rows if r["method"] == "macb" and r["budget"] == b]
        t.append(stat.median(r["time_ms"] for r in sel)); mem.append(stat.median(r["peak_kb"] for r in sel))
        act.append(stat.median(r["peak_active"] for r in sel)); logi.append(stat.median(r["peak_logical"] for r in sel))
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.55))
    a = axs[0]; a.plot(BUDGETS, t, "o-", color=PUR, lw=1.4, ms=4)
    a.set_xlabel("Active-node budget $B$"); a.set_ylabel("Median execution time (ms)")
    b = axs[1]
    b.plot(BUDGETS, act, "o-", color=PUR, lw=1.4, ms=4, label="Evaluated (active)")
    b.plot(BUDGETS, logi, "s-", color=GRN, lw=1.4, ms=4, label="Logical (active + deferred)")
    b.set_xlabel("Active-node budget $B$"); b.set_ylabel("Median peak frontier (nodes)")
    b.legend(frameon=False, fontsize=6.5, loc="lower right", handlelength=1.6)
    c = axs[2]
    for bi, ti, mi in zip(BUDGETS, t, mem):
        c.plot(mi, ti, "o", color=PUR, ms=5)
        c.annotate(f"$B$ = {bi}", (mi, ti), xytext=(6, 0), textcoords="offset points", ha="left", va="center", fontsize=6.5)
    c.set_xlabel("Median peak traced memory (KB)"); c.set_ylabel("Median execution time (ms)")
    pad = 0.4 * (max(mem) - min(mem) or 1.0)
    c.set_xlim(min(mem) - pad, max(mem) + 3 * pad)
    for ax_, letter in zip(axs, "abc"):
        if ax_ is not c:
            ax_.set_xscale("log", base=2); ax_.set_xticks(BUDGETS); ax_.set_xticklabels(BUDGETS)
        ax_.text(-0.2, 1.07, letter, transform=ax_.transAxes, fontsize=11, fontweight="bold", va="bottom")
        ax_.tick_params(labelsize=7); ax_.xaxis.label.set_size(7.5); ax_.yaxis.label.set_size(7.5)
        for s_ in ("top", "right"):
            ax_.spines[s_].set_visible(False)
        ax_.grid(alpha=0.25, lw=0.6)
    fig.tight_layout(w_pad=1.4)
    fig.savefig(os.path.join(out, "fig4_budget.pdf")); fig.savefig(os.path.join(out, "fig4_budget.png"), dpi=300)
    plt.close(fig)
    print("budget medians (B, time ms, memory KB, active, logical):")
    for row in zip(BUDGETS, t, mem, act, logi):
        print("  ", row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(ROOT, "results", "benchmark_results.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "manuscript_figures"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rows = load(args.results)
    fig3(rows, args.out)
    fig4(rows, args.out)
    print("written to", args.out)


if __name__ == "__main__":
    main()
