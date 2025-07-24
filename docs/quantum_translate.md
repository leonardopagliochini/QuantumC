# Quantum Translator Architecture

This document provides a detailed overview of `quantum_translate.py`, the module
responsible for rewriting the classical MLIR produced by `mlir_generator.py`
into operations of the custom quantum dialect defined in
`quantum_dialect.py`.  The translator forms the central step that bridges the
classical compilation pipeline with the subsequent quantum circuit generation.

## Position in the Compilation Flow

The high level pipeline implemented in `pipeline.py` performs the following
stages:

1. **AST Parsing** – The C sources located under `c_code/` are converted to a
   JSON representation by Clang.  `c_ast.py` parses this JSON into a light–weight
   AST based on dataclasses.
2. **Classical Lowering** – `mlir_generator.py` lowers the dataclass AST to a
   classical MLIR module making use of the small custom dialect in
   `dialect_ops.py` for arithmetic with immediates.
3. **Quantum Translation** – `quantum_translate.py` walks the classical module
   and emits an equivalent module where each integer value lives in its own
   quantum register and arithmetic is replaced by quantum dialect operations.
4. **Circuit Generation** – `circuit_pipeline.py` interprets the quantum
   operations using the helpers in `q_arithmetics.py` and
   `q_arithmetics_controlled.py` to build an executable quantum circuit.

The translator is thus responsible for turning the SSA form produced by the
classical lowering into a form amenable to a quantum backend.  It takes care of
allocating registers, recomputing values when a register would be overwritten
and inserting control logic for conditional execution.

## Supported Source Operations

The front end currently recognises a small subset of C.  Expressions can contain
integer literals, variable references and binary arithmetic with either two SSA
operands or one immediate operand.  Comparison operators (`==`, `!=`, `<`, `<=`,
`>`, `>=`) are also handled.  Control flow is restricted to `if` statements and
`for` loops (which are unrolled by `mlir_generator.py`).  Only integer variables
of type `int` are considered.

The classical MLIR generated from this subset uses the following operations:

- `arith.constant` for integer constants.
- `arith.addi`, `arith.subi`, `arith.muli`, `arith.divsi` for binary arithmetic.
- Custom immediate variants `iarith.addi_imm`, `iarith.subi_imm`,
  `iarith.muli_imm`, `iarith.divsi_imm` from `dialect_ops.py`.
- `arith.cmpi` for comparisons returning `i1`.
- `cf.cond_br` for conditional control flow.

`quantum_translate.py` rewrites these into quantum-specific counterparts.

## Quantum Dialect Operations

The quantum dialect defined in `quantum_dialect.py` mirrors the classical
operations but acts on quantum registers.  The translator generates the
following operations:

- `quantum.init` / `quantum.c_init` – create a new register initialised to an
  integer value, optionally under a control bit.
- `quantum.addi`, `quantum.subi`, `quantum.muli`, `quantum.divsi` – binary
  arithmetic on two registers.
- `quantum.addi_imm`, `quantum.subi_imm`, `quantum.muli_imm`,
  `quantum.divsi_imm` – binary arithmetic where the right operand is an
  immediate integer.
- Controlled variants `quantum.c_addi`, `quantum.c_subi`, `quantum.c_muli`,
  `quantum.c_divsi` and their `_imm` forms which execute only when a control
  bit evaluates to one.
- `quantum.cmpi` – comparison producing an `i1` result.
- `quantum.and` – logical conjunction of two control bits.
- `quantum.not` – logical negation of a control bit.

Every integer value in the translated program is bound to exactly one register
identifier.  Registers are immutable: once written, a new register must be
allocated for updated values.  The translator keeps metadata describing for each
classical SSA value which register currently holds it, the version number of the
stored value and the expression that would recreate it if needed.

## Translation Algorithm

The `QuantumTranslator` class is initialised with the classical `ModuleOp`.  Its
`translate()` method computes use counts for all SSA values and then converts
each function individually.  A fresh quantum module is constructed and returned.
For every original operation the translator performs the following steps:

1. **Constant** – allocate a register and emit `quantum.init` (or the controlled
   variant when inside an `if` condition).  Metadata records the register number
   and that the value stems from a constant.
2. **Binary Arithmetic** – materialise the operands, allocating new registers if
   they were overwritten.  Emit the appropriate quantum operation (`quantum.addi`
   etc.) to produce a new register.  The expression description of the result is
   stored so it can be recomputed later.
3. **Immediate Arithmetic** – handled similarly using the `_imm` operations.
4. **Comparison** – operands are materialised and `quantum.cmpi` generates a new
   `i1` register representing the boolean result.
5. **Conditional Branch** – the branch condition is emitted and pushed onto a
   control stack.  Operations inside the `then` block inherit this control bit.
   For the `else` block the condition is inverted with `quantum.not` and pushed
   as the active control.  Nested `if` statements combine multiple controls using
   `quantum.and`.
6. **Return** – the returned value is materialised and a standard `func.return`
   is emitted in the quantum module.

Whenever a value needs to be used but its original register was overwritten, the
translator consults the stored expression description and *recomputes* the value
by emitting the same operations again on fresh registers.  A small cost model
estimates whether recomputation is cheaper than keeping additional registers
alive.

### Register and Version Tracking

- Each allocated register has a monotonically increasing version counter.
- `val_info` maps SSA values to the register and version storing them.
- `reg_ssa` tracks the current SSA value representing the contents of each
  register in the quantum module.
- When an expression is recomputed, a new register is allocated and all metadata
  is updated to point to this fresh location.

This scheme guarantees that registers are never implicitly copied: every update
creates new state and obsolete values can be recomputed on demand.

## Limitations and Assumptions

- Only integer operations are supported; floating point or pointer types are not
  handled.
- Control flow is restricted to `if` statements and simple `for` loops which are
  unrolled during lowering.
- The translator expects functions to consist of a single basic block after
  unrolling.  Complex control flow graphs are not yet handled.
- Quantum operations are emitted in a purely classical simulation manner:
  actual quantum circuit synthesis is performed later by
  `q_arithmetics.py`.
- Unary operators are parsed but currently not lowered nor translated.

Despite these constraints, the pipeline is sufficient to map small imperative C
fragments onto a sequence of quantum register manipulations while preserving the
semantics of the original program.
