# AST to Dataclasses

`c_ast.py` defines a minimal set of dataclasses that model a subset of the Clang AST.  The function `parse_ast(obj: dict)` walks the JSON structure and instantiates these dataclasses to produce a tree rooted at `TranslationUnit`.

`QuantumIR.run_dataclass` loads the JSON and invokes `parse_ast`.  The pretty-printer `pretty_print_translation_unit` can then reconstruct a C-like source representation from the dataclass tree.

This intermediate form simplifies subsequent MLIR generation since the dataclasses present a uniform Python interface rather than raw JSON nodes.
