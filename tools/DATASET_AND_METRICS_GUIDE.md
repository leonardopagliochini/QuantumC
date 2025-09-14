# Dataset And Metrics Guide

## 1) Concepts And What’s Measurable (theory)

- **Goal:** Build a controllable corpus of C programs that spans a 2D grid: cyclomatic complexity (CC) × instruction count (Ir), where both axes are under our control and the Ir reflects real, integer-only operations that the toolchain lowers to quantum IR as well.

- **Cyclomatic Complexity (CC):**
  - **Definition:** Standard cyclomatic complexity (sum of function CCN), as reported by Lizard. Fallback heuristic (keywords `if/for/while/case`, etc.) is used only if Lizard fails.
  - **How we control it:** We synthesize a single `main` function with a chosen number of top-level `if` statements (no nesting), optionally a single `for` loop. With one function, CC obeys:
    - `CC ≈ 1 + (#if) + (1 if for-loop present else 0)`
  - **Why it’s stable:** These top-level decisions do not depend on the region-of-interest (ROI) and remain constant for a generated CC row.

- **Instruction Count (Ir):**
  - **Definition:** Dynamic machine-instruction count (Callgrind’s event `Ir`). This is per-instruction fetch at runtime, not a source-level statement count.
  - **How we measure it:** Valgrind/Callgrind with ROI toggling:
    - We compile with `-O0 -g` and run under Callgrind.
    - We use `--collect-atstart=no --toggle-collect=roi_block` so only the ROI function’s execution is measured.
    - The scanner extracts `Ir` via `callgrind_annotate` or by parsing `callgrind.out` directly.
  - **What it reflects:** Dynamic count only for `roi_block()` body. It excludes process startup, function prologue/epilogue outside the ROI, and any non-ROI code.

- **Region of Interest (ROI) design:**
  - We emit a dedicated function `void __attribute__((noinline)) roi_block(void)` that contains only integer arithmetic statements (no I/O, no pointers, no bitwise, no asm). Examples of unit statements:
    - `ga = ga + k;`
    - `gs = gs + ga;`
    - `gb = gb + 1;`
    - `gs = gs + gb;`
  - These operations are chosen because the toolchain lowers them to classical MLIR and to the custom quantum IR (and eventually gates) with predictable behavior.
  - To ensure the toolchain “sees” the same logic, we duplicate the ROI’s integer operations in `main` (outside the ROI), so both Ir and quantum resources change coherently with the ROI size.

- **Tuning Ir “resolution”:**
  - The ROI is built from “units” of integer statements. Each unit adds a fairly constant number of machine instructions when compiled at `-O0`.
  - We control the **Ir slope** per unit with `roi_unit_ops` (number of statements inside the unit):
    - `roi_unit_ops ≈ 1` → Ir grows ~+3 per unit.
    - `roi_unit_ops ≈ 2` → Ir grows ~+7–8 per unit.
    - `roi_unit_ops ≈ 4` → Ir grows ~+14–16 per unit.
  - The exact slope depends on compiler and architecture, but is consistent within a corpus.

- **Bins and presence maps:**
  - For visualization/coverage checks we use **fixed grid bins** on both axes.
  - Black = at least one program lands in that bin; White = empty.
  - Ticks show the **left edges** of bins, so when `x-bin-w=1` starting at 1, labels read `1, 2, 3, …`; when `y-bin-w=10` starting at 10, labels read `10, 20, 30, …`.

- **Normalization helpers (optional for analysis):**
  - Per-CC **k indexing**: within each CC group, sort by Ir and assign `k=1..N`. This gives a perfect CC×k grid independent of absolute Ir.
  - **Baseline removal**: subtract the per-CC minimum Ir (optionally +1 to start at 1). Useful to factor out constant offsets.

- **Compatibility with the C→Quantum toolchain:**
  - The ROI uses only integer arithmetic; no inline asm, no includes, no I/O. The pipeline parses it, lowers to classical MLIR and to the custom quantum MLIR, and then to QASM.
  - The ROI call itself (`roi_block()`) is not directly lowered to a call in the quantum pipeline; what matters is that we duplicate the same integer ops in `main`, so resource usage tracks the ROI size.

- **Determinism and portability:**
  - Generator emits deterministic code for a given set of flags; there’s no RNG.
  - Absolute Ir values can vary across machines/compilers; the **trend** (slope per unit and baseline) is stable within a run and is what binning/normalization uses.

