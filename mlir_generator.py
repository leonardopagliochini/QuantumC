# =============================================================================
# MLIR Generator
# =============================================================================

from __future__ import annotations

from xdsl.ir import Block, Region, SSAValue
from xdsl.dialects.builtin import i32
from xdsl.dialects.func import FuncOp, ReturnOp
from xdsl.dialects.arith import ConstantOp, AddiOp, SubiOp, MuliOp, DivSIOp


from c_ast import (
    Expression,
    IntegerLiteral,
    DeclRef,
    BinaryOperator,
    BinaryOperatorWithImmediate,
    VarDecl,
    AssignStmt,
    ReturnStmt,
    FunctionDecl,
)
from dialect_ops import AddiImmOp, SubiImmOp, MuliImmOp, DivSImmOp


# -----------------------------------------------------------------------------
# Generator Class
# -----------------------------------------------------------------------------

class MLIRGenerator:
    """Translate the dataclass AST into xDSL operations."""

    def __init__(self) -> None:
        self.symbol_table: dict[str, SSAValue | None] = {}
        self.current_block: Block | None = None

    # ------------------------------------------------------------------
    def process_expression(self, expr: Expression) -> SSAValue:
        """Recursively convert an expression to IR."""
        if isinstance(expr, IntegerLiteral):
            op = ConstantOp.from_int_and_width(expr.value, 32)
            self.current_block.add_op(op)
            return op.results[0]

        if isinstance(expr, DeclRef):
            if expr.name not in self.symbol_table or self.symbol_table[expr.name] is None:
                raise ValueError(f"Use of undeclared or uninitialized variable '{expr.name}'")
            return self.symbol_table[expr.name]

        if isinstance(expr, BinaryOperator):
            lhs_val = self.process_expression(expr.lhs)
            rhs_val = self.process_expression(expr.rhs)

            op_map = {
                '+': AddiOp,
                '-': SubiOp,
                '*': MuliOp,
                '/': DivSIOp,
            }
            op_cls = op_map.get(expr.opcode)
            if op_cls is None:
                raise ValueError(f"Unsupported binary operator: {expr.opcode}")
            op = op_cls(lhs_val, rhs_val)
            self.current_block.add_op(op)
            return op.results[0]

        if isinstance(expr, BinaryOperatorWithImmediate):
            if isinstance(expr.lhs, IntegerLiteral):
                imm = expr.lhs.value
                lhs_val = self.process_expression(expr.rhs)
            else:
                imm = expr.rhs.value
                lhs_val = self.process_expression(expr.lhs)

            op_map = {
                '+': AddiImmOp,
                '-': SubiImmOp,
                '*': MuliImmOp,
                '/': DivSImmOp,
            }
            op_cls = op_map.get(expr.opcode)
            if op_cls is None:
                raise ValueError(f"Unsupported binary operator with immediate: {expr.opcode}")
            op = op_cls(lhs_val, imm)
            self.current_block.add_op(op)
            return op.results[0]

        raise TypeError(f"Unsupported expression type: {type(expr)}")

    # ------------------------------------------------------------------
    def generate_function(self, func: FunctionDecl) -> FuncOp:
        """Convert a function declaration into MLIR."""
        block = Block()
        self.current_block = block
        self.symbol_table.clear()

        for stmt in func.body.stmts:
            if isinstance(stmt, VarDecl):
                if stmt.init:
                    op = self.process_expression(stmt.init)
                    self.symbol_table[stmt.name] = op
                else:
                    self.symbol_table[stmt.name] = None
            elif isinstance(stmt, AssignStmt):
                value_op = self.process_expression(stmt.value)
                self.symbol_table[stmt.name] = value_op
            elif isinstance(stmt, ReturnStmt):
                if stmt.value:
                    result_op = self.process_expression(stmt.value)
                    ret = ReturnOp(result_op)
                else:
                    ret = ReturnOp([])
                self.current_block.add_op(ret)

        func_type = ([i32] * len(func.params), [i32])
        return FuncOp(func.name, func_type, Region([block]))

