# QuantumC

## Introduction

QuantumC is a small experimental compiler pipeline built on top of [xDSL](https://github.com/xdsl-dev/xdsl). It starts from simple C source files and lowers them in multiple stages:

1. The C files are converted to Clang JSON AST dumps.
2. The JSON is parsed into lightweight Python dataclasses.
3. The dataclasses are lowered to classical MLIR using xDSL.
4. The classical MLIR is translated to a custom quantum dialect.

The repository demonstrates how to go from regular C code to a quantum friendly IR while keeping the individual stages easy to inspect.

## Usage

First generate the AST dumps. This requires a working `clang` installation.

```bash
python generate_ast.py
```

This reads all `*.c` files in `c_code/` and emits `json_out/<file>.json`.
Each JSON file can then be fed to the main pipeline:

```bash
python pipeline.py json_out/try.json
```

The program prints the dataclass AST, the classical MLIR and finally the quantum MLIR.

## Detailed Process

The high level entry point is the `QuantumIR` class in `pipeline.py`.
It exposes methods for each stage of the flow:

1. **run_dataclass** – parses the JSON AST using `c_ast.parse_ast`.
2. **run_generate_ir** – converts the dataclasses to MLIR via `MLIRGenerator`.
3. **run_generate_quantum_ir** – rewrites the MLIR to the quantum dialect using `QuantumTranslator`.

The supporting modules are:

- **astJsonGen.py** – helper invoking Clang to create JSON AST files.
- **c_ast.py** – dataclasses representing the AST and utilities for parsing and pretty printing.
- **mlir_generator.py** – lowers the dataclasses to standard MLIR operations and includes helper ops defined in `dialect_ops.py`.
- **quantum_translate.py** – converts classical arithmetic operations to quantum operations defined in `quantum_dialect.py` while keeping track of virtual quantum registers.
- **run_all_pipeline.py** – convenience script that runs the pipeline over every JSON file and writes the resulting MLIR to `mlir_out/`.

## Code Layout

```
pipeline.py           - orchestrates the entire flow
mlir_generator.py     - converts dataclasses to MLIR
quantum_translate.py  - turns classical MLIR into quantum dialect
quantum_dialect.py    - quantum operations
dialect_ops.py        - MLIR operations with immediates
c_ast.py              - dataclass AST representation
astJsonGen.py         - clang JSON AST generation helper
generate_ast.py       - runs astJsonGen on c_code/
run_all_pipeline.py   - batch processing helper
test_mlir_equivalence.py - compares classical vs quantum MLIR results
```

The AST dataclasses form a simple hierarchy:

```
Expression
├─ IntegerLiteral
├─ DeclRef
├─ BinaryOperator
└─ BinaryOperatorWithImmediate

VarDecl
AssignStmt
ReturnStmt
CompoundStmt
FunctionDecl
TranslationUnit
```

The quantum dialect defines operations such as `quantum.init`, `quantum.addi`, and variants taking immediate values. These mirror the classic arithmetic operations so that the translator can replace them one-to-one.

## Example

After running `generate_ast.py`, try:

```bash
python pipeline.py json_out/test_1.json
```

You will see the original program reconstructed from the dataclasses, the classical MLIR, and finally the quantum MLIR.

