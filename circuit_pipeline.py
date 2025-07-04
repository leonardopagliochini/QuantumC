"""Pipeline that generates a quantum circuit from the quantum MLIR."""
from __future__ import annotations
import os
from typing import Dict

from qiskit import QuantumCircuit

from xdsl.dialects.func import ReturnOp

from quantum_dialect import (
    QuantumInitOp,
    QAddiOp,
    QSubiOp,
    QMuliOp,
    QDivSOp,
    QAddiImmOp,
    QSubiImmOp,
    QMuliImmOp,
    QDivSImmOp,
)

import q_arithmetics as qa
from pipeline import QuantumIR


class QuantumCircuitPipeline(QuantumIR):
    """Extended pipeline creating a :class:`.QuantumCircuit`."""

    def __init__(self, json_path: str = "json_out/try.json", output_dir: str = "output", num_bits: int = 8) -> None:
        super().__init__(json_path=json_path, output_dir=output_dir)
        self.num_bits = num_bits
        self.circuit: QuantumCircuit | None = None

    # ------------------------------------------------------------------
    def run_generate_circuit(self) -> None:
        """Generate a quantum circuit from the quantum MLIR."""
        if self.quantum_module is None:
            raise RuntimeError("Must call run_generate_quantum_ir first")

        qa.set_number_of_bits(self.num_bits)
        qc = QuantumCircuit()
        reg_map: Dict[object, object] = {}

        for func in self.quantum_module.ops:
            block = func.body.blocks[0]
            for op in block.ops:
                if isinstance(op, QuantumInitOp):
                    val = int(op.value.value.data)
                    reg = qa.initialize_variable(qc, val)
                    reg_map[op.results[0]] = reg
                elif isinstance(op, QAddiOp):
                    lhs = reg_map[op.lhs]
                    rhs = reg_map[op.rhs]
                    reg_map[op.results[0]] = qa.add(qc, lhs, rhs)
                elif isinstance(op, QSubiOp):
                    lhs = reg_map[op.lhs]
                    rhs = reg_map[op.rhs]
                    reg_map[op.results[0]] = qa.sub(qc, lhs, rhs)
                elif isinstance(op, QMuliOp):
                    lhs = reg_map[op.lhs]
                    rhs = reg_map[op.rhs]
                    reg_map[op.results[0]] = qa.mul(qc, lhs, rhs)
                elif isinstance(op, QAddiImmOp):
                    lhs = reg_map[op.lhs]
                    imm = int(op.imm.value.data)
                    reg_map[op.results[0]] = qa.addi(qc, lhs, imm)
                elif isinstance(op, QSubiImmOp):
                    lhs = reg_map[op.lhs]
                    imm = int(op.imm.value.data)
                    reg_map[op.results[0]] = qa.subi(qc, lhs, imm)
                elif isinstance(op, QMuliImmOp):
                    lhs = reg_map[op.lhs]
                    imm = int(op.imm.value.data)
                    reg_map[op.results[0]] = qa.muli(qc, lhs, imm)
                elif isinstance(op, (QDivSOp, QDivSImmOp)):
                    raise NotImplementedError("Division operations are not supported")
                elif isinstance(op, ReturnOp):
                    if op.operands:
                        reg = reg_map[op.operands[0]]
                        qa.measure(qc, reg)
                else:
                    raise NotImplementedError(f"Unsupported op {op.name}")
        self.circuit = qc

    # ------------------------------------------------------------------
    def export_qasm(self, filename: str = "out.qasm") -> str:
        """Write the generated circuit to ``filename`` and return its path."""
        if self.circuit is None:
            raise RuntimeError("Must call run_generate_circuit first")
        path = os.path.join(self.output_dir, filename)
        os.makedirs(self.output_dir, exist_ok=True)
        from qiskit import qasm2
        with open(path, "w") as f:
            f.write(qasm2.dumps(self.circuit))
        print(f"QASM circuit written to {path}")
        return path


def main() -> None:
    """CLI entry point mirroring :mod:`pipeline` with circuit generation."""
    import sys

    input_json = sys.argv[1] if len(sys.argv) > 1 else "json_out/try.json"
    pipeline = QuantumCircuitPipeline(json_path=input_json)
    pipeline.run_dataclass()
    pipeline.run_generate_ir()
    pipeline.run_generate_quantum_ir()
    pipeline.run_generate_circuit()
    pipeline.export_qasm()


if __name__ == "__main__":
    main()
