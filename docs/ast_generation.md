# AST Generation

`generate_ast.py` drives the creation of Clang JSON AST files from the small C programs stored in `c_code/`.  It relies on `astJsonGen.py` which wraps the Clang invocation and places the resulting JSON under `json_out/`.

## Files
- **astJsonGen.py** – Contains `generate_ast(path: str)` that invokes Clang with `-ast-dump=json` and writes the output to the given path.
- **generate_ast.py** – Scans `c_code/` and calls `generate_ast` for every `.c` file found.  Run this script whenever the input programs change.

Running `python generate_ast.py` ensures fresh ASTs are available for the rest of the pipeline.
