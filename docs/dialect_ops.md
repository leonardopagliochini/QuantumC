# Immediate Arithmetic Dialect

This document describes the implementation of `dialect_ops.py`, which defines a
set of custom MLIR operations used throughout the compiler pipeline.  The file
implements arithmetic operations that accept an immediate operand as a property
rather than as a regular SSA value.  Such ops are convenient for lowering
constant expressions because they avoid the need for separate `arith.constant`
operations.

`dialect_ops.py` is part of the classical portion of the pipeline; it is used
by `mlir_generator.py` when translating the internal C AST into MLIR.  The
resulting operations are later interpreted by the tests and form the starting
point for the quantum translation implemented in `quantum_translate.py`.

## Rationale and Theoretical Background

MLIR's standard `arith` dialect expects both operands of a binary operation to
be SSA values.  When one side is a constant, a preceding `arith.constant` must
produce it.  This repository instead defines *immediate* versions of addition,
subtraction, multiplication, and signed division.  Each operation stores the
constant as an `IntegerAttr` property.  This mirrors assembly-level immediates
found in classical ISAs and keeps the IR concise.

The operations are defined using xDSL's IRDL API, which closely resembles
MLIR's ODS.  Every op declares its operands, results, properties and traits, and
provides custom parsing/printing logic.  All arithmetic ops are purely
functional (they have the `Pure` trait) and match either signless integers or
indices via the shared `signlessIntegerLike` type matcher.

A second base class adds optional overflow semantics via the
`IntegerOverflowAttr` property.  This matches MLIR's behaviour for the
`arith.addi` and similar ops where the overflow behaviour can be `none`, `wrap`
or `saturate`.

## Operation Semantics and Constraints

### Base Classes

```
class SignlessIntegerBinaryOpWithImmediate(IRDLOperation)
```
* Operands: one SSA value of type `T`.
* Result : one SSA value of type `T`.
* Property `imm` : `IntegerAttr` of the same type as the operand.
* Verifies that `imm`'s type matches `lhs`.
* Provides helper methods `py_operation`, `is_right_zero` and `is_right_unit`
  used by tests and optimisations.

```
class SignlessIntegerBinaryOpWithImmediateAndOverflow(...)
```
* Extends the previous base class with the property `overflowFlags` of type
  `IntegerOverflowAttr` (defaults to `"none"`).
* Parsing accepts an optional `overflow[...]` suffix, mirroring MLIR syntax.

### Concrete Arithmetic Operations

| Operation class | MLIR name          | Python semantics            |
|-----------------|--------------------|-----------------------------|
| `AddiImmOp`     | `iarith.addi_imm`  | `lhs + imm`                 |
| `SubiImmOp`     | `iarith.subi_imm`  | `lhs - imm`                 |
| `MuliImmOp`     | `iarith.muli_imm`  | `lhs * imm`                 |
| `DivSImmOp`     | `iarith.divsi_imm` | `lhs // imm` or `None` when dividing by zero |

All four operations inherit overflow support.  Each also overrides
`is_right_zero` and `is_right_unit` to indicate whether the immediate acts as a
mathematical identity element (e.g. zero for addition, one for multiplication).
These helpers enable small algebraic simplifications when lowering or
interpreting the IR.

### Control‑flow Operations

The module further defines simplified versions of `cf.br` and `cf.cond_br` used
by the MLIR generator:

```
class BranchOp(IRDLOperation)
```
* Successor: one target block.

```
class CondBranchOp(IRDLOperation)
```
* Operand `cond` : `i1`.
* Successors: `true_dest` and `false_dest` blocks.

These mirror the control‑flow dialect to keep the dependency footprint small
when running tests.

## Practical Usage in the Pipeline

During lowering from the custom C AST, `mlir_generator.py` emits these
immediate operations whenever a binary operator has a literal operand.  For
example, the expression `x + 3` becomes `iarith.addi_imm %x, 3`.  When both sides
are variables, the standard `arith` dialect ops are used instead.

The quantum translation phase (`quantum_translate.py`) later replaces the
immediate arithmetic ops with equivalent operations from `quantum_dialect.py`
that operate on quantum registers.  Having immediate forms greatly simplifies
this replacement because the translator only needs to update the operation name
while keeping the constant property intact.

In the test suite (`test_mlir_equivalence_to_fix.py`) each operation provides a
`py_operation` method so that the interpreter can execute the classical and
quantum IR and compare results.

## Supported C Subset

The overall compiler currently recognises a minimal subset of C constructs:

* Integer constants and variables of 32‑bit signless type.
* Binary arithmetic operators `+`, `-`, `*`, and `/` with optional constant
  operand (mapped to the immediate ops described above).
* Comparison operators `==`, `!=`, `<`, `<=`, `>`, `>=`.
* Unary operators including `+`, `-`, `++`, `--`, `!` and `~`.
* Variable declarations and assignments.
* Structured control flow via `if` statements and `for` loops.
* Functions returning a single integer value.

This subset is sufficient to express the small examples under `c_code/` and to
exercise the quantum translation workflow.

## Relation to the Rest of the Project

`dialect_ops.py` bridges the gap between the classical MLIR representation and
the custom quantum dialect.  By providing immediate variants, it keeps the IR
compact and allows the later stages to reason about constant operands easily.
The operations integrate with xDSL's verification and parsing infrastructure,
ensuring that malformed IR is detected early during tests.  They also serve as a
reference implementation for how new dialect operations can be defined using the
IRDL API.