# IR Dependency DAG

`dag_builder.py` constructs a dependency graph from the classical MLIR produced by the pipeline. Nodes correspond to operations and edges connect each producer to the operations that consume its SSA values. The labels show each operation in SSA form using arithmetic symbols (for example `%2 = %0 + %1`), but also c-like representation using variable names of original code (e.g. c = a + b). 

If an operation reads the same value multiple times, parallel edges are emitted: two edges from producer to consumer.

Running the CLI will automatically generate `output/classical_ir_dag.png` and `output/classical_ir_dag.xdot` after the MLIR is produced. A second graph named `output/no_double_consume_dag.*` shows the version where duplicated operands are split. Both can be inspected with standard Graphviz tools.
