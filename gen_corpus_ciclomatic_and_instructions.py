#!/usr/bin/env python3
"""
Genera due corpora C:
- corpus_c_ciclomatic: 300 file con if annidati (complessità ciclomatica crescente).
- corpus_c_instructions: 300 file con addizioni sequenziali (instruction count crescente).
Tutti i confronti sono contro literal interi (nessun '%').
"""

import argparse
import pathlib

def gen_cyclomatic_nested_ifs(depth: int) -> str:
    """
    Genera 'depth' if annidati.
    Ogni if contiene `a = a + 1;`.
    Nessun modulo: solo confronti con literal.
    """
    b = []
    b.append("int main(){\n  volatile int acc=0;\n")
    b.append("  int a=0;\n")

    for i in range(depth):
        K = i + 1   # literal puro
        indent = "  " * (i + 1)
        b.append(f"{indent}if (a < {K}) {{\n")

    b.append("  " * (depth + 1) + "a = a + 1;\n")

    for i in reversed(range(depth)):
        indent = "  " * (i + 1)
        b.append(f"{indent}}}\n")

    b.append("  (void)a;\n  return 0;\n}\n")
    return "".join(b)


def gen_sequential_additions(n_adds: int) -> str:
    """
    Genera un main con n_adds addizioni in sequenza.
    """
    b = []
    b.append("int main(){\n  volatile int acc=0;\n")
    b.append("  int a=0;\n")
    for _ in range(n_adds):
        b.append("  a = a + 1;\n")
    b.append("  (void)a;\n  return 0;\n}\n")
    return "".join(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-cyclomatic", type=str, default="corpus_c_ciclomatic")
    ap.add_argument("--out-instructions", type=str, default="corpus_c_instructions")
    ap.add_argument("--max-cyclomatic", type=int, default=30)
    ap.add_argument("--max-instructions", type=int, default=30)
    args = ap.parse_args()

    out_cyclo = pathlib.Path(args.out_cyclomatic)
    out_instr = pathlib.Path(args.out_instructions)

    out_cyclo.mkdir(parents=True, exist_ok=True)
    out_instr.mkdir(parents=True, exist_ok=True)

    # corpus ciclomatico
    for depth in range(1, args.max_cyclomatic + 1):
        src = gen_cyclomatic_nested_ifs(depth)
        (out_cyclo / f"cyclo_ifnest_depth{depth:03d}.c").write_text(src)

    # corpus instruction count
    for n in range(1, args.max_instructions + 1):
        src = gen_sequential_additions(n)
        (out_instr / f"instructions_addseq_{n:03d}.c").write_text(src)

    print(f"[gen] wrote {args.max_cyclomatic} cyclomatic and {args.max_instructions} instruction files.")


if __name__ == "__main__":
    main()
