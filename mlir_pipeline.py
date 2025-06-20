# =============================================================================
# Imports
# =============================================================================

import json
import sys
import abc
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union

from xdsl.ir import Block, Region
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp, IntegerAttr, i32
from xdsl.dialects.func import FuncOp
from xdsl.dialects.arith import ConstantOp, SubiOp, AddiOp, MuliOp, DivSIOp
from xdsl.printer import Printer



# =============================================================================
# AST Node Definitions
# =============================================================================

class Expression:
    """Abstract base class for all expressions."""
    pass

@dataclass
class IntegerLiteral(Expression):
    value: int  # Constant integer value

@dataclass
class DeclRef(Expression):
    name: str  # Reference to a previously declared variable

@dataclass
class BinaryOperator(Expression):
    opcode: str              # E.g., '+', '-', '*', '/'
    lhs: Expression          # Left-hand side expression
    rhs: Expression          # Right-hand side expression

@dataclass
class BinaryOperatorWithImmediate(Expression):
    opcode: str              # Binary operation
    lhs: Expression          # One operand (likely variable)
    rhs: Expression          # One operand (must be immediate literal)

@dataclass
class VarDecl:
    name: str                         # Variable name
    init: Optional[Expression] = None # Optional initializer

@dataclass
class ReturnStmt:
    value: Optional[Expression] = None  # Optional return expression

@dataclass
class AssignStmt:
    name: str            # Variable name being assigned
    value: Expression    # Expression to assign

@dataclass
class CompoundStmt:
    stmts: List[Union[VarDecl, ReturnStmt, AssignStmt]] = field(default_factory=list)

@dataclass
class FunctionDecl:
    name: str                    # Function name
    body: CompoundStmt           # Body of the function
    params: List[str] = field(default_factory=list)  # Parameters (currently unused)

@dataclass
class TranslationUnit:
    decls: List[FunctionDecl] = field(default_factory=list)  # Top-level function declarations


# =============================================================================
# Expression Parser
# =============================================================================

def parse_expression(expr_node: dict) -> Expression:
    """
    Convert a JSON AST expression node into a Python expression dataclass.
    """
    kind = expr_node["kind"]

    # Recursively unwrap ImplicitCastExpr (e.g., promotion, conversion)
    if kind == "ImplicitCastExpr":
        return parse_expression(expr_node["inner"][0])

    # Unwrap parentheses (e.g., (x + y))
    if kind == "ParenExpr":
        return parse_expression(expr_node["inner"][0])

    # Case: Constant integer
    if kind == "IntegerLiteral":
        return IntegerLiteral(int(expr_node["value"]))

    # Case: Variable reference
    elif kind == "DeclRefExpr":
        if "name" in expr_node:
            name = expr_node["name"]
        elif "referencedDecl" in expr_node and "name" in expr_node["referencedDecl"]:
            name = expr_node["referencedDecl"]["name"]
        else:
            raise ValueError(f"Cannot extract name from DeclRefExpr: {expr_node}")
        return DeclRef(name)

    # Case: Binary operator (e.g., x + y or 3 + y)
    elif kind == "BinaryOperator":
        opcode = expr_node["opcode"]
        inner_nodes = expr_node.get("inner", [])
        if len(inner_nodes) != 2:
            raise ValueError(f"BinaryOperator must have 2 children: {expr_node}")

        lhs_expr = parse_expression(inner_nodes[0])
        rhs_expr = parse_expression(inner_nodes[1])

        # Use specialized variant if exactly one operand is a literal
        if isinstance(lhs_expr, IntegerLiteral) ^ isinstance(rhs_expr, IntegerLiteral):
            return BinaryOperatorWithImmediate(opcode, lhs_expr, rhs_expr)
        else:
            return BinaryOperator(opcode, lhs_expr, rhs_expr)

    # Case: Unrecognized expression node
    else:
        raise ValueError(f"Unsupported expression node: {kind}")


# =============================================================================
# AST Parser (JSON → Dataclass)
# =============================================================================

