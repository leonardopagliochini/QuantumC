"""CLI driving the QuantumC compilation pipeline."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import csv

from xdsl.dialects.builtin import ModuleOp
from xdsl.printer import Printer

from step2_ast_to_dataclasses.c_ast import parse_ast, TranslationUnit, pretty_print_translation_unit
from step3_dataclasses_to_mlir.mlir_generator import MLIRGenerator
from step4_mlir_to_quantum_mlir.quantum_mlir_generator import generate_quantum_mlir
from step5_quantum_mlir_to_qasm.qasm_generator import generate_circuit, export_qasm, export_qasm_clifford_t
from step5_quantum_mlir_to_qasm.q_arithmetics import simulate

from qiskit import QuantumCircuit, transpile
from qiskit.transpiler import PassManager
from qiskit.transpiler.passes import RemoveBarriers

JSON_DIR = "json_out"
MLIR_DIR = "mlir_out"
QMLIR_DIR = "quantum_mlir_out"
QASM_DIR = "output"
BENCHMARK_CSV = "benchmark_results.csv"


def generate_json_ast(c_path: str) -> str:
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


def compile_c_file(
    c_file: str, num_bits: int = 16, verbose: bool = False, pretty: bool = False, run: bool = False
) -> str:
    base = os.path.splitext(os.path.basename(c_file))[0]

    json_path = generate_json_ast(c_file)
    with open(json_path) as f:
        ast_json = json.load(f)
    tu = parse_ast(ast_json)

    if pretty:
        print("=== Pretty Printed C Code ===")
        print(pretty_print_translation_unit(tu))
        print("================================")

    mlir_module = generate_mlir(tu)
    classical_path = os.path.join(MLIR_DIR, f"{base}_classical.mlir")
    save_module(mlir_module, classical_path)

    quantum_module = generate_quantum_mlir(mlir_module)
    quantum_path = os.path.join(QMLIR_DIR, f"{base}_quantum.mlir")
    save_module(quantum_module, quantum_path)

    circuit = generate_circuit(quantum_module, num_bits=num_bits, verbose=verbose)
    qasm_path = os.path.join(QASM_DIR, f"{base}.qasm")

    # Export depending on run
    if run:
        export_qasm(circuit, qasm_path)
    else:
        export_qasm_clifford_t(circuit, qasm_path)

    return qasm_path


def run_benchmarks(folder: str, num_bits: int) -> None:
    all_gate_types = set()
    results = []

    os.makedirs(QASM_DIR, exist_ok=True)

    c_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".c")]
    for c_file in sorted(c_files):
        try:
            print(f"[+] Compiling {c_file}...")
            qasm_path = compile_c_file(c_file, num_bits=num_bits, run=False)
            qc = QuantumCircuit.from_qasm_file(qasm_path)
            qc = transpile(qc, optimization_level=3)
            qc = PassManager(RemoveBarriers()).run(qc)

            gate_counts = qc.count_ops()
            all_gate_types.update(gate_counts.keys())

            results.append({
                "filename": os.path.basename(c_file),
                "num_qubits": qc.num_qubits,
                "total_gates": qc.size(),
                **gate_counts
            })
        except Exception as e:
            print(f"[!] Error compiling {c_file}: {e}")

    all_gates = sorted(all_gate_types)
    with open(BENCHMARK_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "num_qubits", "total_gates"] + all_gates)
        writer.writeheader()
        for row in results:
            for g in all_gates:
                if g not in row:
                    row[g] = 0
            writer.writerow(row)

    print(f"[✓] Benchmark results saved to {BENCHMARK_CSV}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile C code to QASM and optionally simulate.")
    parser.add_argument("c_file", nargs="?", default=os.path.join("c_code", "try.c"), help="Path to the C file")
    parser.add_argument("--run", action="store_true", help="Run the resulting QASM file with simulation")
    parser.add_argument("--bits", type=int, default=16, help="Number of bits used for the quantum representation")
    parser.add_argument("--verbose", action="store_true", help="Verbose output during circuit generation")
    parser.add_argument("--pretty", action="store_true", help="Print the parsed C code from the AST")
    parser.add_argument("--benchmarks", type=str, help="Run benchmark on folder of C files")
    parser.add_argument("--time", action="store_true", help="Print total compilation + simulation time")

    args = parser.parse_args()

    if args.benchmarks:
        run_benchmarks(args.benchmarks, args.bits)
        return

    start = time.time() if args.time else None

    qasm_path = compile_c_file(
        args.c_file,
        num_bits=args.bits,
        verbose=args.verbose,
        pretty=args.pretty,
        run=args.run,
    )

    if args.run:
        print(f"Running simulation for {qasm_path} ...")
        qc = QuantumCircuit.from_qasm_file(qasm_path)
        simulate(qc)

    if args.time:
        elapsed = time.time() - start
        print(f"\n[Pipeline completed in {elapsed:.2f} seconds]")


if __name__ == "__main__":
    main()
