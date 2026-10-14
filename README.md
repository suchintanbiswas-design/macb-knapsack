# Memory-Aware Cascading Branch and Bound (MACB) for the 0/1 Knapsack Problem

Source code, datasets and graphs for the paper

> **Memory-Aware Cascading Branch and Bound: A Resource-Bounded Extension of the Cascading-Tree Algorithm for the 0/1 Knapsack Problem**
> Suchintan Biswas, Shinjan Roy, Subhodeep Mandal and Suhasini S, School of Computer Science and Engineering / School of Electronics Engineering, Vellore Institute of Technology, Chennai, India.

MACB is an *exact*, resource-bounded variant of the Cascading-Tree Algorithm (CTA, Moeini, Schermer & Wendt, 2024).
Instead of keeping every open node fully evaluated, MACB keeps at most **B** fully evaluated nodes in an *active heap* and stores the
remaining children as lightweight *deferred descriptors* that carry their parent's (admissible) upper bound.
No feasible branch is ever discarded, so the optimum is still guaranteed.

Four exact solvers are implemented and compared:

| Method | Module | Paper |
|---|---|---|
| Dynamic programming (2-D table, item reconstruction) | `macb/core.py` | Algorithm 1 |
| Standard best-bound branch and bound (binary branching) | `macb/solvers.py::standard_bnb` | Algorithm 2 |
| Cascading-Tree Algorithm (CTA) | `macb/solvers.py::cta` | Algorithm 3 |
| Memory-Aware Cascading B&B (MACB) | `macb/solvers.py::macb` | Algorithm 4 |

## Repository layout

```
macb/                 solver package (core.py, solvers.py, runner.py)
scripts/
  run_validation.py   241-instance exhaustive-enumeration validation
  run_benchmark.py    full benchmark (75 reproduction + 12 extended instances, 696 rows)
  analyze.py          builds all tables and figures from the benchmark CSV
  environment_info.py records Python / OS / CPU used for the run
  run_all.sh          runs everything in order
tests/                unit tests (python -m unittest discover -s tests)
data/
  instances.csv               all 87 benchmark instances (weights, values, capacity, seed)
  validation_instances.csv    the 241 validation instances
results/
  benchmark_results.csv       raw row-level log, one row per (instance, method, budget)
  validation_results.csv      validation log (1,928 checks)
  environment.json            machine used for the included run
  RESULTS.md                  all tables in readable form
  tables/                     tables as CSV (+ headline_metrics.json)
  figures/                    fig4 ... fig8 (time/memory, open list, pruning, budget sensitivity, time-memory)
docs/diagrams/                branching-structure, MACB control-flow and workflow diagrams
```

## Quick start

Requires Python 3.9+ (tested with 3.12). Only `matplotlib` is needed (for the figures).

```bash
git clone <this-repository-url>
cd macb-knapsack
pip install -r requirements.txt

python -m unittest discover -s tests -v     # fast correctness tests
bash scripts/run_all.sh                     # validation + benchmark + tables + figures (~5 min)
```

or step by step:

```bash
python scripts/run_validation.py            # -> data/validation_*.csv, results/validation_results.csv
python scripts/run_benchmark.py             # -> data/instances.csv, results/benchmark_results.csv
python scripts/analyze.py                   # -> results/tables/*, results/figures/*, results/RESULTS.md
```

`python scripts/run_benchmark.py --quick` runs a small smoke-test subset (seconds).

### Using the solvers directly

```python
from macb import generate_instance, sort_items, run_method

w, v, cap = generate_instance(n=30, correlation="strong", seed=1)
order, ws, vs = sort_items(w, v)                       # ratio order, ties by original index
res = run_method("macb", w, v, cap, order, ws, vs, budget=4, time_limit=3.0)
print(res["value"], res["items"], res["peak_active"], res["peak_deferred"], res["time_ms"], res["peak_kb"])
```

## Experimental protocol (matches Section II-E of the paper)

