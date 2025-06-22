# SSA DAG Construction

`ssa_dag.py` contains utilities for analysing the write-in-place IR by building a directed acyclic graph representing data dependencies. `QuantumIR.build_ssa_dag` exposes this functionality to pipeline users.

`build_dag(module)` scans the operations of the translated function, mapping every SSA value to a node. Edges capture value flow between operations so that the resulting `networkx` graph can be visualised or exported.

Two convenience helpers are provided:

* `visualize_dag(g, filename)` renders the DAG using GraphViz and saves a PNG image.
* `save_dag_dot(g, filename)` writes the graph in DOT format for further processing.

These functions are used by `pipeline.py` to produce diagrams of the quantum IR before and after applying additional constraints.
