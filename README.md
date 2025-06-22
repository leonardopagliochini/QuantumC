# QuantumC

## Introduction

QuantumC demonstrates a tiny compilation pipeline based on [xDSL](https://github.com/xdsl-project/xdsl). The repository converts small C programs into MLIR and then rewrites that MLIR using a custom quantum dialect.  The last step enforces *write-in-place* semantics on that dialect rather than producing a full quantum program. The code is intentionally compact so that each phase of the translation process can be inspected and experimented with easily.

The flow is divided into two main scripts:

* `generate_ast.py` invokes Clang on every `.c` file under `c_code` and stores the JSON AST into `json_out`.
* `pipeline.py <path>` loads one of those JSON files, converts it into dataclasses, lowers the dataclasses to standard MLIR, and finally enforces write-in-place semantics using the quantum dialect.

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
   The script prints the reconstructed C source, the classical MLIR, and the write-in-place quantum IR to the terminal.

## Pipeline Overview

The compilation process performed by `pipeline.py` consists of four stages:

1. **JSON Parsing** – `c_ast.parse_ast` converts the Clang generated JSON AST into a hierarchy of lightweight dataclasses such as `FunctionDecl`, `VarDecl`, and `BinaryOperator`.
2. **MLIR Generation** – `mlir_generator.MLIRGenerator` walks those dataclasses and emits standard MLIR using the xDSL API.  Operations with constant immediates make use of custom ops defined in `dialect_ops.py`.
3. **Write-in-Place Enforcement** – `quantum_translate.QuantumTranslator` analyzes the classical MLIR and rewrites it into the quantum dialect defined in `quantum_dialect.py` while enforcing write-in-place semantics.  Each integer variable becomes a quantum register, and arithmetic operations overwrite their left operand using versioned paths to avoid clobbering existing values.
4. **Printing** – xDSL's `Printer` utility is used to display the generated modules.
5. **Path Visualization** – `paths_dataframe.build_paths_dataframe` constructs a pandas DataFrame showing register usage which is stored on `QuantumIR.paths_df`. The table includes an `operation` column describing the computation performed at each timestep.

Running the pipeline will therefore produce two MLIR modules: the direct lowering from C and a write-in-place version expressed with quantum-style operations.

The translator assigns a numeric register identifier to each integer variable and
tracks both a version and path every time a register is overwritten.  The classical and
write-in-place versions are compared in ``test_mlir_equivalence.py`` using the xDSL
interpreter to ensure they compute the same result.

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
├── mlir_pipeline.py       – compatibility layer re-exporting the main classes
├── test_mlir_equivalence.py – lightweight regression test
└── docs/                  – additional documentation
```

Each module exposes small classes and functions with comprehensive docstrings so the internals can be inspected using standard Python tools.

### File Descriptions

* **astJsonGen.py** – Uses Clang to dump the AST of each C example.
* **generate_ast.py** – Wrapper around ``astJsonGen.py`` populating ``json_out``.
* **c_ast.py** – Dataclass definitions representing the C AST.
* **mlir_generator.py** – Lowers the dataclasses to classic MLIR.
* **dialect_ops.py** – Immediate arithmetic operations used during lowering.
* **quantum_dialect.py** – Defines the custom quantum operations and properties.
* **quantum_translate.py** – Rewrites standard MLIR into the quantum dialect and enforces write-in-place semantics.
* **paths_dataframe.py** – Builds a pandas table mapping register versions used during translation.
* **pipeline.py** – Command line driver running the whole compilation pipeline.
* **mlir_pipeline.py** – Compatibility layer re-exporting frequently used names.
* **test_mlir_equivalence.py** – Regression test comparing classical and write-in-place outputs.

## Documentation

Additional documentation describing each stage of the pipeline can be found under the [`docs/`](docs/) directory:

- [AST Generation](docs/ast_generation.md)
- [AST to Dataclasses](docs/ast_to_dataclasses.md)
- [Classical MLIR Generation](docs/classical_mlir_generation.md)
- [Enforcing Write-In-Place](docs/enforce_write_in_place.md)
- [Overall Pipeline Overview](docs/pipeline_overview.md)

