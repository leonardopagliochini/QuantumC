# Benchmarking Workflow Guide

This document explains how the QuantumC benchmarking tooling is organised, how
the main scripts interact, and how to run a full study from dataset generation
to analysis. Keep this guide alongside the configuration templates in
`benchmarking/study_*.cfg` so that even if you trim your active plots the
reference material remains available.

## Environment & Prerequisites

- Activate the project Conda environment before running any script
- External tools required by various stages:
  - **gcc/clang** (or any C compiler that accepts `-O0 -g`).
  - **valgrind** with Callgrind and `callgrind_annotate` for instruction-count
    metrics.
  - **lizard** (Python module) for cyclomatic complexity.
  - The **pipeline** Python package shipped with QuantumC (loaded by
    `benchmark_runner`).
  - Optional: `tqdm` for progress bars.

## Directory Layout

```
benchmarking/
├── README.md                # this guide
├── study_generate.py        # create CC/Ir controlled C corpus
├── study_benchmark.py       # run the pipeline and collect metrics
├── study_scan.py            # quick CC/Ir scan without full pipeline
├── study_analyze.py         # plotting and curve fitting
├── study_generate.cfg       # generation template (TOML)
├── study_benchmark.cfg      # benchmarking template (TOML)
├── study_analyze.cfg        # plotting template (TOML)
├── bench_tools/             # shared helpers used by the scripts
└── tools_old/               # legacy one-off scripts kept for reference
```

Each study lives under `benchmarking/<study>/` with three subfolders created by
`study_generate.py`:

- `<study>_dataset`: generated (or manually curated) C sources.
- `<study>_results`: CSV metrics, temporary binaries, QASM dumps.
- `<study>_plots`: PDFs and summaries produced by the analysis stage.

## End-to-End Workflow

1. **Generate the corpus**
   ```bash
   conda run -n cotenv python benchmarking/study_generate.py <study> --config benchmarking/study_generate.cfg
   ```
   The generator calibrates each requested cyclomatic complexity (CC) level
   with Callgrind, discovers the instruction-count slope introduced by a single
   repetition of the straight-line "pre-work", and materialises one C file per
   CC × Ir offset pair. Output file names follow `ccXX_irYYYYYY.c`.

2. **(Optional) Fast CC/Ir sanity check**
   ```bash
   conda run -n cotenv python benchmarking/study_scan.py <study> --progress auto --show-stages
   ```
   `study_scan.py` is a convenience wrapper over
   `bench_tools/scan_cc_ir.py`. It recomputes CC (via Lizard) and Ir (via
   Callgrind) for the dataset and deposits `<study>_cc_ir.csv` inside the
   results directory. Use it when you tweak the corpus manually and want quick
   feedback before running the full pipeline.

3. **Benchmark through the QuantumC pipeline**
   ```bash
   conda run -n cotenv python benchmarking/study_benchmark.py <study> --config benchmarking/study_benchmark.cfg
   ```
   The benchmarker leverages `bench_tools/benchmark_runner.py` to compile each
   C program, run it through the QuantumC pipeline, collect Callgrind metrics,
   and extract QASM statistics. Results are appended incrementally to
   `<study>_results/<study>_metrics.csv`, then rewritten in a sorted, deduped
   form once the run ends.

4. **Analyse and plot metrics**
 ```bash
  conda run -n cotenv python benchmarking/study_analyze.py <study>
  ```
  `study_analyze.py` parses the metrics CSV and builds the plot/fit artefacts
  declared in `study_analyze.cfg`. Scatter plots are saved alongside
  best-fitting curves and per-model CSV summaries. The plotting backend is
  Matplotlib (Agg mode), so the step is non-interactive.

To execute the three stages back-to-back with the default configs, run:

```bash
python benchmarking/study_run_pipeline.py <study>
```
The helper reuses the default `study_*.cfg` files and skips the generation step
automatically if `benchmarking/<study>/` already exists.

Running the scripts repeatedly overwrites plots and fit summaries, while the
generator refuses to clobber an existing study directory—delete it or choose a
new name when regenerating from scratch.

## Configuration Files

### `study_generate.cfg`

- Provide the study name on the CLI when invoking the generator; the config
  does not need a `study` key.
- `cc_values`: strictly increasing CC targets (positive integers). Each value
  determines how many top-level `if` statements the generator emits.
