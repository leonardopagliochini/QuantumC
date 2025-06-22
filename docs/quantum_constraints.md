# Quantum Constraint Enforcement

After constructing the SSA DAG it is often useful to rewrite the IR so that every register is used in a quantum friendly way. The function `enforce_constraints` in `ssa_dag.py` clones operations to satisfy two additional rules:

1. A value may not be overwritten before all of its uses have executed.
2. When both operands of a binary operation refer to the same register version, the right operand is duplicated to respect the no-cloning rule.

`QuantumIR.run_enforce_quantum_constraints` applies this transformation to the write-in-place module and updates the paths DataFrame and DAG. The resulting IR can be visualised with the same helpers used for the initial graph.