def parse_ast(ast_json: dict) -> TranslationUnit:
    """
    Convert a full Clang AST (JSON format) into our structured Python dataclass AST.
    """
    tu = TranslationUnit()

    # Iterate through top-level declarations
    for decl in ast_json.get("inner", []):
        if decl["kind"] == "FunctionDecl":
            func_name = decl["name"]
            compound_stmt = None

            # Locate compound body of the function
            for inner in decl.get("inner", []):
                if inner["kind"] == "CompoundStmt":
                    compound_stmt = CompoundStmt()

                    # Loop through individual statements inside the function body
                    for stmt in inner.get("inner", []):
                        
                        # ----------------------------
                        # Variable declaration: int x = expr;
                        # ----------------------------
                        if stmt["kind"] == "DeclStmt":
                            for var_decl in stmt.get("inner", []):
                                if var_decl["kind"] == "VarDecl":
                                    init_expr = None
                                    if "inner" in var_decl and var_decl["inner"]:
                                        init_expr = parse_expression(var_decl["inner"][0])
                                    compound_stmt.stmts.append(
                                        VarDecl(var_decl["name"], init_expr)
                                    )

                        # ----------------------------
                        # Assignment statement: x = expr;
                        # ----------------------------
                        elif stmt["kind"] == "BinaryOperator" and stmt["opcode"] == "=":
                            lhs = stmt["inner"][0]
                            rhs = stmt["inner"][1]

                            # Support only simple assignments: variable = expression
                            if lhs["kind"] == "DeclRefExpr":
                                var_name = lhs.get("name") or lhs.get("referencedDecl", {}).get("name")
                                if not var_name:
                                    raise ValueError("Cannot resolve variable name in assignment LHS")

                                rhs_expr = parse_expression(rhs)
                                compound_stmt.stmts.append(AssignStmt(var_name, rhs_expr))
                            else:
                                raise ValueError(f"Unsupported assignment LHS: {lhs['kind']}")

                        # ----------------------------
                        # Return statement: return expr;
                        # ----------------------------
                        elif stmt["kind"] == "ReturnStmt":
                            return_expr = None
                            if "inner" in stmt and stmt["inner"]:
                                return_expr = parse_expression(stmt["inner"][0])
                            compound_stmt.stmts.append(ReturnStmt(return_expr))

                        # ----------------------------
                        # Skip unsupported statements (e.g., IfStmt, CallExpr)
                        # ----------------------------
                        else:
                            pass  # Future support

            # Register parsed function declaration
            if compound_stmt:
                tu.decls.append(FunctionDecl(func_name, compound_stmt))

    return tu

# =============================================================================
# Pretty-Printing Functions (AST → Source Code String)
# =============================================================================

def pretty_print_translation_unit(tu: TranslationUnit) -> str:
    """
    Converts a parsed TranslationUnit (our AST) back into readable C-like source code.
    Useful for debugging and verification.
    """
    lines = []

    # Iterate over all top-level function declarations
    for func in tu.decls:
        # Format function signature with optional parameters
        params = ", ".join(f"int {p}" for p in func.params)
        lines.append(f'int {func.name}({params}) {{')

        # Print each statement in the function body
        for stmt in func.body.stmts:

            # -----------------------------
            # Case: Variable declaration
            # -----------------------------
            if isinstance(stmt, VarDecl):
                if stmt.init:
                    expr_str = pretty_print_expression(stmt.init)
                    lines.append(f"    int {stmt.name} = {expr_str};")
                else:
                    lines.append(f"    int {stmt.name};")

            # -----------------------------
            # Case: Assignment
            # -----------------------------
            elif isinstance(stmt, AssignStmt):
                expr_str = pretty_print_expression(stmt.value)
                lines.append(f"    {stmt.name} = {expr_str};")

            # -----------------------------
            # Case: Return
            # -----------------------------
            elif isinstance(stmt, ReturnStmt):
                if stmt.value:
                    expr_str = pretty_print_expression(stmt.value)
                    lines.append(f"    return {expr_str};")
                else:
                    lines.append(f"    return;")

        # Close function body
        lines.append("}")
        lines.append("")  # Blank line between functions

    return "\n".join(lines)


