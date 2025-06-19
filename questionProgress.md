# Q&P

## General Info
- **Ancillary qbit**: a qbit that needs to be used not because is part of the representation of the actual operation you want to make, but for **temporary sub-operations**. It's a logical qbit, this has not to do with physical-qbit redundancy. Usually best practice is to find gate representation that avoid the necessity for ancillary qbits. 

## Operations to implement

### Risc-V ISA (no branching)
Every load/store op should not be considered, no branching (jumps) for now.
No immediate operations either, there is no encoding of instructions, there are no instructions in QC...

Integer Operations
- `ADD`
- `SUB`
- `XOR`
- `OR`
- `AND`
- `MUL`
- `DIV`
- `REM`

Note: in standard-computing you have different possible precisions, this might hold true only in a _bit->qbit_ translation, which we'll try to avoid. Working in phase I have no idea of what is the possible precision.



### Risc-V ISA (add branching)
### Risc-V ISA (add floating-point ops)

## Papers
### Operations
#### Survey-paper





### Quantum Constraints for Fake Quantum Assembly

*Below is a concise list of constraints applied during quantumization, along with clarifications on when they are valid in quantum computing contexts.*

---

*1. In-Place Immediate Operations*

- Format: `OPI dst, src, imm`
- Constraint: Must **overwrite the source** in-place.
- Valid: ✅ For known classical values (e.g., initialized with `LI`).
- Not Valid: ❌ If `src` is a general quantum state.

---

*2. Register-Register Binary Operations*

- Format: `OP dst, src1, src2`
- Constraint: Must **overwrite `src2`**.
- Valid: ✅ Only if `src2` is no longer needed or can be recomputed.
- Not Valid: ❌ If `src2` holds a quantum state needed later.

---

*3. No Fan-Out (Register Reuse)*

- Constraint: You **cannot use the same quantum register in multiple branches** unless you:
  - a) Overwrite it,
  - b) Uncompute it,
  - c) Recompute it from scratch.
- Valid: ✅ If register is classical or re-creatable.
- Not Valid: ❌ For unknown superpositions.

---

*4. No Cloning of Quantum Registers*

- Constraint: `MOV dst, src` is only valid if:
  - a) `src` is classical (e.g., after `LI`, or measurement),
  - b) `src` can be **recomputed** from its generating operations.
- Valid: ✅ For classical values or recomputation.
- Not Valid: ❌ For arbitrary quantum states (violates no-cloning theorem).

---

*5. Register Copying Before Overwrite*

- Pattern:
  ```
  MOV qr9, qr3         ; only valid if qr3 is classical or reconstructible
  ADD qr9, qr2, qr9    ; qr3 is preserved via qr9
  ```
- Valid: ✅ Only when `qr3` is classical or reconstructible.
- Not Valid: ❌ When `qr3` is a general quantum state.

---

*6. Irreversibility of Destructive Writes*

- Constraint: Once a quantum register is overwritten, its prior state is lost unless:
  - It was copied (if classical),
  - Or can be recomputed via gate history.
- Implication: Design must avoid destructive updates unless data is dispensable.

---

*7. No Arbitrary Swaps Without Tracking*

- Constraint: Any change in data routing (e.g., "moving" values) must be logically reversible or tracked via swap gates.
- Valid: ✅ If swaps are gate-based and reversible.
- Not Valid: ❌ Arbitrary reassignments with no physical meaning.

---

*8. All Operations Must Be Unitary or Classical*

- Constraint: Every transformation must be:
  - A unitary operation on quantum data, or
  - A classical deterministic operation on known inputs.
- Valid: ✅ For logic that can be mapped to gates.
- Not Valid: ❌ For irreversible computations on quantum states.




### Pipeline of application
1. Take the C code and parse it --> bring it to MLIR dialect
2. The MLIR is unique but basically comprehends two things:
    - normal MLIR representation of the C code, not compliant with Quantum constraints
    - some additional operations that only makes sense to comply with Quantum Constraints
3. Initally the parsed code is in "classic" version only
4. Then is processed in order to comply with Quantum constraints: this also requires to employ the additional operations
5. Final MLIR should be connectable to previous work  (I don't recall if there is an intermediate step to some QMLIR before connecting to qskit)
6. Optimization of the MLIR (optional) can be done on MLIR diredctly using work of last year bros


