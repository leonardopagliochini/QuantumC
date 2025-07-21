"""Pipeline that generates a quantum circuit from the quantum MLIR."""
from __future__ import annotations
import os
from typing import Dict

from qiskit import QuantumCircuit

from xdsl.dialects.func import ReturnOp

from astJsonGen import astJsonGen

from quantum_dialect import (
    QuantumInitOp, QuantumCInitOp,
    QAddiOp, QSubiOp, QMuliOp, QDivSOp,
    QAddiImmOp, QSubiImmOp, QMuliImmOp, QDivSImmOp,
    CQAddiOp, CQSubiOp, CQMuliOp, CQDivSOp,
    CQAddiImmOp, CQSubiImmOp, CQMuliImmOp, CQDivSImmOp,
    QCmpiOp, QAndOp, QNotOp,
)

import q_arithmetics as qa
import q_arithmetics_controlled as qac
from pipeline import QuantumIR


class QuantumCircuitPipeline(QuantumIR):
    """Extended pipeline creating a :class:`.QuantumCircuit`."""

    def __init__(self, json_path: str = "json_out/try.json", output_dir: str = "output", num_bits: int = 8, verbose: bool = False) -> None:
        super().__init__(json_path=json_path, output_dir=output_dir)
        self.num_bits = num_bits
        self.verbose = verbose
        self.circuit: QuantumCircuit | None = None

    def run_generate_circuit(self) -> None:
        """Generate a quantum circuit from the quantum MLIR."""
        if self.quantum_module is None:
            raise RuntimeError("Must call run_generate_quantum_ir first")

        qa.set_number_of_bits(self.num_bits)
        qc = QuantumCircuit()
        reg_map: Dict[object, object] = {}

        def log_op(op, msg=None):
            if self.verbose:
                result = op.results[0] if op.results else "?"
                op_type = op.__class__.__name__
                print(f"[{op_type}] {result} = {op.name}({', '.join(str(a) for a in op.operands)})" + (f" → {msg}" if msg else ""))

        for func in self.quantum_module.ops:
            block = func.body.blocks[0]
            for op in block.ops:

                if isinstance(op, QuantumInitOp):
                    val = int(op.value.value.data)
                    log_op(op, f"init {val}")
                    reg = qa.initialize_variable(qc, val)
                    reg_map[op.results[0]] = reg

                elif isinstance(op, QuantumCInitOp):
                    val = int(op.value.value.data)
                    ctrl = reg_map[op.ctrl]
                    log_op(op, f"c_init {val} controlled by {op.ctrl}")
                    reg = qac.initialize_variable_controlled(qc, val, ctrl)
                    reg_map[op.results[0]] = reg

                elif isinstance(op, QAddiOp):
                    log_op(op, "add")
                    reg_map[op.results[0]] = qa.add(qc, reg_map[op.lhs], reg_map[op.rhs])
                elif isinstance(op, QSubiOp):
                    log_op(op, "sub")
                    reg_map[op.results[0]] = qa.sub(qc, reg_map[op.lhs], reg_map[op.rhs])
                elif isinstance(op, QMuliOp):
                    log_op(op, "mul")
                    reg_map[op.results[0]] = qa.mul(qc, reg_map[op.lhs], reg_map[op.rhs])
                elif isinstance(op, QDivSOp):
                    log_op(op, "div")
                    reg_map[op.results[0]], _ = qa.div(qc, reg_map[op.lhs], reg_map[op.rhs])

                elif isinstance(op, QAddiImmOp):
                    imm = int(op.imm.value.data)
                    log_op(op, f"addi_imm {imm}")
                    reg_map[op.results[0]] = qa.addi(qc, reg_map[op.lhs], imm)
                elif isinstance(op, QSubiImmOp):
                    imm = int(op.imm.value.data)
                    log_op(op, f"subi_imm {imm}")
                    reg_map[op.results[0]] = qa.subi(qc, reg_map[op.lhs], imm)
                elif isinstance(op, QMuliImmOp):
                    imm = int(op.imm.value.data)
                    log_op(op, f"muli_imm {imm}")
                    reg_map[op.results[0]] = qa.muli(qc, reg_map[op.lhs], imm)
                elif isinstance(op, QDivSImmOp):
                    imm = int(op.imm.value.data)
                    log_op(op, f"divi_imm {imm}")
                    reg_map[op.results[0]], _ = qa.divi(qc, reg_map[op.lhs], imm)

                elif isinstance(op, CQAddiOp):
                    log_op(op, "c_add")
                    reg_map[op.results[0]] = qac.add_controlled(qc, reg_map[op.lhs], reg_map[op.rhs], reg_map[op.ctrl])
                elif isinstance(op, CQSubiOp):
                    log_op(op, "c_sub")
                    reg_map[op.results[0]] = qac.sub_controlled(qc, reg_map[op.lhs], reg_map[op.rhs], reg_map[op.ctrl])
                elif isinstance(op, CQMuliOp):
                    log_op(op, "c_mul")
                    reg_map[op.results[0]] = qac.mul_controlled(qc, reg_map[op.lhs], reg_map[op.rhs], reg_map[op.ctrl])
                elif isinstance(op, CQDivSOp):
                    log_op(op, "c_div")
                    reg_map[op.results[0]], _ = qac.div_controlled(qc, reg_map[op.lhs], reg_map[op.rhs], reg_map[op.ctrl])

                elif isinstance(op, CQAddiImmOp):
                    imm = int(op.imm.value.data)
                    log_op(op, f"c_addi_imm {imm}")
                    reg_map[op.results[0]] = qac.addi_controlled(qc, reg_map[op.lhs], imm, reg_map[op.ctrl])
                elif isinstance(op, CQSubiImmOp):
                    imm = int(op.imm.value.data)
                    log_op(op, f"c_subi_imm {imm}")
                    reg_map[op.results[0]] = qac.subi_controlled(qc, reg_map[op.lhs], imm, reg_map[op.ctrl])
                elif isinstance(op, CQMuliImmOp):
                    imm = int(op.imm.value.data)
                    log_op(op, f"c_muli_imm {imm}")
                    reg_map[op.results[0]] = qac.muli_controlled(qc, reg_map[op.lhs], imm, reg_map[op.ctrl])
                elif isinstance(op, CQDivSImmOp):
                    imm = int(op.imm.value.data)
                    log_op(op, f"c_divi_imm {imm}")
                    reg_map[op.results[0]], _ = qac.divi_controlled(qc, reg_map[op.lhs], imm, reg_map[op.ctrl])

                elif isinstance(op, QCmpiOp):
                    lhs = reg_map[op.lhs]
                    rhs = reg_map[op.rhs]
                    predicate = int(op.predicate.value.data)
                    msg = ["eq", "neq", "lt", "le", "gt", "ge"][predicate]
                    log_op(op, f"cmpi.{msg}")
                    if predicate == 0:
                        reg_map[op.results[0]] = qa.equal(qc, lhs, rhs)
                    elif predicate == 1:
                        reg_map[op.results[0]] = qa.not_equal(qc, lhs, rhs)
                    elif predicate == 2:
                        reg_map[op.results[0]] = qa.less_than(qc, lhs, rhs)
                    elif predicate == 3:
                        reg_map[op.results[0]] = qa.less_equal(qc, lhs, rhs)
                    elif predicate == 4:
                        reg_map[op.results[0]] = qa.greater_than(qc, lhs, rhs)
                    elif predicate == 5:
                        reg_map[op.results[0]] = qa.greater_equal(qc, lhs, rhs)
                    else:
                        raise NotImplementedError(f"Unsupported cmp predicate: {predicate}")

                elif isinstance(op, QAndOp):
                    log_op(op, "and")
                    lhs = reg_map[op.lhs]
                    rhs = reg_map[op.rhs]
                    reg_map[op.results[0]] = qa.logical_and(qc, lhs, rhs)

                elif isinstance(op, QNotOp):
                    operand = reg_map[op.operand]
                    existing_names = {reg.name for reg in qc.qregs}
                    idx = 0
                    while f"not{idx}" in existing_names:
                        idx += 1
                    out = qa.initialize_bit(qc, 1, f"not{idx}")
                    log_op(op, "not")
                    qc.cx(operand, out)
                    reg_map[op.results[0]] = out

                elif isinstance(op, ReturnOp):
                    if op.operands:
                        log_op(op, f"return {op.operands[0]}")
                        try:
                            qa.measure(qc, reg_map[op.operands[0]])
                        except Exception as e:
                            if "already exists" in str(e):
                                if self.verbose:
                                    print(f"Skipping duplicate measurement for {reg_map[op.operands[0]].name}")
                            else:
                                raise

                else:
                    raise NotImplementedError(f"Unsupported op {op.name}")

        self.circuit = qc


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

    astJsonGen(input_dir="c_code")
    input_json = sys.argv[1] if len(sys.argv) > 1 else "json_out/try.json"
    pipeline = QuantumCircuitPipeline(json_path=input_json)
    pipeline.run_dataclass()
    pipeline.run_generate_ir()
    pipeline.run_generate_quantum_ir()
    pipeline.run_generate_circuit()
    pipeline.export_qasm()


if __name__ == "__main__":
    main()
