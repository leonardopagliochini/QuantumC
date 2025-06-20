"""Quantum friendly pipeline using custom MLIR dialect."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Optional, ClassVar

from xdsl.ir import Block, Region, SSAValue, Attribute
from xdsl.dialects.builtin import ModuleOp, IntegerAttr, i32, IntegerType, IndexType, AnyOf
from xdsl.dialects.func import FuncOp, ReturnOp
from xdsl.irdl import (
    IRDLOperation,
    irdl_op_definition,
    VarConstraint,
    operand_def,
    result_def,
    prop_def,
    traits_def,
)
from xdsl.traits import Pure
from xdsl.printer import Printer

from c_ast import (
    TranslationUnit,
    FunctionDecl,
    VarDecl,
    AssignStmt,
    ReturnStmt,
    Expression,
    IntegerLiteral,
    DeclRef,
    BinaryOperator,
    BinaryOperatorWithImmediate,
    parse_ast,
    pretty_print_translation_unit,
)

# ===========================================================================
# Dialect Definitions
# ===========================================================================

signlessIntegerLike = AnyOf([IntegerType, IndexType])


@irdl_op_definition
class QInitOp(IRDLOperation):
    """Initialize a quantum register to a classical value."""

    name = "quantum.init"

    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    value = prop_def(IntegerAttr)
    result = result_def(T)

    assembly_format = "attr-dict $value `:` type($result)"

    def __init__(self, value: int | IntegerAttr, result_type: Attribute = i32):
        if isinstance(value, int):
            value = IntegerAttr(value, result_type)
        super().__init__(result_types=[result_type], properties={"value": value})


@irdl_op_definition
class QBinaryOp(IRDLOperation):
    """Base class for quantum binary operations."""

    name = "quant.binary"

    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    lhs = operand_def(T)
    rhs = operand_def(T)
    result = result_def(T)

    traits = traits_def(Pure())

    def __init__(self, lhs: SSAValue, rhs: SSAValue):
        super().__init__(operands=[lhs, rhs], result_types=[lhs.type])


@irdl_op_definition
class QAddOp(QBinaryOp):
    name = "quant.add"
    assembly_format = "$lhs `,` $rhs attr-dict `:` type($result)"


@irdl_op_definition
class QSubOp(QBinaryOp):
    name = "quant.sub"
    assembly_format = "$lhs `,` $rhs attr-dict `:` type($result)"


@irdl_op_definition
class QMulOp(QBinaryOp):
    name = "quant.mul"
    assembly_format = "$lhs `,` $rhs attr-dict `:` type($result)"


@irdl_op_definition
class QDivOp(QBinaryOp):
    name = "quant.div"
    assembly_format = "$lhs `,` $rhs attr-dict `:` type($result)"


@irdl_op_definition
class QBinaryImmOp(IRDLOperation):
    """Binary op with immediate that overwrites its operand."""

    name = "quant.binary_imm"

    T: ClassVar = VarConstraint("T", signlessIntegerLike)
    lhs = operand_def(T)
    result = result_def(T)
    imm = prop_def(IntegerAttr)

    traits = traits_def(Pure())

    def __init__(self, lhs: SSAValue, imm: int | IntegerAttr):
        if isinstance(imm, int):
            imm = IntegerAttr(imm, lhs.type)
        super().__init__(operands=[lhs], result_types=[lhs.type], properties={"imm": imm})


@irdl_op_definition
class QAddiOp(QBinaryImmOp):
    name = "quant.addi"
    assembly_format = "$lhs `,` $imm attr-dict `:` type($result)"


@irdl_op_definition
class QSubiOp(QBinaryImmOp):
    name = "quant.subi"
    assembly_format = "$lhs `,` $imm attr-dict `:` type($result)"


@irdl_op_definition
class QMuliOp(QBinaryImmOp):
    name = "quant.muli"
    assembly_format = "$lhs `,` $imm attr-dict `:` type($result)"


@irdl_op_definition
class QDiviOp(QBinaryImmOp):
    name = "quant.divi"
    assembly_format = "$lhs `,` $imm attr-dict `:` type($result)"



# ===========================================================================
# IR Generation Utilities
# ===========================================================================

@dataclass
class ValueInfo:
    value: SSAValue
    var: Optional[str] = None


class QuantumMLIRGenerator:
    """Generate quantum-friendly MLIR operations."""

    def __init__(self):
        self.symbol_table: Dict[str, SSAValue | None] = {}
        self.expr_table: Dict[str, Expression | None] = {}
        self.use_counts: Dict[str, int] = {}
        self.block: Block | None = None
        self.in_recompute = False

    # ------------------------------------------------------------------
    def collect_use_counts(self, func: FunctionDecl) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)

        def visit(expr: Expression):
            if isinstance(expr, DeclRef):
                counts[expr.name] += 1
            elif isinstance(expr, BinaryOperator):
                visit(expr.lhs)
                visit(expr.rhs)
            elif isinstance(expr, BinaryOperatorWithImmediate):
                if isinstance(expr.lhs, IntegerLiteral):
                    visit(expr.rhs)
                else:
                    visit(expr.lhs)

        for stmt in func.body.stmts:
            if isinstance(stmt, VarDecl) and stmt.init:
                visit(stmt.init)
            elif isinstance(stmt, AssignStmt):
                visit(stmt.value)
            elif isinstance(stmt, ReturnStmt) and stmt.value:
                visit(stmt.value)
        return counts

    def expr_cost(
        self, expr: Expression | None, visited: Optional[set[str]] | None = None
    ) -> int:
        """Estimate the cost to compute an expression.

        A simple recursive heuristic is used. To avoid infinite recursion on
        self-referential assignments (e.g. ``x = x + 1``) we keep track of the
        variables that have already been visited while computing the cost.
        """

        if visited is None:
            visited = set()

        if expr is None:
            return 0
        if isinstance(expr, IntegerLiteral):
            return 1
        if isinstance(expr, DeclRef):
            if expr.name in visited:
                return 0
            visited.add(expr.name)
            cost = self.expr_cost(self.expr_table.get(expr.name), visited)
            visited.remove(expr.name)
            return cost
        if isinstance(expr, BinaryOperator):
            return 1 + self.expr_cost(expr.lhs, visited) + self.expr_cost(expr.rhs, visited)
        if isinstance(expr, BinaryOperatorWithImmediate):
            if isinstance(expr.lhs, IntegerLiteral):
                return 1 + self.expr_cost(expr.rhs, visited)
            else:
                return 1 + self.expr_cost(expr.lhs, visited)
        return 0

    # ------------------------------------------------------------------
    def recompute_variable(self, name: str) -> ValueInfo:
        expr = self.expr_table.get(name)
        if expr is None:
            raise ValueError(f"Variable '{name}' used before initialization")
        was = self.in_recompute
        self.in_recompute = True
        val = self._process_expression(expr, name)
        self.in_recompute = was
        self.symbol_table[name] = val.value
        return val

    def _process_expression(self, expr: Expression, target_var: Optional[str] = None) -> ValueInfo:
        if isinstance(expr, IntegerLiteral):
            op = QInitOp(expr.value, i32)
            self.block.add_op(op)
            return ValueInfo(op.results[0])

        if isinstance(expr, DeclRef):
            if not self.in_recompute:
                self.use_counts[expr.name] -= 1
            val = self.symbol_table.get(expr.name)
            if val is None:
                val = self.recompute_variable(expr.name).value
            return ValueInfo(val, expr.name)

        if isinstance(expr, BinaryOperator):
            lhs = self._process_expression(expr.lhs, target_var)
            rhs = self._process_expression(expr.rhs, target_var)

            lhs_use = self.use_counts.get(lhs.var, 0) if lhs.var else 0
            rhs_use = self.use_counts.get(rhs.var, 0) if rhs.var else 0

            if lhs.var is None:
                chosen, other = rhs, lhs
            elif rhs.var is None:
                chosen, other = lhs, rhs
            else:
                if lhs_use == 0:
                    chosen, other = lhs, rhs
                elif rhs_use == 0:
                    chosen, other = rhs, lhs
                else:
                    lhs_cost = self.expr_cost(self.expr_table.get(lhs.var))
                    rhs_cost = self.expr_cost(self.expr_table.get(rhs.var))
                    if lhs_cost <= rhs_cost:
                        chosen, other = lhs, rhs
                    else:
                        chosen, other = rhs, lhs

            if expr.opcode == '+':
                op = QAddOp(chosen.value, other.value)
            elif expr.opcode == '-':
                op = QSubOp(chosen.value, other.value)
            elif expr.opcode == '*':
                op = QMulOp(chosen.value, other.value)
            elif expr.opcode == '/':
                op = QDivOp(chosen.value, other.value)
            else:
                raise ValueError(f"Unsupported op {expr.opcode}")

            self.block.add_op(op)
            result = ValueInfo(op.results[0])

            if chosen.var and not self.in_recompute and chosen.var != target_var:
                if self.use_counts.get(chosen.var, 0) > 0:
                    self.symbol_table[chosen.var] = None
                    self.recompute_variable(chosen.var)
                else:
                    self.symbol_table[chosen.var] = None
            return result

        if isinstance(expr, BinaryOperatorWithImmediate):
            if isinstance(expr.lhs, IntegerLiteral):
                imm = expr.lhs.value
                lhs = self._process_expression(expr.rhs, target_var)
            else:
                imm = expr.rhs.value
                lhs = self._process_expression(expr.lhs, target_var)

            op_cls = {
                '+': QAddiOp,
                '-': QSubiOp,
                '*': QMuliOp,
                '/': QDiviOp,
            }.get(expr.opcode)
            if op_cls is None:
                raise ValueError(f"Unsupported op {expr.opcode}")

            op = op_cls(lhs.value, imm)
            self.block.add_op(op)
            result = ValueInfo(op.results[0])

            if lhs.var and not self.in_recompute and lhs.var != target_var:
                if self.use_counts.get(lhs.var, 0) > 0:
                    self.symbol_table[lhs.var] = None
                    self.recompute_variable(lhs.var)
                else:
                    self.symbol_table[lhs.var] = None
            return result

        raise TypeError(f"Unsupported expression type {type(expr)}")

    def process_expression(
        self, expr: Expression, target_var: Optional[str] = None
    ) -> ValueInfo:
        """Process an expression, optionally knowing the variable being defined."""
        return self._process_expression(expr, target_var)

    # ------------------------------------------------------------------
    def generate_function(self, func: FunctionDecl) -> FuncOp:
        self.block = Block()
        self.symbol_table.clear()
        self.expr_table.clear()
        self.use_counts = self.collect_use_counts(func)

        for stmt in func.body.stmts:
            if isinstance(stmt, VarDecl):
                self.expr_table[stmt.name] = stmt.init
                if stmt.init:
                    val = self.process_expression(stmt.init, stmt.name)
                    self.symbol_table[stmt.name] = val.value
                else:
                    self.symbol_table[stmt.name] = None
            elif isinstance(stmt, AssignStmt):
                self.expr_table[stmt.name] = stmt.value
                val = self.process_expression(stmt.value, stmt.name)
                self.symbol_table[stmt.name] = val.value
            elif isinstance(stmt, ReturnStmt):
                if stmt.value:
                    val = self.process_expression(stmt.value)
                    ret = ReturnOp(val.value)
                else:
                    ret = ReturnOp([])
                self.block.add_op(ret)

        func_type = ([i32] * len(func.params), [i32])
        return FuncOp(func.name, func_type, Region([self.block]))


# ===========================================================================
# Pipeline Driver
# ===========================================================================

class QuantumPipeline:
    """End-to-end pipeline producing quantum-friendly MLIR."""

    def __init__(self, json_path: str = "json_out/try.json"):
        self.json_path = json_path
        self.root: TranslationUnit | None = None
        self.module: ModuleOp | None = None

    def run_dataclass(self) -> None:
        with open(self.json_path) as f:
            ast_json = json.load(f)
        self.root = parse_ast(ast_json)

    def pretty_print_source(self) -> None:
        if self.root is None:
            raise RuntimeError("run_dataclass first")
        print(pretty_print_translation_unit(self.root))

    def run_generate_ir(self) -> None:
        if self.root is None:
            raise RuntimeError("run_dataclass first")
        gen = QuantumMLIRGenerator()
        self.module = ModuleOp([])
        for func in self.root.decls:
            op = gen.generate_function(func)
            self.module.regions[0].blocks[0].add_op(op)

    def visualize_ir(self) -> None:
        if self.module is None:
            raise RuntimeError("run_generate_ir first")
        Printer().print_op(self.module)
        print()


if __name__ == "__main__":
    import sys

    try:
        input_json = sys.argv[1] if len(sys.argv) > 1 else "json_out/try.json"
        pipeline = QuantumPipeline(json_path=input_json)
        pipeline.run_dataclass()
        pipeline.pretty_print_source()
        pipeline.run_generate_ir()
        pipeline.visualize_ir()
    except Exception as e:
        print("Error:", e)
        raise