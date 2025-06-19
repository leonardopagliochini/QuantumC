import json
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union

from xdsl.ir import Block, Region
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp, IntegerAttr, i32
from xdsl.dialects.func import FuncOp
from xdsl.dialects.arith import ConstantOp, SubiOp, AddiOp, MuliOp, DivSIOp
from xdsl.printer import Printer

# === AST Classes ===

class Expression:
    pass

@dataclass
class IntegerLiteral(Expression):
    value: int

@dataclass
class DeclRef(Expression):
    name: str

@dataclass
class BinaryOperator(Expression):
    opcode: str
    lhs: Expression
    rhs: Expression

@dataclass
class BinaryOperatorWithImmediate(Expression):
    opcode: str
    lhs: Expression
    rhs: Expression

@dataclass
class VarDecl:
    name: str
    init: Optional[Expression] = None

@dataclass
class ReturnStmt:
    value: Optional[Expression] = None

@dataclass
class AssignStmt:
    name: str
    value: Expression

@dataclass
class CompoundStmt:
    stmts: List[Union[VarDecl, ReturnStmt, AssignStmt]] = field(default_factory=list)

@dataclass
class FunctionDecl:
    name: str
    body: CompoundStmt
    params: List[str] = field(default_factory=list)  # Optional for now

@dataclass
class TranslationUnit:
    decls: List[FunctionDecl] = field(default_factory=list)


# === Expression Parser ===

def parse_expression(expr_node: dict) -> Expression:
    kind = expr_node["kind"]

    # Skip implicit casts
    if kind == "ImplicitCastExpr":
        return parse_expression(expr_node["inner"][0])

    # Skip parentheses
    if kind == "ParenExpr":
        return parse_expression(expr_node["inner"][0])

    # Integer literal
    if kind == "IntegerLiteral":
        return IntegerLiteral(int(expr_node["value"]))

    # Variable reference
    elif kind == "DeclRefExpr":
        if "name" in expr_node:
            name = expr_node["name"]
        elif "referencedDecl" in expr_node and "name" in expr_node["referencedDecl"]:
            name = expr_node["referencedDecl"]["name"]
        else:
            raise ValueError(f"Cannot extract name from DeclRefExpr: {expr_node}")
        return DeclRef(name)

    # Binary operator
    elif kind == "BinaryOperator":
        opcode = expr_node["opcode"]
        inner_nodes = expr_node.get("inner", [])
        if len(inner_nodes) != 2:
            raise ValueError(f"BinaryOperator must have 2 children: {expr_node}")

        lhs_expr = parse_expression(inner_nodes[0])
        rhs_expr = parse_expression(inner_nodes[1])

        # Use a specialized class when one operand is an immediate
        if isinstance(lhs_expr, IntegerLiteral) ^ isinstance(rhs_expr, IntegerLiteral):
            return BinaryOperatorWithImmediate(opcode, lhs_expr, rhs_expr)
        else:
            return BinaryOperator(opcode, lhs_expr, rhs_expr)

    else:
        raise ValueError(f"Unsupported expression node: {kind}")



def parse_ast(ast_json: dict) -> TranslationUnit:
    tu = TranslationUnit()

    for decl in ast_json.get("inner", []):
        if decl["kind"] == "FunctionDecl":
            func_name = decl["name"]
            compound_stmt = None

            for inner in decl.get("inner", []):
                if inner["kind"] == "CompoundStmt":
                    compound_stmt = CompoundStmt()

                    for stmt in inner.get("inner", []):
                        # Variable declaration: int x = 1;
                        if stmt["kind"] == "DeclStmt":
                            for var_decl in stmt.get("inner", []):
                                if var_decl["kind"] == "VarDecl":
                                    init_expr = None
                                    if "inner" in var_decl and var_decl["inner"]:
                                        init_expr = parse_expression(var_decl["inner"][0])
                                    compound_stmt.stmts.append(
                                        VarDecl(var_decl["name"], init_expr)
                                    )

                        # Assignment: x = y + z;
                        elif stmt["kind"] == "BinaryOperator" and stmt["opcode"] == "=":
                            lhs = stmt["inner"][0]
                            rhs = stmt["inner"][1]

                            if lhs["kind"] == "DeclRefExpr":
                                var_name = lhs.get("name") or lhs.get("referencedDecl", {}).get("name")
                                if not var_name:
                                    raise ValueError("Cannot resolve variable name in assignment LHS")

                                rhs_expr = parse_expression(rhs)
                                compound_stmt.stmts.append(AssignStmt(var_name, rhs_expr))
                            else:
                                raise ValueError(f"Unsupported assignment LHS: {lhs['kind']}")

                        # Return: return x; or return;
                        elif stmt["kind"] == "ReturnStmt":
                            return_expr = None
                            if "inner" in stmt and stmt["inner"]:
                                return_expr = parse_expression(stmt["inner"][0])
                            compound_stmt.stmts.append(ReturnStmt(return_expr))

                        # Future support: skip or warn on other kinds
                        else:
                            # print(f"Skipping unsupported stmt: {stmt['kind']}")
                            pass

            if compound_stmt:
                tu.decls.append(FunctionDecl(func_name, compound_stmt))

    return tu

