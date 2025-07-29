# QuantumC

This repository contains a small experimental compiler pipeline that converts
simple C programs into MLIR and then into a custom quantum dialect. The project
also includes tools to generate quantum circuits from the translated IR.

## Entry points

- [`pipeline.py`](./pipeline.py) – compile a C source directly to QASM while
  saving JSON and MLIR intermediates.
- [`quantum_mlir_generator.py`](./step4_mlir_to_quantum_mlir/quantum_mlir_generator.py) – wraps the
  translation from classical MLIR to the custom quantum dialect.
- [`qasm_generator.py`](./step5_quantum_mlir_to_qasm/qasm_generator.py) – utilities to build a
  `QuantumCircuit` and export it as QASM.
- [`generate_ast.py`](./step1_c_to_ast/generate_ast.py) – helper that calls
  [`astJsonGen.py`](./step1_c_to_ast/astJsonGen.py) over the `c_code` folder to regenerate the
  JSON AST files.
- [`generate_llvm.py`](./generate_llvm.py) – produces loop-unrolled LLVM IR for
  the test C sources.
- [`run_all_pipeline.py`](./run_all_pipeline.py) – runs the pipeline on every
  JSON file under `json_out` and stores the MLIR output.

## Source files

### Core compiler

- [`c_ast.py`](./step2_ast_to_dataclasses/c_ast.py) – dataclass definitions for a tiny C‑like AST and
  utilities to parse the JSON produced by Clang. Also implements pretty printing
  back to C code.
- [`mlir_generator.py`](./step3_dataclasses_to_mlir/mlir_generator.py) – lowers the dataclass AST to MLIR
  using xDSL constructs.
- [`dialect_ops.py`](./step3_dataclasses_to_mlir/dialect_ops.py) – custom MLIR operations for arithmetic
  with immediates. These are used during lowering and later interpreted in tests.
- [`quantum_dialect.py`](./step4_mlir_to_quantum_mlir/quantum_dialect.py) – defines the quantum dialect
  operations that operate on quantum registers.
- [`quantum_translate.py`](./step4_mlir_to_quantum_mlir/quantum_translate.py) – translates classical MLIR
  into the quantum dialect while tracking register allocation and value
  lifetimes.

### Quantum circuit generation

- [`q_arithmetics.py`](./step5_quantum_mlir_to_qasm/q_arithmetics.py) – helper functions implemented with
  Qiskit for arithmetic operations on quantum registers.
- [`q_arithmetics_controlled.py`](./step5_quantum_mlir_to_qasm/q_arithmetics_controlled.py) – controlled
  versions of the same operations.

### Utility scripts

- [`llvmIrGen.py`](./llvmIrGen.py) – invokes `clang` and `opt` to generate LLVM
  IR for the C test files with loop unrolling.
- [`astJsonGen.py`](./step1_c_to_ast/astJsonGen.py) – runs `clang -ast-dump=json` on every C
  source in a folder.

### Tests

- [`test_all_c_files_to_fix.py`](./test_all_c_files_to_fix.py) – regenerates JSON
  and MLIR for every C file in `c_code` and then checks the outputs.
- [`test_mlir_equivalence_to_fix.py`](./test_mlir_equivalence_to_fix.py) – loads
  the saved MLIR modules and interprets them to ensure classical and quantum
  variants return the same result.

### Sample inputs and binaries

- [`c_code/`](./c_code/) – contains the example C programs. `try.c` is used by
  default and the `others/` directory holds additional small tests. The `main`
  binary is a pre‑built executable.
- [`provaMLIR/json_out/try.json`](./provaMLIR/json_out/try.json) – sample JSON AST
  used for experimentation.
- [`main`](./main) – compiled executable (macOS binary) unrelated to the Python
  pipeline.
- [`c_code/main`](./c_code/main) – another compiled binary accompanying the test
  sources.

### Miscellaneous

- [`check_circuits.ipynb`](./check_circuits.ipynb) – Jupyter notebook with
  experiments for verifying generated circuits.
- [`Readings_all/`](./Readings_all/) – collection of research papers related to
  quantum compilation.
- [`qvenv/`](./qvenv/) – Python virtual environment containing third‑party
  dependencies. It is not required to understand the project logic.
- [`.gitignore`](./.gitignore) – lists files and folders excluded from version
  control.
- [`.DS_Store`](./.DS_Store) – macOS metadata file.


## How it all fits together

1. **Generate AST** – `pipeline.py` invokes Clang on the chosen C source and
   stores the JSON AST under `json_out/`.
2. **Lower to MLIR** – the AST is lowered by `step3_dataclasses_to_mlir/mlir_generator.py` to classical
   MLIR saved in `mlir_out/`.
3. **Translate to quantum MLIR** – `step4_mlir_to_quantum_mlir/quantum_mlir_generator.py` converts the
   classical IR to the quantum dialect defined in `step4_mlir_to_quantum_mlir/quantum_dialect.py` and
   `step3_dataclasses_to_mlir/dialect_ops.py`.
4. **Build circuits** – `step5_quantum_mlir_to_qasm/qasm_generator.py` interprets the quantum MLIR with
   helpers from `step5_quantum_mlir_to_qasm/q_arithmetics.py` and `step5_quantum_mlir_to_qasm/q_arithmetics_controlled.py` and exports
   a QASM circuit under `output/`.
5. **Testing** – `test_all_c_files_to_fix.py` regenerates JSON and MLIR for all
   example sources, while `test_mlir_equivalence_to_fix.py` loads those modules
   and checks that classical and quantum executions produce identical results.

This overview should help navigate every file in the repository and understand
how the pieces interact to form a simple C‑to‑quantum compilation pipeline.