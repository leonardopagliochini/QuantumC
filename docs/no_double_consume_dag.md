# No Double Consume DAG

`IRDependencyDAG.duplicate_double_consumers` rewrites the classical dependency graph so that an operation never consumes the same register twice. When a consumer uses the same SSA value for both operands, its producer is cloned into two copies. The copies inherit all incoming edges of the original node and their result names receive `'` and `"` suffixes. The consumer is then updated to depend on the new results.

The resulting graph is stored as `output/no_double_consume_dag.*` by `QuantumIR.build_no_double_consume_dag`.