def pretty_print_translation_unit(tu: TranslationUnit) -> str:
    lines = []

    for func in tu.decls:
        params = ", ".join(f"int {p}" for p in func.params)
        lines.append(f'int {func.name}({params}) {{')
        for stmt in func.body.stmts:
            if isinstance(stmt, VarDecl):
                if stmt.init:
                    expr_str = pretty_print_expression(stmt.init)
                    lines.append(f"    int {stmt.name} = {expr_str};")
                else:
                    lines.append(f"    int {stmt.name};")
            elif isinstance(stmt, AssignStmt):
                expr_str = pretty_print_expression(stmt.value)
                lines.append(f"    {stmt.name} = {expr_str};")
            elif isinstance(stmt, ReturnStmt):
                if stmt.value:
                    expr_str = pretty_print_expression(stmt.value)
                    lines.append(f"    return {expr_str};")
                else:
                    lines.append(f"    return;")
        lines.append("}")
        lines.append("")  # blank line between functions

    return "\n".join(lines)

def pretty_print_expression(expr: Expression) -> str:
    if isinstance(expr, IntegerLiteral):
        return str(expr.value)
    elif isinstance(expr, DeclRef):
        return expr.name
    elif isinstance(expr, BinaryOperator):
        lhs = pretty_print_expression(expr.lhs)
        rhs = pretty_print_expression(expr.rhs)
        return f"({lhs} {expr.opcode} {rhs})"
    else:
        return "<unsupported_expr>"
    
from xdsl.ir import SSAValue, Attribute
from xdsl.dialects.builtin import IntegerAttr, i32
from xdsl.irdl import (
    irdl_op_definition,
    IRDLOperation,
    VarConstraint,
    operand_def,
    result_def,
    prop_def,
    traits_def,
)
from xdsl.traits import Pure
from xdsl.utils.exceptions import VerifyException
from xdsl.dialects.builtin import IntegerType, IndexType, AnyOf

from xdsl.dialects.arith import ClassVar
from xdsl.dialects.arith import IntegerOverflowAttr


# Match signless integer-like types
signlessIntegerLike = AnyOf([IntegerType, IndexType])

@irdl_op_definition
class SignlessIntegerBinaryOpWithImmediate(IRDLOperation):
    """
    Base class for binary integer ops where the right operand is an immediate literal.
    """

    name = "mydialect.binary_imm"

    T: ClassVar = VarConstraint("T", signlessIntegerLike)

    lhs = operand_def(T)
    result = result_def(T)
    imm = prop_def(IntegerAttr)

    traits = traits_def(Pure())

    assembly_format = "$lhs `,` $imm attr-dict `:` type($result)"

    def __init__(
        self,
        lhs: SSAValue,
        imm: int | IntegerAttr,
        result_type: Attribute | None = None
    ):
        if isinstance(imm, int):
            imm = IntegerAttr(imm, lhs.type)

        if result_type is None:
            result_type = lhs.type

        super().__init__(
            operands=[lhs],
            result_types=[result_type],
            properties={"imm": imm},
        )

    def verify_(self):
        if not isinstance(self.imm, IntegerAttr):
            raise VerifyException("Immediate must be an IntegerAttr")

        if self.lhs.type != self.imm.type:
            raise VerifyException(
                f"Operand and immediate must have matching types, "
                f"got {self.lhs.type} vs {self.imm.type}"
            )

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int | None:
        return None  # To be overridden in subclasses

    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        return False  # Override if your op has a zero absorbing element

    @staticmethod
    def is_right_unit(attr: IntegerAttr) -> bool:
        return False  # Override if your op has an identity element
    