* **Generator** (`macb/core.py`): weights `U[1,100]`; values `U[1,100]` (*uncorrelated*), `U[max(1,w-10), w+10]` (*weak*), `w+10` (*strong*); capacity `floor(0.5 * sum(w))`.
* **Seeds:** `20260914 + 1_000_000*class_index + 1_000*n + replicate` (class index: uncorrelated 0, weak 1, strong 2).
* **Reproduction suite:** 3 classes x n in {10,20,30,40,50} x 5 seeds = 75 instances. **Extended suite:** 3 classes x n in {100,200} x 2 seeds = 12 instances.
* **Methods:** DP, standard B&B, CTA, MACB with B in {4, 8, 16, 32, 64} = 8 configurations per instance = 696 rows.
* **Deadline:** 3 s, checked inside every tree-search loop (DP is exempt). A timeout is stored as `timed_out = True` and is *never* treated as an optimal answer.
* **Timing/memory:** each configuration is run **once**; `gc.collect()`, then `tracemalloc` is started, the solver runs, and `tracemalloc` is stopped. `peak_kb` is the tracemalloc peak (Python allocation pressure, *not* resident-set size).
* **Correctness:** objective value and feasibility are recomputed from the returned item set; every completed run is compared with the DP optimum (`correct_vs_dp`).
* **Validation:** `run_validation.py` checks DP, B&B, CTA and MACB (all budgets) against exhaustive enumeration on 241 instances (one 5-item example + 240 random instances with 5 <= n <= 12, 80 per class, capacity fraction in {0.25, 0.5, 0.75}), including the resource invariant `|A_t| <= B` and `activations <= deferrals`.

## Implementation notes

* Items are sorted by non-increasing `v/w`, ties broken by original index; all tree searches use FIFO tie-breaking in their heaps, so runs are deterministic.
* Node bounds are integer: `UB = floor(Dantzig bound)` (all values are integers), so a node is pruned when `UB <= incumbent`.
* The integer heuristic keeps all whole items of the relaxation, fixes the break item to 0 and then adds every later free item that still fits. The resulting set is *maximal*, which makes the cascade partition (Property 1 of the paper) exact.
* `generated` = number of node relaxations actually solved; `children` = cascade children created (including deferred ones); `explored` = nodes expanded; `pruned` = nodes discarded by the bound test; pruning rate = `pruned / (pruned + explored)`.
* `peak_active` = largest evaluated open list; `peak_deferred` = largest deferred heap; `peak_logical` = largest `|A| + |D|`.

## Data dictionary (`results/benchmark_results.csv`)

| Column | Meaning |
|---|---|
| `instance_id`, `suite`, `correlation`, `n`, `replicate`, `seed`, `capacity` | instance identity (regenerate from `seed`, or read `data/instances.csv`) |
| `method`, `budget` | `dp` / `std_bnb` / `cta` / `macb`; budget B only for MACB |
| `value`, `weight`, `feasible`, `correct_vs_dp` | objective recomputed from returned items; feasibility; agreement with DP (empty on timeouts) |
| `timed_out` | True if the 3 s deadline was hit (result is censored, not optimal) |
| `time_ms`, `peak_kb` | wall-clock time and tracemalloc peak |
| `generated`, `explored`, `pruned`, `infeasible` | search counters |
| `peak_active`, `peak_deferred`, `peak_logical` | frontier sizes |
| `cascades`, `children`, `max_fanout` | cascade statistics (children per expansion) |
| `immediate`, `deferrals`, `activations` | MACB: children evaluated at once / deferred / later activated |
| `items` | selected items (zero-based original indices) |

## Reproducibility notes

* Instance generation, search order and all counters (`explored`, `peak_active`, `peak_logical`, ...) are deterministic for completed runs.
* **Wall-clock time and tracemalloc peaks depend on the machine and Python version**, and sub-millisecond readings are noisy (each configuration is timed once). Re-running will give slightly different times; `results/environment.json` records the machine used for the included run.
* The included `results/` files were produced by `scripts/run_all.sh` on the machine described in `results/environment.json`.

## Citation

If you use this code, please cite the paper above and the original CTA paper:
M. Moeini, D. Schermer, O. Wendt, "Cascading-Tree Algorithm for the 0-1 Knapsack Problem," arXiv:2405.13450, 2024.

## License

MIT - see `LICENSE`.
