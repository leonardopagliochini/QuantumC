# Pipeline Overview

The project translates small C programs to a quantum-inspired MLIR dialect in several stages.  The main driver is `pipeline.py` which exposes a `QuantumIR` class.  The typical workflow is:

1. **AST Generation** – `generate_ast.py` produces JSON ASTs.
2. **AST Parsing** – `QuantumIR.run_dataclass` parses the JSON into dataclasses defined in `c_ast.py`.
3. **Classical MLIR Generation** – `QuantumIR.run_generate_ir` uses `MLIRGenerator` to lower the dataclasses to standard MLIR.
4. **Write-in-Place Enforcement** – `QuantumIR.run_enforce_write_in_place` calls `QuantumTranslator` to rewrite the MLIR using the quantum dialect while enforcing in-place updates.
5. **Visualization** – helper methods print both the classical and write-in-place modules using a custom printer.
6. **Path DataFrame** – `paths_dataframe.build_paths_dataframe` constructs a pandas table of register usage which is stored on `QuantumIR.paths_df`.  The DataFrame features an `operation` column describing the expression executed at each timestep. `QuantumIR.visualize_paths_dataframe` prints this table.
7. **SSA DAG Construction** – `QuantumIR.build_ssa_dag` uses utilities in `ssa_dag.py` to create a dependency graph of the write-in-place IR. `visualize_dag` and `save_dag_dot` can render or export this graph.
8. **Quantum Constraint Enforcement** – `QuantumIR.run_enforce_quantum_constraints` applies additional rewriting on the DAG using `enforce_constraints` so that registers obey quantum-friendly usage rules.

Each step can be invoked individually when experimenting with the compiler.