@irdl_op_definition
class SignlessIntegerBinaryOpWithImmediateAndOverflow(SignlessIntegerBinaryOpWithImmediate):
    """
    Base class for immediate-operand integer binary ops that support overflow flags.
    """

    name = "mydialect.binary_imm_overflow"

    overflow_flags = prop_def(
        IntegerOverflowAttr,
        default_value=IntegerOverflowAttr("none"),
        prop_name="overflowFlags",
    )

    # Note: this extends the parent assembly format
    assembly_format = (
        "$lhs `,` $imm (`overflow` `` $overflowFlags^)? attr-dict `:` type($result)"
    )

    def __init__(
        self,
        lhs: SSAValue,
        imm: int | IntegerAttr,
        result_type: Attribute | None = None,
        overflow: IntegerOverflowAttr = IntegerOverflowAttr("none"),
    ):
        if isinstance(imm, int):
            imm = IntegerAttr(imm, lhs.type)
        if result_type is None:
            result_type = lhs.type

        super().__init__(lhs=lhs, imm=imm, result_type=result_type)
        self.properties["overflowFlags"] = overflow



@irdl_op_definition
class AddiImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    name = "mydialect.addi_imm"

    traits = traits_def(Pure())

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int:
        return lhs + imm

    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        return attr.value.data == 0

    @staticmethod
    def is_right_unit(attr: IntegerAttr) -> bool:
        return attr.value.data == 0

    def __init__(
        self,
        lhs: SSAValue,
        imm: int | IntegerAttr,
        result_type: Attribute | None = None,
        overflow: IntegerOverflowAttr = IntegerOverflowAttr("none"),
    ):
        super().__init__(lhs=lhs, imm=imm, result_type=result_type, overflow=overflow)



@irdl_op_definition
class SubiImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    name = "mydialect.subi_imm"

    traits = traits_def(Pure())

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int:
        return lhs - imm

    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        return attr.value.data == 0

    @staticmethod
    def is_right_unit(attr: IntegerAttr) -> bool:
        return attr.value.data == 0  # optional, 0 is neutral for subtraction

    def __init__(
        self,
        lhs: SSAValue,
        imm: int | IntegerAttr,
        result_type: Attribute | None = None,
        overflow: IntegerOverflowAttr = IntegerOverflowAttr("none"),
    ):
        super().__init__(lhs=lhs, imm=imm, result_type=result_type, overflow=overflow)

    
@irdl_op_definition
class MuliImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    name = "mydialect.muli_imm"

    traits = traits_def(Pure())

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int:
        return lhs * imm

    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        return attr.value.data == 0

    @staticmethod
    def is_right_unit(attr: IntegerAttr) -> bool:
        return attr.value.data == 1

    def __init__(
        self,
        lhs: SSAValue,
        imm: int | IntegerAttr,
        result_type: Attribute | None = None,
        overflow: IntegerOverflowAttr = IntegerOverflowAttr("none"),
    ):
        super().__init__(lhs=lhs, imm=imm, result_type=result_type, overflow=overflow)


@irdl_op_definition
class DivSImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    name = "mydialect.divsi_imm"

    traits = traits_def(Pure())

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int | None:
        if imm == 0:
            return None
        return lhs // imm

    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        return False  # division by zero is undefined, not absorbing

    @staticmethod
    def is_right_unit(attr: IntegerAttr) -> bool:
        return attr.value.data == 1

    def __init__(
        self,
        lhs: SSAValue,
        imm: int | IntegerAttr,
        result_type: Attribute | None = None,
        overflow: IntegerOverflowAttr = IntegerOverflowAttr("none"),
    ):
        super().__init__(lhs=lhs, imm=imm, result_type=result_type, overflow=overflow)


# === MLIR Generator ===

from xdsl.ir import Block, Region
from xdsl.dialects.builtin import i32
from xdsl.dialects.func import FuncOp, ReturnOp
from xdsl.dialects.arith import ConstantOp, AddiOp, SubiOp, MuliOp, DivSIOp

