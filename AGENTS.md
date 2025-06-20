# Coding Guidelines

- Only edit files inside this repository's root, excluding the `qvenv` directory which contains the virtual environment.
- Each Python file should include a clear module level docstring and docstrings for all classes and functions.
- Keep code formatting simple and compatible with `python -m py_compile`.

# Testing

Run the following from the repository root after making changes:

```bash
source qvenv/bin/activate
python generate_ast.py
python -m py_compile dialect_ops.py quantum_dialect.py quantum_translate.py generate_ast.py mlir_pipeline.py mlir_generator.py pipeline.py astJsonGen.py c_ast.py
python pipeline.py
```

Ensure the pipeline executes without errors.