---

## 2) Script Manual (how to run)

### A. Generate corpora — `tools/gen_cc_ir_programs.py`

Recommended call (after activating your env, e.g., `conda activate cotenv`):

```
python tools/gen_cc_ir_programs.py gen-grid \
  --out-dir corpus_grid10 \
  --cc-min 1 --cc-max 10 \
  --k 10 \
  --exact-k \
  --roi --roi-region nops --roi-mode func \
  --roi-unit-ops 1 \
  --ops-per-iter 1
```

This generates a 10×10 grid (CC=1..10, k=1..10) where ROI uses integer-only ops; ROI size grows with k; Ir steps are small (~+3 per k) for higher resolution.

- **Subcommands:**
  - `gen-one`: emit a single C program.
  - `gen-range`: fixed CC, vary iteration count (legacy) or ROI size.
  - `gen-grid`: sweep CC over a range and generate `k` variants per CC (preferred for datasets).

- **Common flags:**
  - `--out-dir DIR`: output directory for generated `.c` files.
  - `--cc INT`: target cyclomatic complexity for `gen-one`/`gen-range`.
  - `--ops-per-iter INT`: legacy loop-body size (not needed for ROI usage).

- **ROI-related flags (recommended):**
  - `--roi`: enable region-of-interest generation.
  - `--roi-region nops`: select the ROI in the generator (kept as name; generates integer ops).
  - `--roi-mode func`: emit `roi_block()` as a separate function (enables Callgrind toggling).
  - `--roi-unit-ops INT`: integer statements per ROI unit (controls Ir slope: 1≈+3, 2≈+7–8, 4≈+14–16).
  - Internally, the generator duplicates the ROI ops in `main` so the toolchain lowers them to quantum IR (no extra flags needed).

- **`gen-grid` flags:**
  - `--cc-min INT --cc-max INT`: CC range (inclusive).
  - `--k INT`: number of ROI sizes (units) per CC row.
  - `--exact-k`: instructs the generator to use the ROI-based path (no loops) with `k = 1..K` units.
  - Example (10×10 grid, small Ir steps):
    - `conda run -n cotenv python tools/gen_cc_ir_programs.py gen-grid \
       --out-dir corpus_grid10 \
       --cc-min 1 --cc-max 10 --k 10 \
       --exact-k --roi --roi-region nops --roi-mode func \
       --roi-unit-ops 1`

### B. Measure Ir — `tools/scan_cc_ir.py`

Recommended call (after activating your env):

```
python tools/scan_cc_ir.py \
  --corpus corpus_grid10 \
  --roi --roi-func roi_block \
  --progress plain
```

This measures only the ROI (`roi_block`) with Callgrind and writes `tools/results/corpus_grid10_cc_ir.csv`.

- **Required:**
  - `--corpus DIR`: folder with the generated `.c` programs.

- **ROI mode (recommended):**
  - `--roi`: run Callgrind with `--collect-atstart=no`.
  - `--roi-func roi_block`: toggles collection for the ROI function.
  - This makes `Ir` measure only the ROI ops.

- **Other flags:**
  - `--cc gcc`: C compiler (default `gcc`).
  - `--arch x86-64|arm|...`: optional target architecture hint.
  - `--input-cmd "..."`: optional stdin for programs (not used here).
  - `--progress auto|plain|none`, `--show-stages`: logging style.
  - `--out PATH`: output CSV (by default: `tools/results/<corpus>_cc_ir.csv`).

- **Example (scan ROI):**
  - `conda run -n cotenv python tools/scan_cc_ir.py \
     --corpus corpus_grid10 \
     --roi --roi-func roi_block \
     --progress plain`

### C. Normalize/transform CSVs

Per-CC k indexing (after activating your env):

```
python tools/normalize_k_from_ir.py \
  --in tools/results/corpus_grid10_cc_ir.csv \
  --out tools/results/corpus_grid10_cc_ir_k.csv
```

Per-CC baseline removal starting from 1 (after activating your env):

```
python tools/remove_ir_baseline.py \
  tools/results/corpus_grid10_cc_ir.csv \
  --start-one
```