def pretty_print_expression(expr: Expression) -> str:
    """
    Converts an Expression node into its C-style string representation.
    """
    if isinstance(expr, IntegerLiteral):
        return str(expr.value)

    elif isinstance(expr, DeclRef):
        return expr.name

    elif isinstance(expr, BinaryOperator):
        lhs = pretty_print_expression(expr.lhs)
        rhs = pretty_print_expression(expr.rhs)
        return f"({lhs} {expr.opcode} {rhs})"

    elif isinstance(expr, BinaryOperatorWithImmediate):
        lhs = pretty_print_expression(expr.lhs)
        rhs = pretty_print_expression(expr.rhs)
        return f"({lhs} {expr.opcode} {rhs})"

    else:
        return "<unsupported_expr>"


# =============================================================================
# IRDL Support Imports for xDSL Dialect Definitions
# =============================================================================

from xdsl.ir import SSAValue, Attribute
from xdsl.dialects.builtin import IntegerAttr, i32
from xdsl.irdl import (
    irdl_op_definition,   # Decorator for defining custom operations
    IRDLOperation,        # Base class for IRDL-based ops
    VarConstraint,        # For variadic operand constraints
    operand_def,          # Operand definition utility
    result_def,           # Result definition utility
    prop_def,             # Property definition utility
    traits_def            # Trait registration utility
)

from xdsl.traits import Pure                        # Marker for pure (side-effect-free) ops
from xdsl.utils.exceptions import VerifyException   # Exception used during verification
from xdsl.dialects.builtin import IntegerType, IndexType, AnyOf

from xdsl.dialects.arith import ClassVar            # Used in Arith op definitions
from xdsl.dialects.arith import IntegerOverflowAttr # Overflow handling attributes


# =============================================================================
# Type Matcher: Signless Integer or Index
# =============================================================================

# Utility matcher to constrain operand/result types
# Allows either integer types (e.g., i32) or index types (used for loop indices)
signlessIntegerLike = AnyOf([IntegerType, IndexType])


# =============================================================================
# Custom Dialect: Signless Integer Ops with Immediate RHS
# =============================================================================

class SignlessIntegerBinaryOpWithImmediate(IRDLOperation, abc.ABC):
    """
    Abstract base class for binary integer operations where the right-hand operand
    is a constant immediate (IntegerAttr), e.g., `x + 4`, `x * 2`.

    - Enforces same type on lhs and immediate.
    - Provides hooks for zero/unit detection and evaluation.
    - Format compatible with MLIR immediate conventions.
    """

    name = "mydialect.binary_imm"

    # Operand/result type must be a signless integer or index type
    T: ClassVar = VarConstraint("T", signlessIntegerLike)

    # One operand (lhs), one result
    lhs = operand_def(T)
    result = result_def(T)

    # Immediate constant as property (not an SSA operand)
    imm = prop_def(IntegerAttr)

    # Declare as pure operation (no side effects)
    traits = traits_def(Pure())

    # === Assembly format (MLIR-style pretty-print) ===
    # Example: `%res = mydialect.binary_imm %x, 42 : i32`
    assembly_format = "$lhs `,` $imm attr-dict `:` type($lhs)"

    def __init__(
        self,
        lhs: SSAValue,
        imm: int | IntegerAttr,
        result_type: Attribute | None = None
    ):
        # Auto-wrap immediate if passed as plain integer
        if isinstance(imm, int):
            imm = IntegerAttr(imm, lhs.type)

        # Use lhs type as fallback for result type
        if result_type is None:
            result_type = lhs.type

        # Call IRDL base constructor with correct slots
        super().__init__(
            operands=[lhs],
            result_types=[result_type],
            properties={"imm": imm},
        )

    def verify_(self):
        """
        Verify semantic constraints of the operation:
        - imm must be an IntegerAttr
        - lhs and imm must have the same type
        """
        if not isinstance(self.imm, IntegerAttr):
            raise VerifyException("Immediate must be an IntegerAttr")

        if self.lhs.type != self.imm.type:
            raise VerifyException(
                f"Operand and immediate must have matching types, "
                f"got {self.lhs.type} vs {self.imm.type}"
            )

    # Optional: Python-level evaluation logic
    @staticmethod
    def py_operation(lhs: int, imm: int) -> int | None:
        return None  # To be implemented in subclasses

    # Optional: Absorbing element check (e.g., x * 0)
    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        return False

    # Optional: Identity element check (e.g., x + 0)
    @staticmethod
    def is_right_unit(attr: IntegerAttr) -> bool:
        return False


# =============================================================================
# Variant with Overflow Handling
# =============================================================================

