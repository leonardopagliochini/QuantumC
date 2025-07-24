# `run_all_pipeline.py` Overview

`run_all_pipeline.py` is a small driver script that executes the full QuantumIR
compilation pipeline over every JSON file produced from the C test programs.
It is intended as a bulk-processing helper used during development and testing.

The script expects the `json_out/` directory to contain one or more JSON files
obtained by running `clang -ast-dump=json` (see `generate_ast.py`).  For each
input JSON file it performs the following steps:

1. **Instantiate the pipeline** – A :class:`QuantumIR` object (defined in
   `pipeline.py`) is created pointing at the JSON file.
2. **Parse and lower** – The pipeline parses the JSON into dataclasses (`run_dataclass`),
   lowers the AST to classical MLIR (`run_generate_ir`) and finally translates the
   result to the custom quantum dialect (`run_generate_quantum_ir`).
3. **Emit MLIR modules** – Two MLIR files are written under `mlir_out/`:
   `<name>_classical.mlir` contains the classical IR and `<name>_quantum.mlir`
   contains the quantum dialect version.  The xDSL printer is used for emission.

In effect, running the script provides fresh MLIR artifacts for all examples in
one go.  Those artifacts are later consumed by the testing utilities
(`test_all_c_files_to_fix.py` and `test_mlir_equivalence_to_fix.py`) which
verify that the classical and quantum variants compute identical results.

## Role in the overall project

The repository implements a minimal C–to–quantum compilation experiment.  The
process, as outlined in `README.md`, is:

1. **Generate ASTs** with `clang` (`generate_ast.py`).
2. **Lower to MLIR** using `pipeline.py` and `mlir_generator.py`.
3. **Translate to the quantum dialect** with `quantum_translate.py`.
4. **(Optional) Build quantum circuits** through `circuit_pipeline.py`.

`run_all_pipeline.py` automates steps 2–3 for every available input AST and thus
acts as the bridge between raw JSON and the MLIR modules used for testing and
further experimentation.

## Supported C subset

Only a very small fragment of C is currently handled.  The implementation can
parse and lower:

- **Integer literals** and variable references.
- **Variable declarations** of type `int` with optional initialization.
- **Assignments** to previously declared variables.
- **Binary arithmetic operators:** `+`, `-`, `*`, `/`.
- **Comparisons:** `==`, `!=`, `<`, `<=`, `>`, `>=`.
- **Logical operators** `&&` and `||` inside `if` conditions (lowered to nested
  conditionals).
- **If statements** with optional `else` blocks.
- **For loops** with init, condition and increment expressions.  Loops are
  unrolled up to `MAX_UNROLL = 10` iterations during lowering.
- **Return statements** with or without a value.
- **Binary operations with an immediate constant** on one side, enabling the
  use of specialized MLIR ops such as `iarith.addi_imm`.

Unary operators are recognized in the AST but are not yet lowered to MLIR.
No pointer arithmetic, floating point types, arrays or function calls are
supported.

## Theoretical considerations

`run_all_pipeline.py` itself is a thin wrapper, but the modules it invokes
implement a classic front-end–to–IR translation followed by a domain-specific
rewriting pass:

- `mlir_generator.py` performs a syntax-driven traversal of the dataclass AST.
  It emits xDSL operations representing control flow and arithmetic.  A small
  custom dialect (`dialect_ops.py`) provides immediate-operand variants of the
  standard arithmetic ops.  Control-flow structures (`if`, `for`) are expanded
  into basic blocks and branches.  The loop translator performs a fixed bound
  unrolling to avoid structured loops in the resulting IR.

- `quantum_translate.py` takes the classical MLIR and creates a new module where
  arithmetic instructions are replaced by their quantum equivalents defined in
  `quantum_dialect.py`.  Register allocation is explicitly modeled: each value
  lives in a quantum register whose version is tracked so that values can be
  recomputed when overwritten.  Controlled operations use additional control
  bits derived from conditional branches.

By repeatedly invoking this pipeline for every JSON file, `run_all_pipeline.py`
produces side‑by‑side classical and quantum IR modules that reflect exactly the
same semantics, enabling the project’s testing methodology where both variants
are interpreted and compared.