"""Check that classical and quantum MLIR evaluate to the same result."""

from __future__ import annotations

import glob
from typing import Any

from xdsl.interpreter import Interpreter, InterpreterFunctions, impl, register_impls
from xdsl.interpreters.func import FuncFunctions
from xdsl.interpreters.arith import ArithFunctions
from xdsl.interpreters.builtin import BuiltinFunctions
from xdsl.dialects.builtin import Builtin
from xdsl.dialects.func import Func
from xdsl.dialects.arith import Arith
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
)
from pipeline import QuantumIR


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
            ],
        )


@register_impls
class CustomFunctions(InterpreterFunctions):
    @impl(AddiImmOp)
    def run_addi_imm(self, interpreter: Interpreter, op: AddiImmOp, args: tuple[Any, ...]):
        return (args[0] + op.imm.value.data,)

    @impl(SubiImmOp)
    def run_subi_imm(self, interpreter: Interpreter, op: SubiImmOp, args: tuple[Any, ...]):
        return (args[0] - op.imm.value.data,)

    @impl(MuliImmOp)
    def run_muli_imm(self, interpreter: Interpreter, op: MuliImmOp, args: tuple[Any, ...]):
        return (args[0] * op.imm.value.data,)

    @impl(DivSImmOp)
    def run_divs_imm(self, interpreter: Interpreter, op: DivSImmOp, args: tuple[Any, ...]):
        imm = op.imm.value.data
        return (None if imm == 0 else args[0] // imm,)

    @impl(QuantumInitOp)
    def run_qinit(self, interpreter: Interpreter, op: QuantumInitOp, args: tuple[Any, ...]):
        return (op.value.value.data,)

    @impl(QAddiOp)
    def run_qaddi(self, interpreter: Interpreter, op: QAddiOp, args: tuple[Any, ...]):
        return (args[0] + args[1],)

    @impl(QSubiOp)
    def run_qsubi(self, interpreter: Interpreter, op: QSubiOp, args: tuple[Any, ...]):
        return (args[0] - args[1],)

    @impl(QMuliOp)
    def run_qmuli(self, interpreter: Interpreter, op: QMuliOp, args: tuple[Any, ...]):
        return (args[0] * args[1],)

    @impl(QDivSOp)
    def run_qdivs(self, interpreter: Interpreter, op: QDivSOp, args: tuple[Any, ...]):
        rhs = args[1]
        return (args[0] // rhs if rhs != 0 else None,)

    @impl(QAddiImmOp)
    def run_qaddi_imm(self, interpreter: Interpreter, op: QAddiImmOp, args: tuple[Any, ...]):
        return (args[0] + op.imm.value.data,)

    @impl(QSubiImmOp)
    def run_qsubi_imm(self, interpreter: Interpreter, op: QSubiImmOp, args: tuple[Any, ...]):
        return (args[0] - op.imm.value.data,)

    @impl(QMuliImmOp)
    def run_qmuli_imm(self, interpreter: Interpreter, op: QMuliImmOp, args: tuple[Any, ...]):
        return (args[0] * op.imm.value.data,)

    @impl(QDivSImmOp)
    def run_qdivs_imm(self, interpreter: Interpreter, op: QDivSImmOp, args: tuple[Any, ...]):
        imm = op.imm.value.data
        return (None if imm == 0 else args[0] // imm,)


def run_module(module) -> Any:
    interpreter = Interpreter(module)
    interpreter.register_implementations(FuncFunctions())
    interpreter.register_implementations(ArithFunctions())
    interpreter.register_implementations(BuiltinFunctions())
    interpreter.register_implementations(CustomFunctions())
    result = interpreter.call_op("main", ())
    return result[0] if result else None


def compare(path: str) -> None:
    pipeline = QuantumIR(json_path=path)
    pipeline.run_dataclass()
    pipeline.run_generate_ir()
    classical = pipeline.module
    pipeline.run_generate_quantum_ir()
    quantum = pipeline.quantum_module

    classical_res = run_module(classical)
    quantum_res = run_module(quantum)
    print(f"{path}: classical={classical_res}, quantum={quantum_res}")
    assert classical_res == quantum_res


if __name__ == "__main__":
    # Only check the example program used in the README to keep execution
    # time reasonable.
    compare("json_out/try.json")