class SignlessIntegerBinaryOpWithImmediateAndOverflow(SignlessIntegerBinaryOpWithImmediate, abc.ABC):
    """
    Extension of the immediate-operand base class to support integer overflow flags.
    """

    name = "mydialect.binary_imm_overflow"

    # Optional property to store overflow behavior (none, wrap, etc.)
    overflow_flags = prop_def(
        IntegerOverflowAttr,
        default_value=IntegerOverflowAttr("none"),
        prop_name="overflowFlags",
    )

    # MLIR-style format with optional `overflow` keyword
    assembly_format = (
        "$lhs `,` $imm (`overflow` `` $overflowFlags^)? attr-dict `:` type($lhs)"
    )

    def __init__(
        self,
        lhs: SSAValue,
        imm: int | IntegerAttr,
        result_type: Attribute | None = None,
        overflow: IntegerOverflowAttr = IntegerOverflowAttr("none"),
    ):
        # Convert integer to IntegerAttr
        if isinstance(imm, int):
            imm = IntegerAttr(imm, lhs.type)
        if result_type is None:
            result_type = lhs.type

        # Call parent constructor
        super().__init__(lhs=lhs, imm=imm, result_type=result_type)

        # Add overflow flag as property
        self.properties["overflowFlags"] = overflow


# =============================================================================
# Concrete Operation: Add Immediate (with optional overflow)
# =============================================================================

@irdl_op_definition
class AddiImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    """
    Addition with constant immediate (e.g., `%res = addi_imm %x, 4`)
    """

    name = "mydialect.addi_imm"
    traits = traits_def(Pure())

    # Python-side behavior
    @staticmethod
    def py_operation(lhs: int, imm: int) -> int:
        return lhs + imm

    # Optimization helper: identity element is 0
    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        return attr.value.data == 0

    @staticmethod
    def is_right_unit(attr: IntegerAttr) -> bool:
        return attr.value.data == 0

    # Constructor with overflow flag support
    def __init__(
        self,
        lhs: SSAValue,
        imm: int | IntegerAttr,
        result_type: Attribute | None = None,
        overflow: IntegerOverflowAttr = IntegerOverflowAttr("none"),
    ):
        super().__init__(lhs=lhs, imm=imm, result_type=result_type, overflow=overflow)




# =============================================================================
# mydialect.subi_imm - Subtraction with Immediate
# =============================================================================

@irdl_op_definition
class SubiImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    """
    Performs subtraction: `%res = %lhs - imm`.

    - Pure operation.
    - Right operand is a constant.
    """

    name = "mydialect.subi_imm"
    traits = traits_def(Pure())

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int:
        return lhs - imm

    # 0 is the neutral element (x - 0 = x)
    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        return attr.value.data == 0

    # Optional: treat 0 as "unit" (though subtraction is not strictly identity-preserving)
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


# =============================================================================
# mydialect.muli_imm - Multiplication with Immediate
# =============================================================================

@irdl_op_definition
class MuliImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    """
    Performs multiplication: `%res = %lhs * imm`.

    - Pure operation.
    - 0 is absorbing; 1 is unit.
    """

    name = "mydialect.muli_imm"
    traits = traits_def(Pure())

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int:
        return lhs * imm

    # 0 is an absorbing element for multiplication
    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        return attr.value.data == 0

    # 1 is the identity for multiplication
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


# =============================================================================
# mydialect.divsi_imm - Signed Division with Immediate
# =============================================================================

@irdl_op_definition
class DivSImmOp(SignlessIntegerBinaryOpWithImmediateAndOverflow):
    """
    Performs signed integer division: `%res = %lhs / imm`.

    - Returns None on divide-by-zero (undefined).
    - 1 is unit (x / 1 = x).
    """

    name = "mydialect.divsi_imm"
    traits = traits_def(Pure())

    @staticmethod
    def py_operation(lhs: int, imm: int) -> int | None:
        if imm == 0:
            return None  # undefined
        return lhs // imm

    # Division by 0 is undefined → not absorbing
    @staticmethod
    def is_right_zero(attr: IntegerAttr) -> bool:
        return False

    # 1 is the identity for division (x / 1 = x)
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


# =============================================================================
# MLIRGenerator - Generates xDSL IR from Dataclass AST
# =============================================================================

