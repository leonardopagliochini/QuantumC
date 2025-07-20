# =============================================================================
# AST Node Definitions and Parsing Utilities
# =============================================================================

"""Dataclasses representing a tiny C-like language and parsing helpers.

This module defines a very small set of dataclasses capturing the subset of C
that is handled by the rest of the repository.  It also contains utilities to
convert the JSON output produced by ``clang -ast-dump=json`` into these
dataclasses and back into a pretty-printed C-like source.  The goal is to keep
the front-end logic separate from the MLIR generation and quantum translation
stages.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union


# -----------------------------------------------------------------------------
# AST Classes
# -----------------------------------------------------------------------------

class Expression:
    """Abstract base class for all expressions."""
    pass


@dataclass
class IntegerLiteral(Expression):
    """Integer constant."""

    value: int


@dataclass
class DeclRef(Expression):
    """Reference to a previously declared variable."""

    name: str


@dataclass
class BinaryOperator(Expression):
    """Binary operation between ``lhs`` and ``rhs``."""

    opcode: str
    lhs: Expression
    rhs: Expression


@dataclass
class BinaryOperatorWithImmediate(Expression):
    """Binary operation where one side is an immediate."""

    opcode: str
    lhs: Expression
    rhs: Expression

@dataclass
class UnaryOperator(Expression):
    """Unary operation like -x, !x, or ~x."""
    opcode: str
    operand: Expression

@dataclass
class VarDecl:
    """Variable declaration optionally with initialization."""

    name: str
    init: Optional[Expression] = None


@dataclass
class ReturnStmt:
    """Return statement with optional value."""

    value: Optional[Expression] = None


@dataclass
class AssignStmt:
    """Assignment of ``value`` to variable ``name``."""

    name: str
    value: Expression


@dataclass
class CompoundStmt:
    stmts: List[Union[VarDecl, ReturnStmt, AssignStmt, 'IfStmt']] = field(default_factory=list)

@dataclass
class FunctionDecl:
    """Function definition."""

    name: str
    body: CompoundStmt
    params: List[str] = field(default_factory=list)


@dataclass
class TranslationUnit:
    """Top-level container of all functions."""

    decls: List[FunctionDecl] = field(default_factory=list)

@dataclass
class IfStmt:
    condition: Expression
    then_body: CompoundStmt
    else_body: Optional[CompoundStmt] = None


# -----------------------------------------------------------------------------
# Expression Parsing
# -----------------------------------------------------------------------------

def parse_expression(expr_node: Dict) -> Expression:
    """Convert a JSON AST expression node into an ``Expression`` instance.

    Parameters
    ----------
    expr_node:
        Dictionary describing the expression as emitted by ``clang``.

    Returns
    -------
    Expression
        One of the dataclass instances defined in this module.
    """
    # ``kind`` indicates which concrete expression class we must construct.
    kind = expr_node["kind"]

    # Ignore implicit casts by looking through them.
    if kind == "ImplicitCastExpr":
        return parse_expression(expr_node["inner"][0])

    # Parentheses merely contain another expression.
    if kind == "ParenExpr":
        return parse_expression(expr_node["inner"][0])

    # Leaf node representing an integer constant.
    if kind == "IntegerLiteral":
        return IntegerLiteral(int(expr_node["value"]))

    # Reference to an existing variable declaration.
    if kind == "DeclRefExpr":
        if "name" in expr_node:
            name = expr_node["name"]
        elif "referencedDecl" in expr_node and "name" in expr_node["referencedDecl"]:
            name = expr_node["referencedDecl"]["name"]
        else:
            raise ValueError(f"Cannot extract name from DeclRefExpr: {expr_node}")
        return DeclRef(name)

    # Binary operator such as ``+`` or ``*``.
    if kind == "BinaryOperator":
        opcode = expr_node["opcode"]
        inner_nodes = expr_node.get("inner", [])
        if len(inner_nodes) != 2:
            raise ValueError(f"BinaryOperator must have 2 children: {expr_node}")

        # Recursively parse both operands.
        lhs_expr = parse_expression(inner_nodes[0])
        rhs_expr = parse_expression(inner_nodes[1])

        # If exactly one operand is a constant, treat it as an immediate form.
        if isinstance(lhs_expr, IntegerLiteral) ^ isinstance(rhs_expr, IntegerLiteral):
            return BinaryOperatorWithImmediate(opcode, lhs_expr, rhs_expr)
        return BinaryOperator(opcode, lhs_expr, rhs_expr)

    # unary operations
    if kind == "UnaryOperator":
        opcode = expr_node["opcode"]
        # The operand is usually wrapped in an ImplicitCastExpr — you already strip that.
        operand_expr = parse_expression(expr_node["inner"][0])
        return UnaryOperator(opcode, operand_expr)


    raise ValueError(f"Unsupported expression node: {kind}")


# -----------------------------------------------------------------------------
# AST Parser (JSON -> Dataclasses)
# -----------------------------------------------------------------------------

def parse_ast(ast_json: Dict) -> TranslationUnit:
    """Convert a complete Clang JSON AST into a :class:`TranslationUnit`.

    Parameters
    ----------
    ast_json:
        Parsed JSON object produced by ``clang -ast-dump=json``.

    Returns
    -------
    TranslationUnit
        The root of the dataclass representation.
    """
    tu = TranslationUnit()

    # Walk over the top-level declarations in the JSON AST.
    for decl in ast_json.get("inner", []):
        if decl.get("kind") != "FunctionDecl":
            continue  # Skip anything that isn't a function.

        func_name = decl["name"]
        compound_stmt = None

        # Find the body of the function which is represented as a CompoundStmt.
        for inner in decl.get("inner", []):
            if inner.get("kind") != "CompoundStmt":
                continue

            compound_stmt = CompoundStmt()

            # Iterate over all statements inside the compound statement.
            for stmt in inner.get("inner", []):
                parsed = parse_statement(stmt)
                if parsed:
                    compound_stmt.stmts.append(parsed)


        # If we successfully built a function body, add the function to the TU.
        if compound_stmt:
            tu.decls.append(FunctionDecl(func_name, compound_stmt))

    return tu

def parse_statement(stmt: Dict) -> Optional[Union[VarDecl, AssignStmt, ReturnStmt, IfStmt]]:
    kind = stmt.get("kind")

    if kind == "DeclStmt":
        for var_decl in stmt.get("inner", []):
            if var_decl.get("kind") == "VarDecl":
                init_expr = None
                if "inner" in var_decl and var_decl["inner"]:
                    init_expr = parse_expression(var_decl["inner"][0])
                return VarDecl(var_decl["name"], init_expr)

    elif kind == "BinaryOperator" and stmt["opcode"] == "=":
        lhs = stmt["inner"][0]
        rhs = stmt["inner"][1]
        if lhs.get("kind") != "DeclRefExpr":
            raise ValueError(f"Unsupported assignment LHS: {lhs['kind']}")
        var_name = lhs.get("name") or lhs.get("referencedDecl", {}).get("name")
        rhs_expr = parse_expression(rhs)
        return AssignStmt(var_name, rhs_expr)

    elif kind == "ReturnStmt":
        if "inner" in stmt and stmt["inner"]:
            return_expr = parse_expression(stmt["inner"][0])
            return ReturnStmt(return_expr)
        else:
            return ReturnStmt()

    elif kind == "IfStmt":
        condition = parse_expression(stmt["inner"][0])

        then_raw = stmt["inner"][1]
        then_block = CompoundStmt()
        if then_raw["kind"] == "CompoundStmt":
            for s in then_raw.get("inner", []):
                parsed = parse_statement(s)
                if parsed:
                    then_block.stmts.append(parsed)

        else_block = None
        if len(stmt["inner"]) > 2:
            else_raw = stmt["inner"][2]
            if else_raw["kind"] == "IfStmt":
                # this is an else if
                nested_if = parse_statement(else_raw)
                else_block = CompoundStmt(stmts=[nested_if]) if nested_if else None
            elif else_raw["kind"] == "CompoundStmt":
                else_block = CompoundStmt()
                for s in else_raw.get("inner", []):
                    parsed = parse_statement(s)
                    if parsed:
                        else_block.stmts.append(parsed)

        return IfStmt(condition, then_block, else_block)

    return None




# -----------------------------------------------------------------------------
# Pretty-Printing Utilities
# -----------------------------------------------------------------------------

def pretty_print_statement(stmt, indent=1) -> List[str]:
    """Pretty-print any statement with correct indentation."""
    indent_str = "    " * indent
    lines: List[str] = []

    if isinstance(stmt, VarDecl):
        if stmt.init:
            expr_str = pretty_print_expression(stmt.init)
            lines.append(f"{indent_str}int {stmt.name} = {expr_str};")
        else:
            lines.append(f"{indent_str}int {stmt.name};")

    elif isinstance(stmt, AssignStmt):
        expr_str = pretty_print_expression(stmt.value)
        lines.append(f"{indent_str}{stmt.name} = {expr_str};")

    elif isinstance(stmt, ReturnStmt):
        if stmt.value:
            expr_str = pretty_print_expression(stmt.value)
            lines.append(f"{indent_str}return {expr_str};")
        else:
            lines.append(f"{indent_str}return;")

    elif isinstance(stmt, IfStmt):
        cond_str = pretty_print_expression(stmt.condition)
        lines.append(f"{indent_str}if ({cond_str}) {{")
        for inner in stmt.then_body.stmts:
            lines.extend(pretty_print_statement(inner, indent + 1))
        lines.append(f"{indent_str}}}")
        if stmt.else_body:
            lines.append(f"{indent_str}else {{")
            for inner in stmt.else_body.stmts:
                lines.extend(pretty_print_statement(inner, indent + 1))
            lines.append(f"{indent_str}}}")

    else:
        lines.append(f"{indent_str}// Unsupported statement: {type(stmt).__name__}")

    return lines

def pretty_print_translation_unit(tu: TranslationUnit) -> str:
    lines: List[str] = []

    for func in tu.decls:
        params = ", ".join(f"int {p}" for p in func.params)
        lines.append(f"int {func.name}({params}) {{")

        for stmt in func.body.stmts:
            lines.extend(pretty_print_statement(stmt, indent=1))

        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def pretty_print_expression(expr: Expression) -> str:
    """Convert an :class:`Expression` into a C-style string.

    Parameters
    ----------
    expr:
        Expression node to print.

    Returns
    -------
    str
        A textual representation of ``expr``.
    """
    # Integer constants appear as-is.
    if isinstance(expr, IntegerLiteral):
        return str(expr.value)
    # Variables are referenced by name.
    if isinstance(expr, DeclRef):
        return expr.name
    # Unary operations
    if isinstance(expr, UnaryOperator):
        operand = pretty_print_expression(expr.operand)
        return f"({expr.opcode}{operand})"
    # Standard binary operator using infix notation.
    if isinstance(expr, BinaryOperator):
        lhs = pretty_print_expression(expr.lhs)
        rhs = pretty_print_expression(expr.rhs)
        return f"({lhs} {expr.opcode} {rhs})"
    # Binary operator where one side is an immediate.
    if isinstance(expr, BinaryOperatorWithImmediate):
        lhs = pretty_print_expression(expr.lhs)
        rhs = pretty_print_expression(expr.rhs)
        return f"({lhs} {expr.opcode} {rhs})"
    return "<unsupported_expr>"

