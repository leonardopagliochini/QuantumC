"""Check that classical MLIR and write-in-place MLIR compute the same result."""

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
    """Dialect registering the immediate arithmetic operations."""

    def __init__(self) -> None:
        """Register the custom arithmetic ops used by the interpreter."""
        super().__init__("mydialect", [AddiImmOp, SubiImmOp, MuliImmOp, DivSImmOp])


class QuantumDialect(Dialect):
    """Dialect containing all quantum operations needed for testing."""

    def __init__(self) -> None:
        """Register the operations of the quantum dialect."""
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
    """Interpreter implementations for the custom operations."""
    @impl(AddiImmOp)
    def run_addi_imm(self, interpreter: Interpreter, op: AddiImmOp, args: tuple[Any, ...]):
        """Execute :class:`AddiImmOp` by performing the integer addition."""
        return (args[0] + op.imm.value.data,)

    @impl(SubiImmOp)
    def run_subi_imm(self, interpreter: Interpreter, op: SubiImmOp, args: tuple[Any, ...]):
        """Execute :class:`SubiImmOp`."""
        return (args[0] - op.imm.value.data,)

    @impl(MuliImmOp)
    def run_muli_imm(self, interpreter: Interpreter, op: MuliImmOp, args: tuple[Any, ...]):
        """Execute :class:`MuliImmOp`."""
        return (args[0] * op.imm.value.data,)

    @impl(DivSImmOp)
    def run_divs_imm(self, interpreter: Interpreter, op: DivSImmOp, args: tuple[Any, ...]):
        """Execute :class:`DivSImmOp` with zero-check."""
        imm = op.imm.value.data
        return (None if imm == 0 else args[0] // imm,)

    @impl(QuantumInitOp)
    def run_qinit(self, interpreter: Interpreter, op: QuantumInitOp, args: tuple[Any, ...]):
        """Initialize a quantum register with a constant value."""
        return (op.value.value.data,)

    @impl(QAddiOp)
    def run_qaddi(self, interpreter: Interpreter, op: QAddiOp, args: tuple[Any, ...]):
        """Quantum addition of two registers."""
        return (args[0] + args[1],)

    @impl(QSubiOp)
    def run_qsubi(self, interpreter: Interpreter, op: QSubiOp, args: tuple[Any, ...]):
        """Quantum subtraction."""
        return (args[0] - args[1],)

    @impl(QMuliOp)
    def run_qmuli(self, interpreter: Interpreter, op: QMuliOp, args: tuple[Any, ...]):
        """Quantum multiplication."""
        return (args[0] * args[1],)

    @impl(QDivSOp)
    def run_qdivs(self, interpreter: Interpreter, op: QDivSOp, args: tuple[Any, ...]):
        """Quantum signed division with zero check."""
        rhs = args[1]
        return (args[0] // rhs if rhs != 0 else None,)

    @impl(QAddiImmOp)
    def run_qaddi_imm(self, interpreter: Interpreter, op: QAddiImmOp, args: tuple[Any, ...]):
        """Quantum addition with immediate."""
        return (args[0] + op.imm.value.data,)

    @impl(QSubiImmOp)
    def run_qsubi_imm(self, interpreter: Interpreter, op: QSubiImmOp, args: tuple[Any, ...]):
        """Quantum subtraction with immediate."""
        return (args[0] - op.imm.value.data,)

    @impl(QMuliImmOp)
    def run_qmuli_imm(self, interpreter: Interpreter, op: QMuliImmOp, args: tuple[Any, ...]):
        """Quantum multiplication with immediate."""
        return (args[0] * op.imm.value.data,)

    @impl(QDivSImmOp)
    def run_qdivs_imm(self, interpreter: Interpreter, op: QDivSImmOp, args: tuple[Any, ...]):
        """Quantum division with immediate and zero check."""
        imm = op.imm.value.data
        return (None if imm == 0 else args[0] // imm,)


def run_module(module) -> Any:
    """Execute ``main`` of the given module using the interpreter."""
    interpreter = Interpreter(module)
    interpreter.register_implementations(FuncFunctions())
    interpreter.register_implementations(ArithFunctions())
    interpreter.register_implementations(BuiltinFunctions())
    interpreter.register_implementations(CustomFunctions())
    result = interpreter.call_op("main", ())
    return result[0] if result else None


def compare(path: str) -> None:
    """Run the full pipeline on ``path`` and assert both versions agree."""
    pipeline = QuantumIR(json_path=path)
    pipeline.run_dataclass()
    pipeline.run_generate_ir()
    classical = pipeline.module
    pipeline.run_enforce_write_in_place()
    wip_module = pipeline.write_in_place_module

    classical_res = run_module(classical)
    wip_res = run_module(wip_module)
    print(f"{path}: classical={classical_res}, write_in_place={wip_res}")
    assert classical_res == wip_res


if __name__ == "__main__":
    # Only check the example program used in the README to keep execution
    # time reasonable.
    compare("json_out/try.json")

