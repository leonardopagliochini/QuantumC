# Project Structure

```
c_ast.py           - dataclass representation of the C-like AST
dialect_ops.py     - helper operations used during translation
generate_ast.py    - script that runs `astJsonGen` over `c_code`
mlir_generator.py  - converts AST dataclasses into MLIR IR
pipeline.py        - main entry point running the full pipeline
mlir_pipeline.py   - re-exports core modules for convenience
astJsonGen.py      - helper that invokes clang to produce JSON AST files
dag_builder.py     - builds a DAG of IR dependencies
```

The typical flow is:
1. `generate_ast.py` converts C files in `c_code` to JSON files in `json_out`.
2. `pipeline.py` parses the JSON using `c_ast.py` and `mlir_generator.py`.

