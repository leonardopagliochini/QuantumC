# CC×Ir Binned Dataset — How To Generate, Scan, and Verify

This guide shows how to build a complete, pipeline‑friendly CC×Ir dataset with a fixed number of Ir bins per CC, scan metrics, and verify coverage.

## Prerequisites

- Activate your environment (contains xdsl, qiskit, valgrind):
  - `conda activate cotenv`
- Repo root as working directory.

## 1) Generate CC 1..10 with 20 Ir bins per CC

- Command (pipeline‑clean code; main only, int ops, top‑level ifs):

```
python tools/gen_cc_ir_aligned.py gen-bins \
  --out-dir corpus_cc10_bins20 \
  --cc-min 1 --cc-max 10 \
  --bins 20 \
  --pre-ops 1 \
  --cc gcc --arch x86-64 \
  --verify-window 3 \
  --progress
```

What it does:
- Calibrates per‑CC Ir slope using Callgrind (temporary binaries only).
- Chooses a common Ir range across all CC for pre_steps in [1..64].
- Splits that range into 20 equal‑width bins.
- For each CC×bin, finds pre_steps so measured Ir falls inside the bin.
- Emits only pipeline‑accepted code: one `main`, local `int` vars, `+ - * /` and top‑level `if`s. No loops/macros/ROI/globals/asm.
- Writes a plan file: `corpus_cc10_bins20/bins_plan.csv`.

Notes:
- To smoke‑test first, try fewer bins: `--bins 8`.
- To widen the Ir span: increase `--pmax` (default 64), e.g., `--pmax 96`.
- To search more around a predicted step: increase `--verify-window` (e.g., 5).
- To fix bin width explicitly: add `--bin-w 5`.

## 2) Scan CC + Ir (whole program)

- Command:

```
python tools/scan_cc_ir.py \
  --corpus corpus_cc10_bins20 \
  --cc gcc --arch x86-64 \
  --progress plain --show-stages \
  --out tools/results/corpus_cc10_bins20_cc_ir.csv
```

- Output CSV columns: `file, cyclomatic, ir_instructions`.
- Ir is whole‑program (no ROI flags or macros used).

## 3) Verify coverage — one program per bin per CC

- Command:

```
python - << 'PY'
import csv, math, sys
from collections import defaultdict

csv_path = 'tools/results/corpus_cc10_bins20_cc_ir.csv'
B = 20  # number of bins to verify

rows = []
with open(csv_path) as f:
    rd = csv.DictReader(f)
    for r in rd:
        try:
            cc = int(float(r['cyclomatic']))
            ir = int(float(r['ir_instructions']))
            fn = r['file']
            rows.append((cc, ir, fn))
        except Exception:
            pass

if not rows:
    print('No rows found. Did the scan run?')
    sys.exit(1)

# Derive common bins from dataset (like plot script): [edge_i, edge_{i+1})
all_irs = [ir for _, ir, _ in rows]
ir_min = min(all_irs)
ir_max = max(all_irs)
start = math.floor(ir_min)
W = max(1, math.ceil((ir_max - start) / B))
edges = [start + i * W for i in range(B + 1)]

bins_by_cc = defaultdict(lambda: [0] * B)
files_by_cc_bin = defaultdict(lambda: [None] * B)

def bin_idx(ir: int):
    if ir < edges[0] or ir >= edges[-1]:
        return None
    i = (ir - edges[0]) // W
    return int(i) if 0 <= i < B else None

for cc, ir, fn in rows:
    i = bin_idx(ir)
    if i is not None and bins_by_cc[cc][i] == 0:
        bins_by_cc[cc][i] = 1
        files_by_cc_bin[cc][i] = fn

ok_cc = []
bad_cc = []
for cc in sorted(bins_by_cc.keys()):
    covered = sum(bins_by_cc[cc])
    if covered == B:
        ok_cc.append(cc)
    else:
        bad_cc.append((cc, covered, [i+1 for i,v in enumerate(bins_by_cc[cc]) if v==0]))

print(f"Bins: B={B}, width={W}, start={start}, range=[{edges[0]}, {edges[-1]})")
if ok_cc:
    print('Full coverage (one per bin):', ok_cc)
if bad_cc:
    print('Partial coverage:')
    for cc, covered, missing in bad_cc:
        print(f'  CC={cc}: {covered}/{B} — missing bins {missing}')
PY
```

If coverage is partial for any CC:
- Regenerate with a larger search window: add `--verify-window 5`.
- Increase Ir span: add `--pmax 96`.
- Fix bin width: add `--bin-w 5` and regenerate.

## (Optional) Plot presence heatmap

- Presence plot with 5‑wide Ir bins:

```
python tools/plot_bw_bins.py \
  --csv tools/results/corpus_cc10_bins20_cc_ir.csv \
  --x cyclomatic --y ir_instructions \
  --x-bin-w 1 --y-bin-w 5 \
  --x-min 1 --x-max 10 \
  --out tools/results/corpus_cc10_bins20_bw.png \
  --title "CC vs Ir presence (bin=5)"
```

## (Optional) Pipeline sanity check

- Run the QuantumC pipeline on each file and record OK/FAIL:

```
bash tools/check_pipeline_corpus.sh corpus_cc10_bins20
```

Outputs:
- `tools/results/corpus_cc10_bins20_pipeline_summary.csv`
- `tools/results/corpus_cc10_bins20_pipeline_ok.txt`
- `tools/results/corpus_cc10_bins20_pipeline_fail.txt`
- Per‑file logs in `tools/results/pipeline_logs_corpus_cc10_bins20/`

---

All generated programs are pipeline‑friendly by construction: one `main`, integer ops, top‑level `if`s only; no loops, no ROI, no macros, no globals, no inline asm.