- **Per-CC k indexing — `tools/normalize_k_from_ir.py`:**
  - `--in IN_CSV --out OUT_CSV`
  - Groups rows by `cyclomatic`, sorts by `ir_instructions`, assigns `k=1..N` per group.
  - Produces columns: `file, cyclomatic, k, ir_instructions`.

- **Baseline removal — `tools/remove_ir_baseline.py`:**
  - `path/to/metrics.csv [--global] [--group COL] [--start-one] [--out PATH]`
  - Modifies only `ir_instructions` by subtracting the minimum per group (default: per-CC if the column exists; otherwise global min). `--start-one` adds +1 after removal.
  - All other columns are preserved.

### D. Fixed-grid presence plot — `tools/plot_bw_bins.py`

Fast use example (5-instructions bins)
```
python tools/plot_bw_bins.py \
  --csv tools/results/corpus_grid10_cc_ir.csv \
  --x cyclomatic --y ir_instructions \
  --x-bin-w 1 --y-bin-w 5 \
  --out tools/results/corpus_grid10_bins10_bw.png
```

Recommended call for Ir-binned presence (after activating your env):

```
python tools/plot_bw_bins.py \
  --csv tools/results/corpus_grid10_cc_ir.csv \
  --x cyclomatic --y ir_instructions \
  --x-bin-w 1 --y-bin-w 10 \
  --x-min 1 --x-max 10 \
  --y-min 0 --y-max 150 \
  --out tools/results/corpus_grid10_bins10_bw.png \
  --title "BW Presence (X=1, Y=10)"
```

Recommended call for perfect CC×k grid (after activating your env):

```
python tools/plot_bw_bins.py \
  --csv tools/results/corpus_grid10_cc_ir_k.csv \
  --x cyclomatic --y k \
  --x-bin-w 1 --y-bin-w 1 \
  --x-min 1 --x-max 10 \
  --y-min 1 --y-max 10 \
  --out tools/results/corpus_grid10_k_bw.png \
  --title "BW Presence (CC vs k)"
```

- **Purpose:** Produce a black/white heatmap over **fixed-size bins** that shows bin coverage explicitly.

- **Core flags:**
  - `--csv CSV`: source metrics CSV.
  - `--x COL --y COL`: columns to plot (e.g., `cyclomatic`, `ir_instructions` or `k`).
  - `--x-bin-w W --y-bin-w W`: bin widths on each axis (e.g., X=1, Y=10).
  - `--x-min MIN --x-max MAX --y-min MIN --y-max MAX`: explicit ranges (recommended to force clean tick labels).
  - `--out PNG`: output path for the image; `--title` optional.

- **Behavior:**
  - Black = at least one row falls in that (X,Y) bin; White = empty.
  - Tick labels use bin **left edges**; with `--x-bin-w 1, --x-min 1`, ticks read `1,2,...`; with `--y-bin-w 10, --y-min 10`, ticks read `10,20,...`.

- **Examples:**
  - X=CC with unit bins, Y=Ir with 10-wide bins starting at 0:
    - `conda run -n cotenv python tools/plot_bw_bins.py \
       --csv tools/results/corpus_grid10_cc_ir.csv \
       --x cyclomatic --y ir_instructions \
       --x-bin-w 1 --y-bin-w 10 \
       --x-min 1 --x-max 10 --y-min 0 --y-max 150 \
       --out tools/results/grid10_bins10_bw.png \
       --title "BW Presence (X=1, Y=10)"`
  - X=CC with unit bins, Y=k (normalized), 10×10 full grid:
    - `conda run -n cotenv python tools/plot_bw_bins.py \
       --csv tools/results/cc_ir_grid10_exact_k.csv \
       --x cyclomatic --y k \
       --x-bin-w 1 --y-bin-w 1 \
       --x-min 1 --x-max 10 --y-min 1 --y-max 10 \
       --out tools/results/grid10_k_bw.png`

---

### Practical Notes & Caveats

- Use `--roi` scanning to isolate the ROI and remove startup/prologue noise.
- Choose `--roi-unit-ops` to match your bin width (e.g., Y=10 wide bins pair well with ~+7–8 or ~+14–16 slopes).
- Absolute Ir varies by platform; the **pattern** (slope and monotonicity) is what you’ll use for bin coverage and trend analysis.
- The generator uses only integer arithmetic; no asm or includes are required for the dataset used in correlations.