from xdsl.ir import Block, Region
from xdsl.dialects.builtin import i32
from xdsl.dialects.func import FuncOp, ReturnOp
from xdsl.dialects.arith import ConstantOp, AddiOp, SubiOp, MuliOp, DivSIOp

# =============================================================================
# Generator Class
# =============================================================================

class MLIRGenerator:
    """
    Translates dataclass-based AST into xDSL-based MLIR IR.

    - Handles variable tracking, constant generation, and expression evaluation.
    - Converts a function into a FuncOp with a Region and Block.
    """

    def __init__(self):
        self.symbol_table = {}       # maps variable names → SSA values
        self.current_block = None    # active IR block for op insertion

    # -------------------------------------------------------------------------
    # Expression Handler
    # -------------------------------------------------------------------------
    def process_expression(self, expr: Expression):
        """
        Recursively converts an expression into IR.

        Supports:
        - Integer literals
        - Variable references
        - Binary ops (Add/Sub/Mul/Div)
        - Binary ops with immediate
        """

        # --- Constant: int literal ---
        if isinstance(expr, IntegerLiteral):
            op = ConstantOp.from_int_and_width(expr.value, 32)
            self.current_block.add_op(op)
            return op.results[0]

        # --- Variable: x or y ---
        elif isinstance(expr, DeclRef):
            if expr.name not in self.symbol_table or self.symbol_table[expr.name] is None:
                raise ValueError(f"Use of undeclared or uninitialized variable '{expr.name}'")
            return self.symbol_table[expr.name]

        # --- Binary Operator: x + y, x - y, etc. ---
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

        # --- Binary Operator with Immediate: x + 5, 5 - y, etc. ---
        elif isinstance(expr, BinaryOperatorWithImmediate):
            # Detect which side is constant
            lhs_expr, rhs_expr = expr.lhs, expr.rhs
            if isinstance(lhs_expr, IntegerLiteral):
                imm = lhs_expr.value
                lhs_val = self.process_expression(rhs_expr)
            else:
                imm = rhs_expr.value
                lhs_val = self.process_expression(lhs_expr)

            # Dispatch to correct immediate-op class
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

        # --- Fallback ---
        else:
            raise TypeError(f"Unsupported expression type: {type(expr)}")


    # -------------------------------------------------------------------------
    # Function Generator
    # -------------------------------------------------------------------------
    def generate_function(self, func: FunctionDecl) -> FuncOp:
        """
        Converts a FunctionDecl dataclass into an xDSL FuncOp.

        Handles:
        - Variable declarations and assignments
        - Return statements
        """

        block = Block()                    # create a new block
        self.current_block = block
        self.symbol_table.clear()         # reset for each function

        for stmt in func.body.stmts:
            # --- Variable Declaration ---
            if isinstance(stmt, VarDecl):
                if stmt.init:
                    op = self.process_expression(stmt.init)
                    self.symbol_table[stmt.name] = op
                else:
                    self.symbol_table[stmt.name] = None

            # --- Assignment: x = y + z ---
            elif isinstance(stmt, AssignStmt):
                value_op = self.process_expression(stmt.value)
                self.symbol_table[stmt.name] = value_op

            # --- Return statement ---
            elif isinstance(stmt, ReturnStmt):
                if stmt.value:
                    result_op = self.process_expression(stmt.value)
                    return_op = ReturnOp(result_op)
                else:
                    return_op = ReturnOp([])

                self.current_block.add_op(return_op)

        # --- Finalize FuncOp ---
        func_type = ([i32] * len(func.params), [i32])  # adjust input/output types as needed
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
# QuantumIR - Full Pipeline Driver
# =============================================================================

