# `q_arithmetics_controlled.py`

This document describes the implementation of `q_arithmetics_controlled.py` and how it integrates within the experimental C–to–quantum compiler contained in this repository.

## Overview

The project converts small C programs into MLIR and then to a custom quantum dialect before finally producing Qiskit circuits. The high level workflow is outlined in the repository README and further detailed in the documentation referenced there. `q_arithmetics_controlled.py` provides controlled versions of the arithmetic primitives used by the pipeline when constructing circuits from the quantum dialect. These primitives implement a subset of C arithmetic: addition, subtraction, multiplication and division of signed or unsigned integers.

## Two's Complement Representation

All operations assume fixed width two's complement representation controlled by the module level variable `NUMBER_OF_BITS`. The helper `int_to_twos_complement` converts Python integers into their two's complement bit strings. Registers are always allocated with exactly `NUMBER_OF_BITS` qubits.

## Conditional Register Initialisation

```python
initialize_variable_controlled(qc, value, control, register_name=None)
```
Lines 17–58 define this routine. It allocates a new quantum register and conditionally prepares it to hold `value` depending on the state of `control`. The constant range is validated against `NUMBER_OF_BITS`, a unique name is generated if required, and controlled `X` gates are applied only if a bit of the classical value is `1`【F:q_arithmetics_controlled.py†L17-L58】.

## Conversion between Sign Encodings

Two helper routines manage conversions between two's complement and sign‑magnitude encodings:

```python
sign_magnitude_to_twos(qc, qreg, sign_reg, control=None)
```
```python
twos_to_sign_magnitude(qc, qreg)
```

Lines 62–87 implement the first function which conditionally flips all bits controlled by `sign_reg` and adds one in place if the sign is negative. The operation may itself be conditioned by an additional `control` qubit. Lines 89–105 implement the second function which copies the sign bit out of a register, performs the inverse transformation and returns a new one‑qubit register holding the sign【F:q_arithmetics_controlled.py†L62-L106】.

These conversions are essential to perform signed divisions because the implemented QFT based divider works on magnitudes.

## Controlled Addition

```python
add_in_place_controlled(qc, a_reg, b_reg, control)
```
```python
add_controlled(qc, a_reg, b_reg, control)
```
```python
addi_in_place_controlled(qc, qreg, b, control)
```
```python
addi_controlled(qc, a_reg, b, control)
```

Lines 131–193 implement a family of controlled adders. The design mirrors the uncontrolled version from `q_arithmetics.py` but every phase rotation is wrapped inside a multi‑controlled `PhaseGate`. Both registers must have equal length and the addition is applied only when the control qubit is `|1⟩`. For constant addition, the classical integer is first converted to two's complement bits and encoded as phases【F:q_arithmetics_controlled.py†L131-L193】.

## Controlled Negation and Subtraction

Negating a register is done by bitwise NOT followed by adding one, all conditioned on a control qubit:

```python
invert_controlled(qc, qreg, control)
```

Subtraction is then implemented by negating the second operand and invoking the adder:

```python
sub_controlled(qc, a_reg, b_reg, control)
```
```python
subi_controlled(qc, a_reg, b, control)
```

Lines 195–208 implement these transformations, ensuring the input operand is restored afterwards for reuse in further computations【F:q_arithmetics_controlled.py†L195-L208】.

## Controlled Multiplication

```python
mul_controlled(qc, a_reg, b_reg, control)
```
```python
muli_controlled(qc, a_reg, c, control, n_output_bits=None)
```

The code uses a QFT based Fourier multiplier. Lines 210–249 allocate an output register, apply the QFT and then rotate with phases dependent on all combinations of bits from the multiplicands. For constant factors, the phases depend only on the absolute value of the scalar and a final conditional sign inversion is applied when the constant is negative. The optional `n_output_bits` parameter allows for truncation or extension of the output register size【F:q_arithmetics_controlled.py†L210-L249】.

## Controlled Division

Division is available in both unsigned and signed form:

```python
divu_controlled(qc, a_reg, b_reg, control, n_output_bits=None)
```
```python
div_controlled(qc, a_reg, b_reg, control, n_output_bits=None)
```
```python
divi_controlled(qc, a_reg, divisor, control, n_output_bits=None)
```

Lines 251–370 implement these routines. The unsigned version uses repeated conditional subtraction and controlled addition to produce the quotient and remainder registers. The signed variant first extracts sign bits with `twos_to_sign_magnitude`, performs the unsigned division and then conditionally restores two's complement signs. `divi_controlled` is a helper that divides by a classical integer, initialising a constant register on demand. The implementation guards against division by zero and names all ancillary registers uniquely to avoid clashes【F:q_arithmetics_controlled.py†L251-L370】.

## Private Helper `_sub_in_place`

A local helper `_sub_in_place` performs subtraction using the inverse adder. It accepts an optional control and is used during the division routines to compute partial remainders in place【F:q_arithmetics_controlled.py†L318-L336】.

## Integration in the Pipeline

The compiler pipeline described in the main README converts C code to classical MLIR and then to the custom quantum dialect. During circuit generation (`circuit_pipeline.py`) the translation layer uses functions from `q_arithmetics.py` for standard operations and from `q_arithmetics_controlled.py` when conditional execution is required—for example inside translated `if` statements or conditional assignments.

## Supported C Operations

Within the current prototype, the following arithmetic operations on integers are available in controlled form:

- Addition (`+`) and subtraction (`-`), including constant variants.
- Multiplication (`*`) with either variable or constant operands.
- Division (`/`) in signed and unsigned form. Division by a constant is supported through `divi_controlled`.

All operations assume a fixed bit width (`NUMBER_OF_BITS`) and operate on registers of equal size. When intermediate registers are needed (e.g., for storing a product or quotient) the routines allocate fresh registers with automatically generated names.

## Constraints and Features

- **Fixed width:** the entire arithmetic library works with a global number of bits; overflow is implicitly modulo \(2^{\text{NUMBER\_OF\_BITS}}\).
- **Quantum Fourier Transform based:** addition and multiplication rely on the QFT and its inverse, resulting in circuits dominated by phase rotations and controlled additions.
- **Conditional execution:** every function accepts a dedicated control qubit. Operations act only when this qubit is `|1⟩`, leaving registers unchanged otherwise.
- **Ancilla management:** helper registers for signs or temporary results are automatically allocated with unique names to avoid collisions inside larger circuits.
- **Two's complement semantics:** signed operations convert to and from sign‑magnitude form to implement negation and signed division correctly.

## Relation to the Overall Project

The repository README positions this module as part of the quantum circuit generation stage. After the compiler emits the quantum dialect, `circuit_pipeline.py` interprets those dialect operations and uses these controlled primitives to build conditional arithmetic segments of the final `QuantumCircuit`. The README highlights the documentation folder for additional context on the code structure and compilation process【F:README.md†L80-L89】.

`q_arithmetics_controlled.py` therefore bridges the abstract quantum dialect with concrete Qiskit implementations, enabling the compiler to represent conditional arithmetic exactly and paving the way for further optimisations and experiments.