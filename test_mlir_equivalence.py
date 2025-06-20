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


class MyDialect(Dialect):
    """Dialect bundling arithmetic ops with immediates."""

    def __init__(self) -> None:
        super().__init__("mydialect", [AddiImmOp, SubiImmOp, MuliImmOp, DivSImmOp])


class QuantumDialect(Dialect):
    """Dialect for quantum operations."""

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
    """Interpreter implementations for custom operations."""

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


def run_module(path: str) -> Any:
    """Parse and execute the MLIR module at ``path``."""
    ctx = Context()
    ctx.load_dialect(Builtin)
    ctx.load_dialect(Func)
    ctx.load_dialect(Arith)
    ctx.load_dialect(MyDialect())
    ctx.load_dialect(QuantumDialect())

    with open(path) as f:
        program = f.read()
    module = Parser(ctx, program).parse_module()
    interpreter = Interpreter(module)
    interpreter.register_implementations(FuncFunctions())
    interpreter.register_implementations(ArithFunctions())
    interpreter.register_implementations(BuiltinFunctions())
    interpreter.register_implementations(CustomFunctions())
    result = interpreter.call_op("main", ())
    return result[0] if result else None


def compare_all(out_dir: str = "mlir_out") -> None:
    """Run classical and quantum MLIR files and compare their results."""
    for file in sorted(os.listdir(out_dir)):
        if not file.endswith("_classical.mlir"):
            continue
        base = file.replace("_classical.mlir", "")
        classical_path = os.path.join(out_dir, file)
        quantum_path = os.path.join(out_dir, f"{base}_quantum.mlir")
        classical_res = run_module(classical_path)
        quantum_res = run_module(quantum_path)
        print(f"{base}: classical={classical_res}, quantum={quantum_res}")
        assert classical_res == quantum_res


if __name__ == "__main__":
    compare_all()