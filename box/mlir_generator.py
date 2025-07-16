# =============================================================================
# MLIR Generator
# =============================================================================

"""Convert a simple C-like AST into MLIR using xDSL.

This module walks over the dataclass representation defined in ``c_ast`` and
creates the equivalent MLIR using the xDSL Python API.  The generated module can
then be further processed or translated to the custom quantum dialect.
"""

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
    """Translate the dataclass AST into xDSL operations.

    Instances of this class walk over the front-end dataclasses defined in
    ``c_ast`` and emit the corresponding xDSL operations.  The generator keeps
    track of declared variables in a symbol table so that expressions can be
    lowered in a single pass.
    """

    def __init__(self) -> None:
        """Initialize generator state."""
        # ``symbol_table`` maps variable names to the SSA value holding their
        # current contents. ``None`` denotes a declared-but-uninitialized
        # variable.
        self.symbol_table: dict[str, SSAValue | None] = {}

        # ``current_block`` is the block currently being populated with
        # operations for the function under construction.
        self.current_block: Block | None = None

    # ------------------------------------------------------------------
    def process_expression(self, expr: Expression) -> SSAValue:
        """Recursively convert an expression to MLIR operations.

        Parameters
        ----------
        expr:
            Expression node to lower.

        Returns
        -------
        SSAValue
            The SSA value produced by the generated operations.
        """
        if isinstance(expr, IntegerLiteral):
            # Lower integer constants to ``arith.constant`` operations.
            op = ConstantOp.from_int_and_width(expr.value, 32)
            self.current_block.add_op(op)
            return op.results[0]

        if isinstance(expr, DeclRef):
            # Load the SSA value associated with the variable from the symbol table.
            if expr.name not in self.symbol_table or self.symbol_table[expr.name] is None:
                raise ValueError(f"Use of undeclared or uninitialized variable '{expr.name}'")
            return self.symbol_table[expr.name]

        if isinstance(expr, BinaryOperator):
            # Recursively lower both sides of the binary operator.
            lhs_val = self.process_expression(expr.lhs)
            rhs_val = self.process_expression(expr.rhs)

            # Map from the opcode string to the concrete MLIR operation class.
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
            # Identify which side of the expression is the immediate.
            if isinstance(expr.lhs, IntegerLiteral):
                imm = expr.lhs.value
                lhs_val = self.process_expression(expr.rhs)
            else:
                imm = expr.rhs.value
                lhs_val = self.process_expression(expr.lhs)

            # Choose the appropriate immediate operation.
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
        """Convert a :class:`FunctionDecl` into MLIR.

        Parameters
        ----------
        func:
            Dataclass describing the function to be lowered.

        Returns
        -------
        FuncOp
            The xDSL function operation implementing ``func``.
        """
        block = Block()
        self.current_block = block
        self.symbol_table.clear()

        # Lower each statement in the function body in order.
        for stmt in func.body.stmts:
            if isinstance(stmt, VarDecl):
                # Variable declaration, possibly with initializer.
                if stmt.init:
                    op = self.process_expression(stmt.init)
                    self.symbol_table[stmt.name] = op
                else:
                    self.symbol_table[stmt.name] = None
            elif isinstance(stmt, AssignStmt):
                # Assignment updates the variable's SSA value.
                value_op = self.process_expression(stmt.value)
                self.symbol_table[stmt.name] = value_op
            elif isinstance(stmt, ReturnStmt):
                # Return statements translate to a ``func.return`` op.
                if stmt.value:
                    result_op = self.process_expression(stmt.value)
                    ret = ReturnOp(result_op)
                else:
                    ret = ReturnOp([])
                self.current_block.add_op(ret)

        func_type = ([i32] * len(func.params), [i32])
        return FuncOp(func.name, func_type, Region([block]))

