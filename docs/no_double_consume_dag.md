# No Double Consume DAG

The classical dependency DAG mirrors the MLIR produced by the compiler. In some cases an operation consumes the same SSA register twice. Such a situation cannot be implemented directly by the hardware, so the pipeline offers a second pass that expands the DAG.

`QuantumIR.build_no_double_consume_dag` calls `IRDependencyDAG.duplicate_double_consumes` which clones any producer whose result is used twice by the same non-immediate consumer. The two clones inherit all incoming dependencies and each provides one value to the consumer. The resulting graph is written to `output/no_double_consume_dag.*`.
