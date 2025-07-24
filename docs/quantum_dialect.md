# Quantum Dialect Overview

This document describes the `quantum_dialect.py` module in detail and explains how it integrates with the overall compilation pipeline documented in [README](../README.md).  The aim is to provide a thorough explanation of every operation defined in the dialect and how these operations are used when translating a subset of the C language to a quantum representation.

## Role in the Pipeline

The repository implements a toy compiler that converts simple C programs into MLIR and finally into a custom *quantum* dialect.  The high level flow is:

1. **Generate AST:** `generate_ast.py` invokes Clang to dump a JSON representation of the C source.
2. **Lower to MLIR:** `pipeline.py` parses the JSON into dataclasses (see `c_ast.py`) and lowers them to classical MLIR using `mlir_generator.py`.
3. **Translate to quantum MLIR:** `quantum_translate.py` walks over that MLIR and replaces arithmetic and control-flow constructs with operations from `quantum_dialect.py`.  All values are allocated to quantum registers and the translator keeps track of register versions and usage.
4. **Build circuits:** `circuit_pipeline.py` interprets the resulting quantum MLIR using the Qiskit helpers in `q_arithmetics.py` and `q_arithmetics_controlled.py` to produce an executable `QuantumCircuit`.

The quantum dialect therefore forms the bridge between a classical representation and the quantum circuit back-end.  Each operation encapsulates a quantum primitive that manipulates registers instead of plain integers while preserving the familiar structure of the original code.  By mirroring the classical arithmetic dialect, the translator can lower standard arithmetic instructions directly to their quantum counterparts.

## Available C Subset

Only a restricted portion of C is currently supported by the front-end:

* Integer variables and assignments
* Binary arithmetic operations (`+`, `-`, `*`, `/`)
* Comparisons (`==`, `!=`, `<`, `<=`, `>`, `>=`)
* Unary operators such as logical and arithmetic negation
* `if` statements and `for` loops (without break or continue)
* Integer constants may appear directly as operands (immediates)
* Return statements from a single function

The tests under `c_code/` exercise mainly arithmetic expressions and simple loops.  This minimal subset is sufficient to demonstrate the translation to quantum MLIR without having to implement a full C front-end.

## Type System and Conventions

All arithmetic in the dialect operates on *signless* integer or index types as matched by the `signlessIntegerLike` constraint:

```python
signlessIntegerLike = AnyOf([IntegerType, IndexType])
```

Operations carry the `Pure` trait, meaning they have no side effects other than updating quantum registers.  Many operations also store immediate values as *properties* rather than as SSA operands to keep the IR concise.  Unless stated otherwise, results have the same type as their operands.

## Operation Reference

Below each operation is described in detail.  The line numbers refer to `quantum_dialect.py` for reference.

### `QuantumInitOp`
Creates and initializes a new quantum register with an integer value.  The value is stored as a property so that the SSA result represents the freshly allocated register.

```python
class QuantumInitOp(IRDLOperation):
    name = "quantum.init"            # lines 55–74
```

*Operands*: none.  
*Result*: a new register of type `T` (typically `i32`).  
*Properties*: `value` – an `IntegerAttr` giving the initial contents.

### `QuantumCInitOp`
Controlled version of `QuantumInitOp`.  The register is initialized only if the control bit is set.

```python
class QuantumCInitOp(IRDLOperation):
    name = "quantum.c_init"          # lines 303–326
```

*Operands*: control bit (`i1`).  
*Result*: new register of type `T`.  
*Attributes*: `value` – the integer constant.

### Binary Arithmetic Operations
The following four classes extend `QuantumBinaryBase` (lines 99–113) and model the standard arithmetic operators but acting on quantum registers:

* `QAddiOp`   – addition (`quantum.addi`, lines 116–121)
* `QSubiOp`   – subtraction (`quantum.subi`, lines 123–127)
* `QMuliOp`   – multiplication (`quantum.muli`, lines 129–134)
* `QDivSOp`   – signed division (`quantum.divsi`, lines 137–141)

Each takes two register operands (`lhs`, `rhs`) of the same type `T` and yields a result of type `T`.

### Immediate Binary Operations
Using `QuantumBinaryImmBase` (lines 144–183) the dialect also provides immediate forms where one operand is a constant integer.  The immediate is stored as a property called `imm`:

* `QAddiImmOp` – `quantum.addi_imm`  (lines 185–189)
* `QSubiImmOp` – `quantum.subi_imm`  (lines 192–196)
* `QMuliImmOp` – `quantum.muli_imm`  (lines 199–203)
* `QDivSImmOp` – `quantum.divsi_imm` (lines 206–210)

### Controlled Binary Operations
Many algorithms require executing an arithmetic instruction only when a control qubit is `1`.  `QuantumControlledBinaryBase` (lines 212–227) implements this pattern by accepting an extra `ctrl` operand.

Concrete controlled variants exist both for register-register operations and for immediate forms:

* `CQAddiOp`, `CQSubiOp`, `CQMuliOp`, `CQDivSOp` – register operands (lines 230–255)
* `CQAddiImmOp`, `CQSubiImmOp`, `CQMuliImmOp`, `CQDivSImmOp` – immediate operand (lines 328–349)

All controlled operations yield a new register holding the result while leaving the control bit unchanged.

### Logical and Comparison Operations

* `QAndOp` – logical AND of two `i1` control bits (lines 38–52).  This is used internally by the translator when combining nested `if`/`for` conditions.
* `QNotOp` – logical NOT on an `i1` value (lines 286–300).  Useful for negating conditions when translating `else` branches.
* `QCmpiOp` – comparison producing an `i1` result (lines 257–284).  The property `predicate` encodes the comparison kind using the same numeric values as `arith.cmpi` from MLIR.

## Interaction with `quantum_translate.py`

The translator allocates a fresh register for every SSA value in the original MLIR module.  Arithmetic operations such as `arith.addi` are mapped one-to-one to their quantum counterparts (`QAddiOp`, `QMuliOp`, etc.).  When an operation uses an immediate operand, the translator emits the `*_imm` variants so that the constant is embedded as a property rather than as a separate `quantum.init` instruction.  Control flow constructs (`cf.cond_br`) result in the creation of control bits via comparisons.  These control bits govern the emission of controlled operations (`CQAddiOp`, `QuantumCInitOp`, etc.) to faithfully replicate conditional execution.

Because registers are immutable once written, if an SSA value is overwritten the translator can recompute it from the stored expression description.  This bookkeeping is managed by `ValueInfo` records inside `QuantumTranslator` and ensures that only the minimal number of qubits are kept alive at any time.

## Summary

`quantum_dialect.py` defines a compact yet expressive collection of MLIR operations for manipulating quantum registers.  The dialect mirrors classical arithmetic while exposing explicit initialization and control semantics required by quantum algorithms.  Combined with the translation logic in `quantum_translate.py` and the circuit builders in `q_arithmetics.py`, these operations form the core of the repository's C‑to‑quantum compilation flow.
