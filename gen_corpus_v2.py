#!/usr/bin/env python3
# tools/gen_corpus_v2.py
import argparse
import pathlib
import hashlib
import random

# ---------- utils ----------

def header() -> str:
    return "#include <stdio.h>\nint main(){\n  volatile int acc=0;\n"

def footer(ret: str = "acc") -> str:
    return f"  (void){ret};\n  return 0;\n}}\n"

def seed_rng(tag: str) -> random.Random:
    h = int.from_bytes(hashlib.blake2b(tag.encode(), digest_size=8).digest(), "little")
    return random.Random(h)

def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

def rand_imm(rng: random.Random, IMM_MIN: int, IMM_MAX: int, avoid=None) -> int:
    if avoid is None: avoid = set()
    choices = [IMM_MIN, IMM_MIN+1, -3, -2, -1, 0, 1, 2, 3, IMM_MAX-1, IMM_MAX]
    choices = [c for c in choices if IMM_MIN <= c <= IMM_MAX and c not in avoid]
    if not choices: choices = [IMM_MIN, IMM_MAX]
    return rng.choice(choices)

def rand_imm_interior(rng: random.Random, IMM_MIN: int, IMM_MAX: int, margin: int = 1, avoid=None) -> int:
    if avoid is None: avoid = set()
    lo, hi = IMM_MIN + margin, IMM_MAX - margin
    if lo > hi:
        return rand_imm(rng, IMM_MIN, IMM_MAX, avoid=avoid)
    while True:
        v = rng.randint(lo, hi)
        if v not in avoid:
            return v

def rand_imm_nonneg_interior(rng: random.Random, IMM_MAX: int, margin: int = 1, avoid=None) -> int:
    """Immediato >= 0 e lontano dal bordo alto."""
    if avoid is None: avoid = set()
    lo, hi = 0, max(0, IMM_MAX - margin)
    if lo > hi:
        return 0
    while True:
        v = rng.randint(lo, hi)
        if v not in avoid:
            return v

def unique_write(path: pathlib.Path, src: str, seen_hashes: set) -> bool:
    h = hashlib.sha1(src.encode()).hexdigest()
    if h in seen_hashes:
        return False
    seen_hashes.add(h)
    path.write_text(src)
    return True

# ---------- families ----------

def gen_for(tc: int, ops_per_iter: int, variant: int, IMM_MIN: int, IMM_MAX: int) -> str:
    """
    For 'safe':
      - a0 >= 0
      - solo immediati non negativi nelle somme (niente -K)
      - pattern semplici (niente aggiornare b con a)
    """
    rng = seed_rng(f"for:{tc}:{ops_per_iter}:{variant}")
    tc = clamp(tc, 0, IMM_MAX)
    body = header()
    a0 = max(0, rand_imm_interior(rng, IMM_MIN, IMM_MAX))  # forza non-negativo
    body += f"  int a={a0}, b=2, c=3;\n"
    body += f"  for(int i=0;i<{tc};i=i+1) {{\n"
    for k in range(ops_per_iter):
        k1 = rand_imm_nonneg_interior(rng, IMM_MAX, margin=1)
        if k % 3 == 0:
            body += f"    a = a*3 + i + {k1};\n"         # tutti + e immediato >= 0
        elif k % 3 == 1:
            body += f"    a = a + {k1};\n"
        else:
            body += f"    c = c + {k1}; a = a + c;\n"
    body += "  }\n"
    body += footer("a")
    return body


def gen_ifnest(depth: int, variant: int, IMM_MIN: int, IMM_MAX: int) -> str:
    rng = seed_rng(f"ifnest:{depth}:{variant}")
    body = header() + "  int x=0, y=1;\n"
    for d in range(depth):
        k  = rand_imm_interior(rng, IMM_MIN, IMM_MAX)
        th = rand_imm_interior(rng, IMM_MIN, IMM_MAX, avoid={k})
        op = "<" if (d + variant) % 2 == 0 else ">"
        lhs = "y" if d % 2 == 0 else "x"
        body += f"  if (({lhs} + {k}) {op} {th}) {{ x+=1; }} else {{ x-=1; }}\n"
    body += footer("x")
    return body

def gen_elseif(n: int, variant: int, IMM_MIN: int, IMM_MAX: int) -> str:
    rng = seed_rng(f"elseif:{n}:{variant}")
    body = header() + "  int k=0, v=5;\n"
    vals = list({clamp(i, IMM_MIN, IMM_MAX) for i in range(0, max(2, n+1))})
    rng.shuffle(vals)
    body += f"  if (v=={vals[0]}) k+={abs(vals[0])%3+1};\n"
    for i in range(1, min(n, len(vals))):
        inc = abs(vals[i]) % 5 + 1
        body += f"  else if (v=={vals[i]}) k+={inc};\n"
    body += "  else k-=1;\n" + footer("k")
    return body

