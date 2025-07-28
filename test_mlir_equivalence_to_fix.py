"""Execute saved MLIR files and compare classical and quantum results."""

from __future__ import annotations
import os
from typing import Any

from xdsl.context import Context
from xdsl.parser import Parser
from xdsl.interpreter import Interpreter, InterpreterFunctions, impl, register_impls
from xdsl.interpreters.func import FuncFunctions
from xdsl.interpreters.arith import ArithFunctions
from xdsl.interpreters.builtin import BuiltinFunctions
from xdsl.interpreters.cf import CfFunctions
from xdsl.dialects.builtin import Builtin
from xdsl.dialects.func import Func
from xdsl.dialects.arith import Arith, ExtUIOp
from xdsl.dialects.cf import Cf
from xdsl.ir import Dialect


from dialect_ops import AddiImmOp, SubiImmOp, MuliImmOp, DivSImmOp
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
    QAndOp,
    QNotOp,
    QCmpiOp,
    QuantumCInitOp,
    CQAddiOp,
    CQSubiOp,
    CQMuliOp,
    CQDivSOp,
    CQAddiImmOp,
    CQSubiImmOp,
    CQMuliImmOp,
    CQDivSImmOp,
)


class MyDialect(Dialect):
    def __init__(self) -> None:
        super().__init__("mydialect", [AddiImmOp, SubiImmOp, MuliImmOp, DivSImmOp])


class QuantumDialect(Dialect):
    def __init__(self) -> None:
        super().__init__(
            "quant",
            [
                QuantumInitOp,
                QAddiOp,
                QSubiOp,
                QMuliOp,
                QDivSOp,
                QAddiImmOp,
                QSubiImmOp,
                QMuliImmOp,
                QDivSImmOp,
                QAndOp,
                QNotOp,
                QCmpiOp,
                QuantumCInitOp,
                CQAddiOp,
                CQSubiOp,
                CQMuliOp,
                CQDivSOp,
                CQAddiImmOp,
                CQSubiImmOp,
                CQMuliImmOp,
                CQDivSImmOp,
            ],
        )


@register_impls
class CustomFunctions(InterpreterFunctions):
    @impl(AddiImmOp)
    def run_addi_imm(self, _, op, args): return (args[0] + op.imm.value.data,)
    @impl(SubiImmOp)
    def run_subi_imm(self, _, op, args): return (args[0] - op.imm.value.data,)
    @impl(MuliImmOp)
    def run_muli_imm(self, _, op, args): return (args[0] * op.imm.value.data,)
    @impl(DivSImmOp)
    def run_divs_imm(self, _, op, args): return (None if op.imm.value.data == 0 else args[0] // op.imm.value.data,)

    @impl(QuantumInitOp)
    def run_qinit(self, _, op, __): return (op.value.value.data,)
    @impl(QAddiOp)
    def run_qaddi(self, _, __, args): return (args[0] + args[1],)
    @impl(QSubiOp)
    def run_qsubi(self, _, __, args): return (args[0] - args[1],)
    @impl(QMuliOp)
    def run_qmuli(self, _, __, args): return (args[0] * args[1],)
    @impl(QDivSOp)
    def run_qdivs(self, _, __, args): return (args[0] // args[1] if args[1] != 0 else None,)
    @impl(QAddiImmOp)
    def run_qaddi_imm(self, _, op, args): return (args[0] + op.imm.value.data,)
    @impl(QSubiImmOp)
    def run_qsubi_imm(self, _, op, args): return (args[0] - op.imm.value.data,)
    @impl(QMuliImmOp)
    def run_qmuli_imm(self, _, op, args): return (args[0] * op.imm.value.data,)
    @impl(QDivSImmOp)
    def run_qdivs_imm(self, _, op, args): return (None if op.imm.value.data == 0 else args[0] // op.imm.value.data,)
    @impl(QAndOp)
    def run_and(self, _, __, args): return (int(bool(args[0]) and bool(args[1])),)
    @impl(QNotOp)
    def run_not(self, _, __, args): return (int(not bool(args[0])),)
    @impl(ExtUIOp)
    def run_extui(self, _, __, args): return (int(args[0]),)
    @impl(CQAddiImmOp)
    def run_cqaddi_imm(self, _, op, args):
        lhs, ctrl = args
        return (lhs + op.imm.value.data if ctrl else lhs,)
    @impl(CQSubiImmOp)
    def run_cqsubi_imm(self, _, op, args):
        lhs, ctrl = args
        return (lhs - op.imm.value.data if ctrl else lhs,)
    @impl(CQMuliImmOp)
    def run_cqmuli_imm(self, _, op, args):
        lhs, ctrl = args
        return (lhs * op.imm.value.data if ctrl else lhs,)
    @impl(CQDivSImmOp)
    def run_cqdivs_imm(self, _, op, args):
        lhs, ctrl = args
        return (lhs // op.imm.value.data if ctrl and op.imm.value.data != 0 else lhs,)
    @impl(QCmpiOp)
    def run_cmp(self, _, op, args):
        lhs, rhs = args
        pred = op.predicate.value.data
        match pred:
            case 0: return (int(lhs == rhs),)
            case 1: return (int(lhs != rhs),)
            case 2: return (int(lhs < rhs),)
            case 3: return (int(lhs <= rhs),)
            case 4: return (int(lhs > rhs),)
            case 5: return (int(lhs >= rhs),)
            case _: raise ValueError(f"Unknown predicate {pred}")
    @impl(QuantumCInitOp)
    def run_cinit(self, _, op, args): return (op.value.value.data if args[0] else 0,)


def run_module(path: str) -> Any:
    ctx = Context()
    ctx.load_dialect(Builtin)
    ctx.load_dialect(Func)
    ctx.load_dialect(Arith)
    ctx.load_dialect(Cf)
    ctx.load_dialect(MyDialect())
    ctx.load_dialect(QuantumDialect())

    with open(path) as f:
        program = f.read()
    module = Parser(ctx, program).parse_module()
    interpreter = Interpreter(module)
    interpreter.register_implementations(FuncFunctions())
    interpreter.register_implementations(ArithFunctions())
    interpreter.register_implementations(BuiltinFunctions())
    interpreter.register_implementations(CfFunctions())
    interpreter.register_implementations(CustomFunctions())

    result = interpreter.call_op("main", ())
    return result[0] if result else None


def compare_all(out_dir: str = "mlir_out") -> None:
    for file in sorted(os.listdir(out_dir)):
        if not file.endswith("_classical.mlir"):
            continue
        base = file.replace("_classical.mlir", "")
        classical_path = os.path.join(out_dir, file)
        quantum_path = os.path.join(out_dir, f"{base}_quantum.mlir")
        classical_res = run_module(classical_path)
        quantum_res = run_module(quantum_path)
        print(f"{base}: classical={classical_res}, quantum={quantum_res}")
        assert classical_res == quantum_res, f"Mismatch in {base}"


if __name__ == "__main__":
    compare_all()
