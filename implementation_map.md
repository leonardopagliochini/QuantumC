# Mapping Research Papers to Implementation

This document summarises how material from the papers under `Readings_all/` was used in the repository. Each section quotes passages from the papers and links them to relevant implementation snippets or documentation. A table at the end provides a quick reference between paper sections and code locations.

## 1. *A MLIR Dialect for Quantum Assembly Languages*

Quoted text:
> "extend MLIR with a new quantum dialect ... lowered to the LLVM intermediate representation ... adherent to the quantum intermediate representation (QIR) specification"【9a3dd3†L1-L15】

Implementation connection:
- The custom quantum dialect defined in `quantum_dialect.py` mirrors this idea. The `QuantumInitOp` class starts the dialect and stores the initial value as a property【F:quantum_dialect.py†L55-L74】. Immediate binary operations such as `QAddiImmOp` follow MLIR conventions for properties and parsing【F:quantum_dialect.py†L144-L210】.

## 2. *QIRO: A Static Single Assignment-based Quantum Program Representation for Optimization*

Quoted text:
> "QIRO ... uses value-semantics (operations consume and produce states) to integrate quantum dataflow in the IR’s Static Single Assignment (SSA) graph"【e5239e†L4-L17】

Implementation connection:
- `quantum_translate.py` allocates a fresh register for each SSA value and recomputes overwritten values to maintain SSA-style semantics【F:quantum_translate.py†L24-L61】. This mirrors the value-based dataflow described in the paper.

## 3. *Enabling Dataflow Optimization for Quantum Programs*

Quoted text:
> "encode the dataflow directly in the IR, allowing for a host of optimizations"【a307b3†L3-L15】

Implementation connection:
- `mlir_generator.py` produces MLIR with explicit SSA values and `cond_br` operations, enabling later transformations to analyse dataflow. For example, the `lower_if` method creates new blocks and branches explicitly【F:mlir_generator.py†L96-L128】.

## 4. *Implementing an Intermediate Representation for Quantum Computing based on MLIR*

Quoted text:
> "we present and implement an IR in MLIR that is optimized for quantum computing"【8a3a36†L1-L13】

Implementation connection:
- The repository’s pipeline uses xDSL (a Python MLIR analogue) to construct an intermediate representation. The `MLIRGenerator` class builds MLIR functions and regions directly in Python【F:mlir_generator.py†L198-L206】.

## 5. *Quantum Intermediate Representation (QuantumIR.pdf)*

Quoted text:
> "create a bridge between classical and quantum circuits through the creation of an intermediate representation"【40e9e8†L15-L23】

Implementation connection:
- The high-level compiler described in `README.md` mirrors this approach. The pipeline converts C into MLIR and then into the custom quantum dialect before circuit generation【F:README.md†L60-L94】.

## 6. *Integer Numeric Multiplication Using Quantum Fourier Transform*

Quoted text:
> "The arithmetic calculation is carried out using the QFT ... quantum multiplication"【0ec78d†L7-L30】

Implementation connection:
- `q_arithmetics.py` implements multiplication via a QFT-based algorithm. The `mul` function applies a QFT, performs controlled–controlled phase rotations and then the inverse QFT【F:q_arithmetics.py†L323-L358】.

## 7. *Quantum Circuit Designs of Integer Division Optimizing T-count and T-depth*

Quoted text:
> "The restoring division algorithm is illustrated by Algorithm 1 ... quantum register jQi will have the quotient"【47a1aa†L8-L24】

Implementation connection:
- Division routines such as `divu` implement the restoring division algorithm exactly. They shift the remainder, subtract the divisor and conditionally restore it【F:q_arithmetics.py†L408-L472】.

## 8. *Floating Point Representations in Quantum Circuit Synthesis*

Quoted text:
> "construct the exponent part of the rotation and ... combine it with a mantissa. This causes the cost of the synthesis to depend more strongly on the relative precision"【df5f87†L1-L17】

Implementation connection:
- Several helpers in `q_arithmetics.py` perform arithmetic via phase rotations whose angles depend on the binary expansion of constants (e.g. `addi_in_place`). This is directly inspired by the floating‑point rotation synthesis techniques.

## 9. *Quantum Arithmetic Circuits: A Survey*

Quoted text:
> "Quantum circuits for elementary arithmetic operations ... covers addition, comparison, and the quantum Fourier transform used for addition"【f79441†L9-L19】

Implementation connection:
- The arithmetic helpers implement exactly these operations. `q_arithmetics.md` documents QFT-based addition and restoring division and lists the comparison predicates supported【F:docs/q_arithmetics.md†L26-L55】.

## 10. *Towards High-Level Synthesis of Quantum Circuits* (DATE23_quantum_hls)

Quoted text:
> "Towards High-Level Synthesis of Quantum Circuits"【e01bd7†L1-L11】

Implementation connection:
- The overall repository functions as a simple high-level synthesis pipeline from C programs to quantum circuits, realised by `circuit_pipeline.py` and associated modules.【F:circuit_pipeline.py†L1-L56】

## Table: Paper Sections to Implementation

| Paper Section | Implementation Reference |
| --- | --- |
| MLIR quantum dialect adherent to QIR【9a3dd3†L1-L15】 | Quantum dialect definitions in `quantum_dialect.py`【F:quantum_dialect.py†L55-L74】 |
| SSA-based dataflow【e5239e†L4-L17】 | Register tracking in `quantum_translate.py`【F:quantum_translate.py†L24-L61】 |
| Dataflow in IR for optimisation【a307b3†L3-L15】 | `lower_if` explicit blocks in `mlir_generator.py`【F:mlir_generator.py†L96-L128】 |
| MLIR-based quantum IR design【8a3a36†L1-L13】 | `MLIRGenerator.generate_function` setup【F:mlir_generator.py†L198-L206】 |
| Bridge classical and quantum IR【40e9e8†L15-L23】 | Pipeline stages summarised in `README.md`【F:README.md†L60-L94】 |
| QFT multiplication approach【0ec78d†L7-L30】 | `mul` QFT algorithm in `q_arithmetics.py`【F:q_arithmetics.py†L323-L358】 |
| Restoring division algorithm【47a1aa†L8-L24】 | `divu` restoring division implementation【F:q_arithmetics.py†L408-L472】 |
| Floating-point rotation synthesis【df5f87†L1-L17】 | Phase-based immediate arithmetic in `q_arithmetics.py`【F:q_arithmetics.py†L161-L176】 |
| Survey of arithmetic circuits【f79441†L9-L19】 | Overview of arithmetic helpers【F:docs/q_arithmetics.md†L26-L55】 |
| High-level synthesis concepts【e01bd7†L1-L11】 | Compilation pipeline in `circuit_pipeline.py`【F:circuit_pipeline.py†L1-L56】 |