def gen_bool(depth: int, variant: int, IMM_MIN: int, IMM_MAX: int) -> str:
    """
    Booleani robusti:
      - SOLO immediati non negativi nelle somme (niente (c + -6))
      - soglie strictly greater dei k (th > k), scelte interne
      - SOLO '<' come confronto (evita <=/>= e traduzioni a imm±1)
      - connettivo unico per file: AND o OR
    """
    rng = seed_rng(f"bool:{depth}:{variant}")
    body = header() + "  int a=1, b=2, c=3;\n"
    use_and = (variant % 2 == 0)
    parts = ["(a > 0)"]
    for i in range(1, depth+1):
        k1 = rand_imm_nonneg_interior(rng, IMM_MAX, margin=1)
        # th deve essere > k1 e lontano dal bordo alto
        lo_th = min(k1 + 1, max(0, IMM_MAX - 1))
        hi_th = max(lo_th, IMM_MAX - 1)
        th = rng.randint(lo_th, hi_th) if lo_th <= hi_th else max(k1 + 1, 1)
        term_var = "b" if ((i + variant) % 2 == 0) else "c"
        parts.append(f"(({term_var} + {k1}) < {th})")
    glue = " && " if use_and else " || "
    cond = glue.join(parts)
    body += f"  if ({cond}) {{ a+=b; }} else {{ a-=c; }}\n"
    body += footer("a")
    return body

def gen_mix(tc: int, depth: int, variant: int, IMM_MIN: int, IMM_MAX: int) -> str:
    rng = seed_rng(f"mix:{tc}:{depth}:{variant}")
    tc = clamp(tc, 0, IMM_MAX)
    body = header() + "  int s=0;\n"
    body += f"  for(int i=0;i<{tc};i=i+1) {{\n"
    for d in range(depth):
        k  = rand_imm_interior(rng, IMM_MIN, IMM_MAX)
        th = rand_imm_interior(rng, IMM_MIN, IMM_MAX, avoid={k})
        if (d + variant) % 2 == 0:
            body += f"    if ((i + {k}) < {th}) s+=i; else s-=1;\n"
        else:
            body += f"    if ((s + {k}) > {th}) s-=i; else s+=1;\n"
    body += "  }\n" + footer("s")
    return body

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bits", type=int, default=16, help="bitwidth della rappresentazione intera della pipeline")
    ap.add_argument("--target", type=int, default=180, help="circa quanti file generare (indicativo)")
    ap.add_argument("--out", type=str, default="corpus_c", help="cartella di output per i .c")
    args = ap.parse_args()

    imm_bits = max(3, args.bits // 2)  # osservato: con bits=8 -> imm_bits=4
    IMM_MIN, IMM_MAX = -(1 << (imm_bits - 1)), (1 << (imm_bits - 1)) - 1
    print(f"[gen] immediate range = {IMM_MIN}..{IMM_MAX} (imm_bits={imm_bits})")

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    seen = set()
    count = 0

    for tc in [2, 3, 5, 7]:
        for ops in [1, 2, 4]:
            for v in range(2):
                src = gen_for(tc, ops, v, IMM_MIN, IMM_MAX)
                name = out_dir / f"for_tc{tc}_ops{ops}_v{v}.c"
                if unique_write(name, src, seen): count += 1

    for d in [1, 2, 3, 4, 5, 6, 8, 10]:
        for v in range(3):
            src = gen_ifnest(d, v, IMM_MIN, IMM_MAX)
            name = out_dir / f"ifnest_d{d}_v{v}.c"
            if unique_write(name, src, seen): count += 1

    for n in [2, 3, 4, 5, 6]:
        for v in range(3):
            src = gen_elseif(n, v, IMM_MIN, IMM_MAX)
            name = out_dir / f"elseif_n{n}_v{v}.c"
            if unique_write(name, src, seen): count += 1

    for d in [1, 2, 3, 4, 5]:
        for v in range(3):
            src = gen_bool(d, v, IMM_MIN, IMM_MAX)
            name = out_dir / f"bool_d{d}_v{v}.c"
            if unique_write(name, src, seen): count += 1

    for tc in [2, 3, 5, 7]:
        for d in [1, 2, 3, 4, 5]:
            if (tc + d) % 2 == 0:
                for v in range(2):
                    src = gen_mix(tc, d, v, IMM_MIN, IMM_MAX)
                    name = out_dir / f"mix_tc{tc}_d{d}_v{v}.c"
                    if unique_write(name, src, seen): count += 1

    print(f"[gen] wrote {count} unique files in {out_dir}")

if __name__ == "__main__":
    main()