- `ir_values`: strictly increasing offsets relative to the calibrated baseline
  Ir for each CC. The generator searches for the combination of pre-steps and
  optional extra operations that lands within a tolerance window around each
  `base + offset` target.

### `study_benchmark.cfg`

- Provide the study name on the CLI when invoking the benchmarker; the config
  does not need a `study` key.
- `bits`: number of qubits requested from the QuantumC pipeline.
- `cc`: compiler used to build temporary binaries for Callgrind (`gcc` by
  default).
- `arch`: optional architecture hint forwarded as `-march=`.
- `max_iter`: pipeline unrolling limit passed to `pipeline.compile_c_file`.
- `ir_roi_func`: optional Callgrind `--toggle-collect` target.
- `workers`: thread-pool size. Accepts integers or strings like `"max-1"`.
- `input_cmd`: stdin contents forwarded to the program under Callgrind.
- `progress` / `show_stages`: choose between quiet, basic, or tqdm-style
  progress and whether to print per-file stage logs.
- `[metrics]`: enable/disable individual columns in the output CSV (e.g. set
  `num_measure = false` to skip that measurement). Dependencies are handled for
  you—requesting `ir_offset` forces `cyclomatic` and `ir_instructions` on,
  while `cpu_time_s` automatically keeps both `user_time_s` and `sys_time_s`
  enabled so the summed wall-clock figure is emitted alongside the individual
  components.

### `study_analyze.cfg`

The upper half of the file contains commented templates for scatter plots and
heatmaps. The `Active Configuration` section defines the plots actually built
during `study_analyze.py`. Each `[[plots]]` table supports:

- `outfile`, `x`, `ys`, and optional styling (scatter vs line, titles, labels).
- `fit = true` to produce an additional best-fit figure and CSV summary.
- `fit_models` to list candidate models. Our customised
  `bench_tools/analyze_tools.py` guards against exponential overflow, prunes
  near-zero polynomial coefficients, and reports every attempted fit in the
  summary CSV while showing only the best curve on the plot.

## Core Helper Modules (`bench_tools/`)

- **`gen_cc_ir_programs.py`** – emits pipeline-friendly C code with exact CC
  and tunable instruction count via straight-line arithmetic "pre-work".
  `study_generate.py` imports `generate_c` from here.
- **`metrics_common.py`** – shared integration with Lizard and Callgrind plus
  QASM counting helpers. Used by both the scanner and the benchmark runner.
- **`scan_cc_ir.py`** – parallel CC/Ir scanner with progress reporting. Accepts
  the same arguments as the `study_scan.py` wrapper but can be run directly for
  ad-hoc corpora.
- **`benchmark_runner.py`** – orchestrates compilation, Callgrind runs, and
  `pipeline.compile_c_file` execution. Handles worker pools, stage logging, CSV
  accumulation, and binary/QASM caching under
  `<study>_results/{bin,qasm}`.
- **`analyze_tools.py`** – plotting and curve-fitting utilities invoked by
  `study_analyze.py`. Supports scatter/line plots, heatmaps, polynomial and
  exponential fits, per-model summaries, and automatic axis scaling.

The `bench_tools/results/` folder caches temporary Callgrind binaries for the
scanner. It is safe to delete when you want to free space.

## Legacy `tools_old/`

Older scripts (e.g. `whole_benchmark.py`) and archived results are kept for
historical reference. Prefer the modern `study_*` entry points, which wrap the
same logic with TOML configs and clearer directory layouts.

## Tips & Troubleshooting

- When a Callgrind run fails, inspect the per-file stage logs (enable
  `show_stages = true`) to see compiler stderr or pipeline tracebacks.
- `study_benchmark.py` rewrites the metrics CSV at the end. If you abort early,
  the incremental file still contains useful rows—rerun to deduplicate.
- Analysis uses Matplotlib in Agg mode; make sure `matplotlib.axes._secondary_axes`
  is available in your environment (install `matplotlib-base` via Conda if
  needed).
- The generator refuses to overwrite an existing study directory. Remove the
  folder or point `study` to a new name when iterating on corpus layouts.

With these pieces in place you can iterate quickly: tweak the configs, regenerate
datasets, rerun the pipeline, and keep the documentation above as the always-on
reference for how each stage works.