class MLIRGenerator:
    def __init__(self):
        self.symbol_table = {}
        self.current_block = None

    def process_expression(self, expr: Expression):
        if isinstance(expr, IntegerLiteral):
            op = ConstantOp.from_int_and_width(expr.value, 32)
            self.current_block.add_op(op)
            return op.results[0]

        elif isinstance(expr, DeclRef):
            if expr.name not in self.symbol_table or self.symbol_table[expr.name] is None:
                raise ValueError(f"Use of undeclared or uninitialized variable '{expr.name}'")
            return self.symbol_table[expr.name]

        elif isinstance(expr, BinaryOperator):
            lhs_val = self.process_expression(expr.lhs)
            rhs_val = self.process_expression(expr.rhs)

            if expr.opcode == '+':
                op = AddiOp(lhs_val, rhs_val)
            elif expr.opcode == '-':
                op = SubiOp(lhs_val, rhs_val)
            elif expr.opcode == '*':
                op = MuliOp(lhs_val, rhs_val)
            elif expr.opcode == '/':
                op = DivSIOp(lhs_val, rhs_val)
            else:
                raise ValueError(f"Unsupported binary operator: {expr.opcode}")

            self.current_block.add_op(op)
            return op.results[0]

        elif isinstance(expr, BinaryOperatorWithImmediate):
            # Decide which side is the constant
            lhs_expr, rhs_expr = expr.lhs, expr.rhs
            if isinstance(lhs_expr, IntegerLiteral):
                imm = lhs_expr.value
                lhs_val = self.process_expression(rhs_expr)
            else:
                imm = rhs_expr.value
                lhs_val = self.process_expression(lhs_expr)

            # Create the correct op
            if expr.opcode == '+':
                op = AddiImmOp(lhs_val, imm)
            elif expr.opcode == '-':
                op = SubiImmOp(lhs_val, imm)
            elif expr.opcode == '*':
                op = MuliImmOp(lhs_val, imm)
            elif expr.opcode == '/':
                op = DivSImmOp(lhs_val, imm)
            else:
                raise ValueError(f"Unsupported binary operator with immediate: {expr.opcode}")

            self.current_block.add_op(op)
            return op.results[0]

        else:
            raise TypeError(f"Unsupported expression type: {type(expr)}")


    def generate_function(self, func: FunctionDecl) -> FuncOp:
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
                    return_op = ReturnOp(result_op) 
                else:
                    return_op = ReturnOp([])
                self.current_block.add_op(return_op)

        func_type = ([i32] * len(func.params), [i32])  # Adjustable later
        return FuncOp(func.name, func_type, Region([block]))


# =============================================================================
# Imports
# =============================================================================

import json
import os
from dataclasses import is_dataclass
from typing import List

from xdsl.ir import Block, Region
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp, i32
from xdsl.dialects.func import FuncOp
from xdsl.printer import Printer


# =============================================================================
# QuantumIR - Updated for full pipeline
# =============================================================================

class QuantumIR():
    """
    Compilation pipeline using C AST JSON and custom IR generator.

    Steps:
    1. Parse JSON → Python Dataclasses
    2. Generate MLIR IR from dataclasses
    3. Visualize MLIR IR
    """

    # --- Configuration ---
    json_path: str = 'json_out/try.json'
    output_dir: str = 'output'

    # --- Internal State ---
    root: TranslationUnit = None
    module: ModuleOp = None

    def __init__(self):
        pass

    def run_dataclass(self):
        """Step 1: Parse JSON into structured dataclass AST."""
        with open(self.json_path) as f:
            ast_json = json.load(f)

        self.root = parse_ast(ast_json)
        print("AST successfully parsed into dataclasses.")
    
    def pretty_print_source(self):
        """Optional: Reconstruct original C-like source from dataclasses."""
        if self.root is None:
            raise RuntimeError("Must call run_dataclass() first")

        source_code = pretty_print_translation_unit(self.root)
        print("=== Pretty Printed C Source ===")
        print(source_code)
        print("=" * 35)


    def run_generate_ir(self):
        """Step 2: Convert dataclass AST into xDSL MLIR."""
        if self.root is None:
            raise RuntimeError("Must call run_dataclass() first")

        generator = MLIRGenerator()
        self.module = ModuleOp([])

        for func in self.root.decls:
            func_op = generator.generate_function(func)
            self.module.regions[0].blocks[0].add_op(func_op)

        print("MLIR IR successfully generated.")

    def visualize_ir(self):
        """Step 3: Print the MLIR IR."""
        if self.module is None:
            raise RuntimeError("Must call run_generate_ir() first")

        printer = Printer()
        printer.print_op(self.module)
        print()
    




# =============================================================================
# Entry Point (CLI Execution)
# =============================================================================

if __name__ == "__main__":
    """
    CLI entry point for running the full QuantumIR pipeline:
    1. Parse JSON into dataclasses
    2. Generate MLIR IR
    3. Print the IR
    """
    try:
        quantum_ir = QuantumIR()
        quantum_ir.run_dataclass()
        quantum_ir.pretty_print_source()
        quantum_ir.run_generate_ir()
        quantum_ir.visualize_ir()
    except Exception as e:
        print("Error in the execution of the program:", e)
        raise

