# Pipeline Overview

The project translates small C programs to MLIR in several stages.  The main driver is `pipeline.py` which exposes a `QuantumIR` class.  The typical workflow is:

1. **AST Generation** – `generate_ast.py` produces JSON ASTs.
2. **AST Parsing** – `QuantumIR.run_dataclass` parses the JSON into dataclasses defined in `c_ast.py`.
3. **Classical MLIR Generation** – `QuantumIR.run_generate_ir` uses `MLIRGenerator` to lower the dataclasses to standard MLIR.
4. **Visualization** – helper methods print the generated MLIR using a custom printer.
5. **Classical DAG Extraction** – `QuantumIR.build_classical_ir_dag` writes a dependency graph of the operations. Nodes are labeled in SSA form using arithmetic symbols and repeated operands create parallel edges.
6. **No Double Consume DAG** – `QuantumIR.build_no_double_consume_dag` duplicates producers when an operation consumes the same register twice. The resulting DAG is written alongside the classical version.

Each step can be invoked individually when experimenting with the compiler.
