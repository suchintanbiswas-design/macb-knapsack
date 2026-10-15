# Demo guide - showing that the code works and the graphs regenerate

Total time: about 5 minutes (fast demo) or about 8 minutes (with the full re-run).

## 1. One-time setup (do this before the presentation)

1. Install Python 3.9 or newer (https://www.python.org/downloads/; tick "Add Python to PATH").
2. Get the code: on the GitHub page click **Code -> Download ZIP**, unzip it, or run
   `git clone https://github.com/suchintanbiswas-design/macb-knapsack.git`
3. Open a terminal **inside the unzipped `macb-knapsack` folder**
   (Windows: open the folder, click the address bar, type `cmd`, press Enter).
4. Install the only dependency: `pip install -r requirements.txt`
   (if `pip` is not found: `python -m pip install -r requirements.txt`; on some Windows machines use `py` instead of `python`).
5. Test once: `python scripts/demo.py` - it should end with **ALL CHECKS PASSED**.

## 2. Running the demo

```
python scripts/demo.py           # fast: about 10 seconds
python scripts/demo.py --full    # full re-run of the experiment: about 2 minutes
```

Everything is written to `results_demo/`; the files in `results/` (the data behind the paper) are never modified.

## 3. What each step shows (suggested talking points)

| Step | What appears on screen | What it proves |
|---|---|---|
| 1. Unit tests | 3 tests `... ok` | the solvers run and agree with brute force |
| 2. Worked example | 4 items, capacity 8; every solver returns value 12 with items 2 and 4; MACB with B = 1 defers nothing | the code reproduces the example in Section II-B.4 / II-C.3 of the paper |
| 3. Validation | `instances: 241  checks: 1928  failures: 0` | DP, standard B&B, CTA and MACB (B = 4, 8, 16, 32, 64) all return the exhaustive-enumeration optimum, and MACB never exceeds its active-node budget |
| 4. Benchmark | instance names scrolling by, then median time per method | the full pipeline (generator -> solvers -> timing/memory measurement -> CSV) works |
| 5. Graphs | `[PASS] graphs regenerated (5 figures)` | Figs. 4-8 and all tables are rebuilt from the CSV; open `results_demo/figures/` and show them |
| 6. (`--full` only) Reproducibility | `identical value / nodes / frontier sizes / items: N of N` | re-running gives exactly the same search behaviour as the saved run |

Open these files at the end:
`results_demo/figures/fig4_time_memory_vs_n.png`, `fig5_open_list_and_explored.png`, `fig6_pruning_and_class_structure.png`, `fig7_budget_sensitivity.png`, `fig8_time_memory_positions.png`
and the readable tables in `results_demo/RESULTS.md`.

## 4. Things to say honestly

* In the **fast** demo the benchmark step uses a small subset (n <= 30) to finish quickly; the 5 graphs are rebuilt from the **saved full run** (`results/benchmark_results.csv`), which is the data reported in the paper.
* In the **full** demo everything is recomputed. Search counters (nodes explored, frontier sizes, selected items) match the saved run exactly; **wall-clock time and memory differ slightly on every computer**, so the new graphs look the same but are not pixel-identical.
* Each configuration is timed once (as stated in the paper), so sub-millisecond readings are noisy.

## 5. Without installing anything: Google Colab

Open https://colab.research.google.com, create a new notebook and run this in one cell:

```python
!git clone https://github.com/suchintanbiswas-design/macb-knapsack.git
%cd macb-knapsack
!pip -q install matplotlib
!python scripts/demo.py
import glob
from IPython.display import Image, display
for f in sorted(glob.glob("results_demo/figures/*.png")):
    print(f); display(Image(f, width=480))
```

Add `--full` after `demo.py` for the complete re-run. The graphs are displayed directly under the cell.

## 6. Troubleshooting

* `ModuleNotFoundError: matplotlib` -> `pip install matplotlib`.
* `python` not recognised on Windows -> use `py scripts/demo.py`.
* Graph window does not open -> nothing is wrong: graphs are saved as PNG files in `results_demo/figures/`; open them from the folder.
* Slow machine in `--full` mode -> some hard instances run until the 3-second deadline by design; the whole run still finishes in about two minutes.
