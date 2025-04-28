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
-
