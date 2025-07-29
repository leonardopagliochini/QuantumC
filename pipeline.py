"""CLI driving the QuantumC compilation pipeline."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from xdsl.dialects.builtin import ModuleOp
from xdsl.printer import Printer

from c_ast import parse_ast, TranslationUnit
from mlir_generator import MLIRGenerator
from quantum_mlir_generator import generate_quantum_mlir
from qasm_generator import generate_circuit, export_qasm

JSON_DIR = "json_out"
MLIR_DIR = "mlir_out"
QMLIR_DIR = "quantum_mlir_out"
QASM_DIR = "output"


def generate_json_ast(c_path: str) -> str:
    """Run clang to dump the JSON AST for ``c_path``."""
    base = os.path.splitext(os.path.basename(c_path))[0]
    os.makedirs(JSON_DIR, exist_ok=True)
    json_path = os.path.join(JSON_DIR, f"{base}.json")
    with open(json_path, "w") as f:
        subprocess.run(
            ["clang", "-Xclang", "-ast-dump=json", "-g", "-fsyntax-only", c_path],
            stdout=f,
            check=True,
        )
    return json_path


def generate_mlir(tu: TranslationUnit) -> ModuleOp:
    """Lower the parsed AST ``tu`` to classical MLIR."""
    generator = MLIRGenerator()
    module = ModuleOp([])
    block = module.body.blocks[0]
    for func in tu.decls:
        block.add_op(generator.generate_function(func))
    return module


def save_module(module: ModuleOp, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        Printer(stream=f).print_op(module)


def compile_c_file(c_file: str, num_bits: int = 16, verbose: bool = False) -> str:
    """Compile ``c_file`` through all pipeline stages and return the QASM path."""
    base = os.path.splitext(os.path.basename(c_file))[0]

    json_path = generate_json_ast(c_file)
    with open(json_path) as f:
        ast_json = json.load(f)
    tu = parse_ast(ast_json)

    mlir_module = generate_mlir(tu)
    classical_path = os.path.join(MLIR_DIR, f"{base}_classical.mlir")
    save_module(mlir_module, classical_path)

    quantum_module = generate_quantum_mlir(mlir_module)
    quantum_path = os.path.join(QMLIR_DIR, f"{base}_quantum.mlir")
    save_module(quantum_module, quantum_path)

    circuit = generate_circuit(quantum_module, num_bits=num_bits, verbose=verbose)
    qasm_path = os.path.join(QASM_DIR, f"{base}.qasm")
    export_qasm(circuit, qasm_path)

    return qasm_path


def main() -> None:
    c_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join("c_code", "try.c")
    compile_c_file(c_file)


if __name__ == "__main__":
    main()
