# IR Dependency DAG

`dag_builder.py` constructs a dependency graph from the classical MLIR produced by the pipeline. Nodes correspond to operations and edges connect each producer to the operations that consume its SSA values.

Running the CLI will automatically generate `output/ir_dag.png` and `output/ir_dag.xdot` after the MLIR is produced. They can be inspected with standard Graphviz tools.
