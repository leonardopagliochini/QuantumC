# QuantumC

## Introduction

QuantumC demonstrates a tiny compilation pipeline based on [xDSL](https://github.com/xdsl-project/xdsl). The repository converts small C programs into MLIR using a compact collection of helper modules.  The code is intentionally small so that each phase of the translation process can be inspected and experimented with easily.

The flow is divided into two main scripts:

* `generate_ast.py` invokes Clang on every `.c` file under `c_code` and stores the JSON AST into `json_out`.
* `pipeline.py <path>` loads one of those JSON files, converts it into dataclasses, and lowers the dataclasses to standard MLIR.

Both scripts rely on the helper modules described below.

## Usage

1. Activate the supplied virtual environment:
   ```bash
   source qvenv/bin/activate
   ```
2. Generate ASTs for all test C programs, always do this before running pipeline:
   ```bash
   python generate_ast.py
   ```
3. Run the full pipeline on one of the produced JSON files (for example `json_out/try.json`):
   ```bash
   python pipeline.py json_out/try.json
   ```
   The script prints the reconstructed C source and the generated MLIR to the terminal. It also writes two dependency graphs: `output/classical_ir_dag.*` mirrors the MLIR as-is, while `output/no_double_consume_dag.*` duplicates producers when a value is consumed twice by the same operation. Each node shows
   the operation in SSA form (for example `%3 = %2 + %1`).

## Pipeline Overview

The compilation process performed by `pipeline.py` consists of five stages:

1. **JSON Parsing** – `c_ast.parse_ast` converts the Clang generated JSON AST into a hierarchy of lightweight dataclasses such as `FunctionDecl`, `VarDecl`, and `BinaryOperator`.
2. **MLIR Generation** – `mlir_generator.MLIRGenerator` walks those dataclasses and emits standard MLIR using the xDSL API.  Operations with constant immediates make use of custom ops defined in `dialect_ops.py`.
3. **Printing** – xDSL's `Printer` utility is used to display the generated modules.
4. **DAG Extraction** – `QuantumIR.build_classical_ir_dag` writes a graph of dependencies between the MLIR operations.
5. **No Double Consume DAG** – `QuantumIR.build_no_double_consume_dag` duplicates producers when a consumer uses the same value twice.


## Project Structure

```
├── astJsonGen.py          – run clang to dump JSON ASTs
├── generate_ast.py        – convenience wrapper around astJsonGen
├── c_ast.py               – dataclasses and JSON → AST parser
├── mlir_generator.py      – convert AST dataclasses to classical MLIR
├── dialect_ops.py         – arithmetic operations with immediate operands
├── pipeline.py            – command line driver combining all phases
├── mlir_pipeline.py       – compatibility layer re-exporting the main classes
└── docs/                  – additional documentation
```

Each module exposes small classes and functions with comprehensive docstrings so the internals can be inspected using standard Python tools.

### File Descriptions

* **astJsonGen.py** – Uses Clang to dump the AST of each C example.
* **generate_ast.py** – Wrapper around ``astJsonGen.py`` populating ``json_out``.
* **c_ast.py** – Dataclass definitions representing the C AST.
* **mlir_generator.py** – Lowers the dataclasses to classic MLIR.
* **dialect_ops.py** – Immediate arithmetic operations used during lowering.
* **pipeline.py** – Command line driver running the whole compilation pipeline.
* **mlir_pipeline.py** – Compatibility layer re-exporting frequently used names.
* **dag_builder.py** – Utility that extracts a dependency DAG from the MLIR.

## Documentation

Additional documentation describing each stage of the pipeline can be found under the [`docs/`](docs/) directory:

- [AST Generation](docs/ast_generation.md)
- [AST to Dataclasses](docs/ast_to_dataclasses.md)
- [Classical MLIR Generation](docs/classical_mlir_generation.md)
- [Overall Pipeline Overview](docs/pipeline_overview.md)
- [IR Dependency DAG](docs/ir_dag.md)
- [No Double Consume DAG](docs/no_double_consume_dag.md)