class QuantumIR:
    """
    High-level compiler driver for converting JSON-based C AST
    → Python dataclass AST → xDSL MLIR → textual output.

    Pipeline:
    1. Parse JSON into dataclasses.
    2. Generate MLIR IR using xDSL.
    3. Visualize final IR output.
    """

    def __init__(self, json_path: str = "json_out/try.json", output_dir: str = "output"):
        self.json_path = json_path
        self.output_dir = output_dir
        self.root: TranslationUnit = None
        self.module: ModuleOp = None
        self.quantum_module: ModuleOp | None = None

        # ---------------------------------------------------------------------
        # File system setup
        # ---------------------------------------------------------------------

        # Ensure input JSON exists
        if not os.path.exists(self.json_path):
            raise FileNotFoundError(f"Input JSON file not found: {self.json_path}")

        # Ensure output directory is present
        os.makedirs(self.output_dir, exist_ok=True)

    # -------------------------------------------------------------------------
    # Step 1: Parse JSON → Dataclasses
    # -------------------------------------------------------------------------
    def run_dataclass(self):
        """
        Parses the JSON AST and stores it as a structured `TranslationUnit`
        in `self.root`.
        """
        with open(self.json_path) as f:
            ast_json = json.load(f)

        self.root = parse_ast(ast_json)
        print("AST successfully parsed into dataclasses.")

    # -------------------------------------------------------------------------
    # Pretty Print (Optional): Reconstruct C-like source
    # -------------------------------------------------------------------------
    def pretty_print_source(self):
        """
        Reconstructs the original C-like source code using the AST dataclasses.
        Mostly used for debugging and human inspection.
        """
        if self.root is None:
            raise RuntimeError("Must call run_dataclass() first")

        source_code = pretty_print_translation_unit(self.root)
        print("=== Pretty Printed C Source ===")
        print(source_code)
        print("=" * 35)

    # -------------------------------------------------------------------------
    # Step 2: Dataclasses → MLIR IR
    # -------------------------------------------------------------------------
    def run_generate_ir(self):
        """
        Translates parsed AST into xDSL IR stored in `self.module`.
        Uses `MLIRGenerator` to walk the AST and emit ops.
        """
        if self.root is None:
            raise RuntimeError("Must call run_dataclass() first")

        generator = MLIRGenerator()
        self.module = ModuleOp([])

        for func in self.root.decls:
            func_op = generator.generate_function(func)
            self.module.regions[0].blocks[0].add_op(func_op)

        print("MLIR IR successfully generated.")

    # -------------------------------------------------------------------------
    # Step 3: Pretty Print MLIR
    # -------------------------------------------------------------------------
    def visualize_ir(self):
        """
        Uses the built-in xDSL `Printer` to emit textual MLIR to stdout.
        """
        if self.module is None:
            raise RuntimeError("Must call run_generate_ir() first")

        printer = Printer()
        printer.print_op(self.module)
        print()

    def run_generate_quantum_ir(self):
        """Translate the previously generated MLIR into the quantum dialect."""
        if self.module is None:
            raise RuntimeError("Must call run_generate_ir() first")

        from quantum_translate import QuantumTranslator
        translator = QuantumTranslator(self.module)
        self.quantum_module = translator.translate()
        print("Quantum MLIR successfully generated.")

    def visualize_quantum_ir(self):
        if self.quantum_module is None:
            raise RuntimeError("Must call run_generate_quantum_ir() first")

        printer = Printer()
        printer.print_op(self.quantum_module)
        print()


# =============================================================================
# Entry Point (CLI Execution)
# =============================================================================

if __name__ == "__main__":
    """
    Top-level entry point when script is run from terminal.
    This triggers the full QuantumIR compilation pipeline:
    
    Steps:
    1. Load JSON file containing C AST
    2. Parse into Python dataclasses
    3. Pretty-print reconstructed C code (for debugging)
    4. Generate xDSL MLIR IR
    5. Print IR to console
    """

    try:
        # ---------------------------------------------------------------------
        # Input Path Handling
        # ---------------------------------------------------------------------
        # If a path is provided as first CLI argument, use it.
        # Otherwise fallback to default "json_out/try.json"
        input_json_path = sys.argv[1] if len(sys.argv) > 1 else "json_out/try.json"

        # ---------------------------------------------------------------------
        # Run Compilation Pipeline
        # ---------------------------------------------------------------------
        quantum_ir = QuantumIR(json_path=input_json_path)
        print()
        quantum_ir.run_dataclass()
        print()
        quantum_ir.pretty_print_source()
        quantum_ir.run_generate_ir()
        quantum_ir.visualize_ir()
        quantum_ir.run_generate_quantum_ir()
        quantum_ir.visualize_quantum_ir()


    except Exception as e:
        # Catch and show any runtime errors
        print("Error in the execution of the program:", e)
        raise
