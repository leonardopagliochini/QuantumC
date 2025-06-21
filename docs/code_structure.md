# Project Structure

```
pipeline.py        - main entry point running the full pipeline
mlir_pipeline.py   - re-exports core modules for convenience
mlir_generator.py  - converts AST dataclasses into MLIR IR
quantum_translate.py - enforces write-in-place semantics on the quantum dialect
quantum_dialect.py - defines the custom quantum dialect operations
dialect_ops.py     - helper operations used during translation
c_ast.py           - dataclass representation of the C-like AST
astJsonGen.py      - helper that invokes clang to produce JSON AST files
generate_ast.py    - script that runs `astJsonGen` over `c_code`
```

The typical flow is:
1. `generate_ast.py` converts C files in `c_code` to JSON files in `json_out`.
2. `pipeline.py` parses the JSON using `c_ast.py` and `mlir_generator.py`.
3. Generated MLIR is processed by `quantum_translate.py` to enforce write-in-place semantics using operations defined in `quantum_dialect.py` and
   `dialect_ops.py`.

