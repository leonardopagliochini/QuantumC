# AST Generation Overview

`generate_ast.py` is the entry point responsible for producing the abstract syntax trees used by the rest of the pipeline. It orchestrates the execution of `astJsonGen.py`, which wraps Clang's `-ast-dump=json` facility. Every C file found in `c_code/` is translated into a JSON AST stored under `json_out/`.

This document explains the implementation in detail and describes how the generated ASTs fit into the larger experimental compiler.

## Context within the Pipeline

The repository implements a prototype translation flow that converts a subset of the C language into MLIR and eventually into a custom quantum dialect. The stages, as outlined in the project README, are:

1. **AST generation** – `generate_ast.py` runs Clang on the test programs and places the resulting JSON into `json_out/`.
2. **MLIR lowering** – `pipeline.py` together with `mlir_generator.py` parses the JSON into dataclasses (`c_ast.py`) and emits standard MLIR.
3. **Quantum translation** – `quantum_translate.py` rewrites the MLIR to operations in `quantum_dialect.py`.
4. **Circuit creation** – optional helpers interpret the quantum IR with Qiskit primitives to build actual circuits.

`generate_ast.py` therefore represents the first step in refreshing the inputs for all downstream phases. The produced JSON is consumed by `pipeline.py` when executing tests or constructing circuits.

## Practical Operation of `generate_ast.py`

```
$ python generate_ast.py
```

Invoking the script performs the following actions:

1. It imports and calls `astJsonGen.astJsonGen`.
2. `astJsonGen` locates the `c_code/` directory relative to the current working directory and enumerates every file ending in `.c`.
3. For each file, a command of the form

   ```bash
   clang -Xclang -ast-dump=json -g -fsyntax-only path/to/file.c > json_out/file.json
   ```

   is executed. The `clang` invocation performs only a syntax check and writes a JSON representation of the AST to the `json_out/` directory.
4. The helper prints the path to each generated file for confirmation.

`generate_ast.py` contains no additional logic beyond forwarding to `astJsonGen`, keeping the interface simple.

## Theoretical Considerations

Clang's JSON AST serves as a stable, structured description of the source program. By converting all examples up front we decouple subsequent translation passes from Clang itself. The JSON is later parsed into a smaller set of dataclasses defined in `c_ast.py`. Those dataclasses model a tiny, well-defined subset of C that is amenable to automatic translation into MLIR.

Using JSON as the interchange format provides two benefits:

* **Determinism** – the dumped AST does not depend on compiler optimisations or code generation details.
* **Reusability** – multiple scripts can consume the same JSON without repeatedly invoking Clang.

## Supported C Subset

Only a restricted portion of C is handled by the current pipeline. The dataclasses in `c_ast.py` reveal which constructs are recognised and therefore which operations can appear in the generated ASTs:

* **Integer literals** and variable references.
* **Binary arithmetic:** `+`, `-`, `*`, and `/`.
* **Binary comparisons:** `==`, `!=`, `<`, `<=`, `>`, `>=`.
* **Logical conjunction and disjunction** (`&&`, `||`) in `if` conditions.
* **Assignments** to previously declared variables.
* **Variable declarations** with optional initialization.
* **`return` statements** returning an integer.
* **`if` statements** including optional `else` blocks and cascading `else if` forms.
* **`for` loops** with initialization, condition, increment, and a compound body. Loop bodies are unrolled in MLIR generation up to a fixed bound (`MAX_UNROLL` in `mlir_generator.py`).

Unary operators such as `+`, `-`, `++`, `--`, `!` and `~` are fully supported. All variables and operations operate on `int` values; other types are unsupported.

These limitations mean that `generate_ast.py` and the subsequent pipeline are best viewed as a proof of concept focusing on straight-line arithmetic with simple control flow.

## Interaction with the Rest of the Program

Once `generate_ast.py` has produced the JSON files, subsequent scripts load them to drive the compilation flow:

1. **Parsing** – `QuantumIR.run_dataclass()` reads a chosen JSON file and converts it into `TranslationUnit`, `FunctionDecl`, `CompoundStmt`, and the other dataclasses.
2. **MLIR emission** – `MLIRGenerator` walks this dataclass representation to emit xDSL/MLIR. Arithmetic operations map to either standard operations or custom immediate forms defined in `dialect_ops.py`.
3. **Quantum translation** – `QuantumTranslator` rewrites these classical operations into their quantum counterparts while allocating quantum registers and tracking value lifetimes.
4. **Testing and circuits** – various helpers interpret the generated MLIR or translate it further into Qiskit circuits for experimentation.

Because the AST dump precisely captures the structure of the original C programs, it acts as the single source of truth for all later stages. Regenerating the JSON whenever the C sources change ensures reproducibility of the translation pipeline.

## Constraints and Requirements

* A working Clang installation must be available on the system path. The helper invokes `clang` directly and will fail if it is missing.
* The script expects a directory named `c_code/` next to the repository root containing the example `.c` files.
* Output JSON files are written to `json_out/`. The directory is created if it does not exist.
* Existing JSON files are overwritten without warning; version control can be used to track changes.

## Summary

`generate_ast.py` is a thin wrapper that triggers the AST generation phase of the QuantumC prototype. By converting all sample C programs to a uniform JSON representation it decouples the remainder of the pipeline from Clang and enables deterministic testing and experimentation. The supported language subset—integer arithmetic with simple control flow—reflects the early-stage nature of the project yet suffices to explore automatic lowering to MLIR and a quantum dialect.
