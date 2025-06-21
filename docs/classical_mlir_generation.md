# Classical MLIR Generation

`mlir_generator.py` contains class `MLIRGenerator` which converts the dataclass representation of the program into standard MLIR using the xDSL API.  Each AST node has a corresponding `generate_*` method that emits the appropriate operations.

Arithmetic operations with constant immediates are represented using helper ops from `dialect_ops.py`.  The resulting `ModuleOp` contains functions that mirror the original C functions but operate entirely on integers.

`QuantumIR.run_generate_ir` orchestrates this step and stores the classical MLIR module for later comparison with the write-in-place version.
