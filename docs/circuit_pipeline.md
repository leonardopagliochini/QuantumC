# QuantumCircuitPipeline

This document provides an in depth overview of `circuit_pipeline.py` and how it integrates with the rest of the repository.  The description is based on the current implementation found in `circuit_pipeline.py` and related modules.

## Position within the compilation flow

`QuantumCircuitPipeline` extends the core pipeline implemented in `pipeline.py`.  The high level steps of the entire toolchain are:

1. **AST generation** – `astJsonGen` invokes Clang to produce a JSON representation of C source files.
2. **Dataclass parsing** – `QuantumIR.run_dataclass()` converts the JSON AST into the lightweight classes defined in `c_ast.py`.
3. **MLIR generation** – `QuantumIR.run_generate_ir()` lowers those dataclasses to classical MLIR via `mlir_generator.py`.
4. **Quantum translation** – `QuantumIR.run_generate_quantum_ir()` translates the classical MLIR into the custom quantum dialect using `quantum_translate.py`.
5. **Circuit construction** – `QuantumCircuitPipeline.run_generate_circuit()` interprets the quantum dialect with helpers from `q_arithmetics.py` and `q_arithmetics_controlled.py` in order to build a `QuantumCircuit` object.
6. **QASM export** – `QuantumCircuitPipeline.export_qasm()` writes the circuit to an OpenQASM 2.0 file.

Steps 1–4 correspond to the classical pipeline documented in `README.md`.  `QuantumCircuitPipeline` adds steps 5 and 6, turning the quantum dialect into an executable circuit.

## Overview of `QuantumCircuitPipeline`

```python
class QuantumCircuitPipeline(QuantumIR):
    def __init__(self, json_path="json_out/try.json", output_dir="output", num_bits=16, verbose=False):
        ...
```

The class inherits from `QuantumIR` in order to reuse all front end phases.  The constructor selects the input JSON file, an output directory and how many bits are used by the arithmetic helpers.  `num_bits` configures the two's complement width employed by `q_arithmetics`.  The optional `verbose` flag prints every interpreted operation when generating the circuit.

### Generating the circuit

`run_generate_circuit()` assumes that `run_generate_quantum_ir()` was executed and iterates over the quantum MLIR module.  It instantiates a fresh `QuantumCircuit` and maps each quantum dialect operation to one or more Qiskit calls:

* **Initialization** – `QuantumInitOp` and `QuantumCInitOp` allocate new registers.  Controlled initialisation uses `initialize_variable_controlled` from `q_arithmetics_controlled.py`.
* **Binary arithmetic** – `QAddiOp`, `QSubiOp`, `QMuliOp`, `QDivSOp` correspond to addition, subtraction, multiplication and signed division on registers.  The helpers in `q_arithmetics.py` implement these operations using QFT based routines.
* **Binary with immediate** – `QAddiImmOp`, `QSubiImmOp`, `QMuliImmOp`, `QDivSImmOp` operate with a classical constant.  The respective `*_imm` helpers perform the arithmetic using phase rotations.
* **Controlled variants** – `CQAddiOp`, `CQSubiOp`, `CQMuliOp`, `CQDivSOp` and the immediate forms are executed only when the control qubit evaluates to `|1⟩`.  They delegate to functions in `q_arithmetics_controlled.py`.
* **Comparisons and logic** – `QCmpiOp` produces an `i1` result implementing equality/inequality and relational comparisons.  `QAndOp` and `QNotOp` realise logical conjunction and negation.
* **Return** – `func.return` operations cause measurement of the returned register.  Duplicate measurements are skipped when the circuit already contains a classical register for the same qubits.

Each generated quantum register is stored in a dictionary `reg_map` keyed by the SSA value corresponding to that register.  Operations read from this map and insert the produced register back.

The procedure terminates by storing the constructed `QuantumCircuit` in `self.circuit`.

### Exporting as QASM

`export_qasm()` serialises the circuit to OpenQASM 2.0.  Before writing, the method calls Qiskit's `transpile` with the gate set `"u1", "u2", "u3", "cx", "id", "measure", "reset"` to guarantee compatibility with the QASM format.  The path of the written file is returned for convenience.

## Supported C subset

The current front end accepts a restricted subset of C which is converted into MLIR by `mlir_generator.py` and subsequently into the quantum dialect.  Supported constructs include:

* **Integer variables** declared with optional initialisers.
* **Assignments** of expressions to variables.
* **Integer constants** and variable references.
* **Binary arithmetic**: `+`, `-`, `*`, `/`.
* **Binary comparisons**: `==`, `!=`, `<`, `<=`, `>`, `>=`.
* **Binary arithmetic with one immediate** (e.g. `x + 5`).
* **If statements** with arbitrary nesting.  Conditions containing `&&` or `||` are rewritten into nested `if` constructs during lowering.
* **For loops** with initialisation, condition and increment expressions.  Loops are statically unrolled up to `MAX_UNROLL = 10` iterations.
* **Return statements** returning an integer expression.

Only straight–line integer computations are handled—pointers, arrays, floating point operations and function calls are outside the implemented subset.  The generator creates single functions that operate on 32‑bit integers mapped to the MLIR `i32` type.

## Constraints and limitations

* Each C function is lowered into a single MLIR `func` with one basic block; control flow constructs become `cf.cond_br` operations with explicit successor blocks.
* Division by zero in immediate form is checked and raises a Python exception during circuit generation.
* Quantum registers are allocated eagerly when their values are first produced.  The translator tracks register versions to recompute values if a register is reused.
* The `QuantumCircuitPipeline` expects Qiskit to be available.  Some optional dependencies such as `qiskit_aer` are used when present but are not mandatory for correctness.

## Conclusion

`circuit_pipeline.py` bridges the gap between the quantum MLIR dialect and executable quantum circuits.  By interpreting each dialect operation with carefully crafted Qiskit routines the module allows programs written in a small subset of C to be automatically compiled into OpenQASM.  The pipeline is fully deterministic and exposes explicit hooks for each compilation stage, making it suitable for experimentation with new optimisations or quantum arithmetic primitives.