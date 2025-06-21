# QuantumC

## Introduction

QuantumC demonstrates a tiny compilation pipeline based on [xDSL](https://github.com/xdsl-project/xdsl). The repository converts small C programs into MLIR and then rewrites that MLIR using a custom quantum dialect.  The code is intentionally compact so that each phase of the translation process can be inspected and experimented with easily.

The flow is divided into two main scripts:

* `generate_ast.py` invokes Clang on every `.c` file under `c_code` and stores the JSON AST into `json_out`.
* `pipeline.py <path>` loads one of those JSON files, converts it into dataclasses, lowers the dataclasses to standard MLIR, and finally translates that MLIR to the quantum dialect.

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
   The script prints the reconstructed C source, the classical MLIR, and the quantum MLIR to the terminal.

## Pipeline Overview

The compilation process performed by `pipeline.py` consists of four stages:

1. **JSON Parsing** – `c_ast.parse_ast` converts the Clang generated JSON AST into a hierarchy of lightweight dataclasses such as `FunctionDecl`, `VarDecl`, and `BinaryOperator`.
2. **MLIR Generation** – `mlir_generator.MLIRGenerator` walks those dataclasses and emits standard MLIR using the xDSL API.  Operations with constant immediates make use of custom ops defined in `dialect_ops.py`.
3. **Quantum Translation** – `quantum_translate.QuantumTranslator` analyzes the classical MLIR and rewrites it into the quantum dialect defined in `quantum_dialect.py`.  Each integer variable becomes a quantum register.  Arithmetic operations are replaced by their quantum counterparts, allocating and reusing registers as needed.
4. **Printing** – xDSL's `Printer` utility is used to display the generated modules.

Running the pipeline will therefore produce two MLIR modules: the direct lowering from C and the equivalent program expressed with quantum operations.

## Project Structure

```
├── astJsonGen.py          – run clang to dump JSON ASTs
├── generate_ast.py        – convenience wrapper around astJsonGen
├── c_ast.py               – dataclasses and JSON → AST parser
├── mlir_generator.py      – convert AST dataclasses to classical MLIR
├── dialect_ops.py         – arithmetic operations with immediate operands
├── quantum_dialect.py     – MLIR dialect for quantum operations
├── quantum_translate.py   – translate classical MLIR to the quantum dialect
├── pipeline.py            – command line driver combining all phases
├── run_all_pipeline.py    – helper to process all JSON files at once
└── docs/                  – additional documentation
```

Each module exposes small classes and functions with comprehensive docstrings so the internals can be inspected using standard Python tools.

