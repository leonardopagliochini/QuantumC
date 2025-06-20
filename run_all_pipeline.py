"""Generate MLIR for all JSON test files."""

from __future__ import annotations
import os
from xdsl.printer import Printer
from pipeline import QuantumIR

def generate_all(json_dir: str = "json_out", out_dir: str = "mlir_out") -> None:
    """Run the pipeline on each JSON file and store MLIR outputs."""
    os.makedirs(out_dir, exist_ok=True)
    for filename in sorted(os.listdir(json_dir)):
        if not filename.endswith(".json"):
            continue
        base = os.path.splitext(filename)[0]
        json_path = os.path.join(json_dir, filename)
        print(f"Processing {filename}...")
        ir = QuantumIR(json_path=json_path)
        ir.run_dataclass()
        ir.run_generate_ir()
        ir.run_generate_quantum_ir()
        with open(os.path.join(out_dir, f"{base}_classical.mlir"), "w") as f:
            Printer(stream=f).print_op(ir.module)
        with open(os.path.join(out_dir, f"{base}_quantum.mlir"), "w") as f:
            Printer(stream=f).print_op(ir.quantum_module)


if __name__ == "__main__":
    generate_all()