#!/usr/bin/env python3
"""
Generate C corpora where each addition contributes a cost depending on its conditional depth:
- Outside any if:         cost = 1
- Inside k nested ifs:    cost = 2*k   (k = 1,2,3,...)

For a given TOTAL instruction budget T, we enumerate all nonnegative integer
solutions to:
    x0*1 + x1*2 + x2*4 + x3*6 + ... + xK*(2*K) = T
(where K = floor(T/2)), and generate one C program per solution.

Concretely:
- We produce files for T in {2,4,6,...,30}.
- For each solution, we emit:
    - x0 additions outside any if;
    - For each k>=1 with xk>0: one chain of k nested ifs containing xk additions.

Notes:
- All if conditions compare against integer literals only.
- We keep code compact by sharing the k-nest among the xk additions at that depth.
"""

import argparse
import pathlib
from typing import Dict, List, Tuple


# -------------------------------------
# Code generation helpers
# -------------------------------------

def gen_nested_ifs_block(depth: int, inner_lines: List[str], literal_seed: int) -> Tuple[str, int]:
    """
    Generate a chain of `depth` nested ifs with integer literal thresholds.
    Insert `inner_lines` inside the innermost block.
    Returns (code, next_literal_seed).
    """
    buf = []
    # Open nested ifs
    for i in range(depth):
        K = literal_seed + i + 1   # ensure distinct literals
        indent = "  " * (i + 1)
        buf.append(f"{indent}if (a < {K}) {{\n")
    # Inner body
    buf.extend("  " * (depth + 1) + line for line in inner_lines)
    # Close ifs
    for i in reversed(range(depth)):
        indent = "  " * (i + 1)
        buf.append(f"{indent}}}\n")
    return "".join(buf), literal_seed + depth


def gen_program_from_allocation(total: int, alloc: Dict[int, int]) -> str:
    """
    Build a C program given an allocation:
      alloc[0] = x0 additions outside any if
      alloc[k] = xk additions inside k nested ifs (k>=1)
    """
    buf: List[str] = []
    buf.append("int main(){\n")
    buf.append("  volatile int acc = 0;\n")
    buf.append("  int a = 0;\n")

    # Outside-any-if additions
    x0 = alloc.get(0, 0)
    for _ in range(x0):
        buf.append("  a = a + 1;\n")

    # Deterministic order by increasing depth
    literal_seed = 0
    for depth in sorted(k for k in alloc.keys() if k >= 1):
        cnt = alloc[depth]
        if cnt <= 0:
            continue
        inner_lines = ["a = a + 1;\n"] * cnt
        block_code, literal_seed = gen_nested_ifs_block(depth, inner_lines, literal_seed)
        buf.append(block_code)

    # Epilogue
    buf.append("  (void)a;\n")
    buf.append("  return 0;\n")
    buf.append("}\n")
    return "".join(buf)


# -------------------------------------
# Combinatorics (enumerate all allocations)
# -------------------------------------

def enumerate_allocations(total: int) -> List[Dict[int, int]]:
    """
    Enumerate all nonnegative integer solutions to:
        x0*1 + sum_{k=1..K} xk*(2*k) = total
    with K = floor(total/2).

    Returns a list of allocations {0:x0, 1:x1, 2:x2, ...} (sparse dicts).
    We ensure uniqueness by recursing with nondecreasing depths.
    """
    weights = {0: 1}
    K = total // 2
    for k in range(1, K + 1):
        weights[k] = 2 * k  # 2,4,6,...

    depths_sorted = sorted(weights.keys())  # [0,1,2,...,K]
    out: List[Dict[int, int]] = []

    def backtrack(i: int, remaining: int, current: Dict[int, int]):
        if i == len(depths_sorted):
            if remaining == 0:
                # prune zeros
                alloc = {k: v for k, v in current.items() if v > 0}
                out.append(alloc)
            return

        depth = depths_sorted[i]
        w = weights[depth]
        max_cnt = remaining // w

        for cnt in range(max_cnt + 1):
            current[depth] = cnt
            backtrack(i + 1, remaining - cnt * w, current)
        current.pop(depth, None)  # cleanup

    backtrack(0, total, {})
    return out


# -------------------------------------
# Filenames / CLI
# -------------------------------------

def alloc_slug(total: int, alloc: Dict[int, int], idx: int) -> str:
    """
    Build a descriptive slug, e.g.:
      T10_idx003_x0_6_x1_2_x3_1
      means total=10, variant #3, 6 outside, 2 inside 1-if, 1 inside 3-ifs
    """
    parts = [f"T{total:02d}", f"idx{idx:03d}"]
    x0 = alloc.get(0, 0)
    parts.append(f"x0_{x0}")
    for k in sorted(k for k in alloc.keys() if k >= 1):
        parts.append(f"x{k}_{alloc[k]}")
    return "_".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out-instructions",
        type=str,
        default="corpus_c_instructions_weighted",
        help="Output folder for instruction-weighted corpora",
    )
    ap.add_argument(
        "--min-total", type=int, default=2, help="Minimum total instruction budget (even)"
    )
    ap.add_argument(
        "--max-total", type=int, default=30, help="Maximum total instruction budget (even)"
    )
    ap.add_argument(
        "--step", type=int, default=2, help="Step between totals (e.g. 2 for 2,4,6,...)"
    )
    args = ap.parse_args()

    out_dir = pathlib.Path(args.out_instructions)
    out_dir.mkdir(parents=True, exist_ok=True)

    totals = [t for t in range(args.min_total, args.max_total + 1, args.step) if t % 2 == 0]

    grand_count = 0
    for T in totals:
        allocations = enumerate_allocations(T)

        # Stable order: sort by (x0 desc, then vector of xk desc) for reproducibility
        def alloc_key(alloc: Dict[int, int]):
            x0 = alloc.get(0, 0)
            vec = tuple(alloc.get(k, 0) for k in range(1, (T // 2) + 1))
            return (-x0, tuple(-v for v in vec))

        allocations.sort(key=alloc_key)

        for idx, alloc in enumerate(allocations, start=1):
            c_src = gen_program_from_allocation(T, alloc)
            slug = alloc_slug(T, alloc, idx)
            (out_dir / f"instructions_{slug}.c").write_text(c_src)
            grand_count += 1

    print(f"[gen] wrote {grand_count} files across totals: {', '.join(map(str, totals))}.")


if __name__ == "__main__":
    main()
