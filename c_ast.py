# =============================================================================
# AST Node Definitions and Parsing Utilities
# =============================================================================

"""Dataclasses representing a tiny C-like language and parsing helpers."""

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
    """Sequence of statements forming a block."""

    stmts: List[Union[VarDecl, ReturnStmt, AssignStmt]] = field(default_factory=list)


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


# -----------------------------------------------------------------------------
# Expression Parsing
# -----------------------------------------------------------------------------

def parse_expression(expr_node: Dict) -> Expression:
    """Convert a JSON AST expression node into an Expression."""
    kind = expr_node["kind"]

    if kind == "ImplicitCastExpr":
        return parse_expression(expr_node["inner"][0])

    if kind == "ParenExpr":
        return parse_expression(expr_node["inner"][0])

    if kind == "IntegerLiteral":
        return IntegerLiteral(int(expr_node["value"]))

    if kind == "DeclRefExpr":
        if "name" in expr_node:
            name = expr_node["name"]
        elif "referencedDecl" in expr_node and "name" in expr_node["referencedDecl"]:
            name = expr_node["referencedDecl"]["name"]
        else:
            raise ValueError(f"Cannot extract name from DeclRefExpr: {expr_node}")
        return DeclRef(name)

    if kind == "BinaryOperator":
        opcode = expr_node["opcode"]
        inner_nodes = expr_node.get("inner", [])
        if len(inner_nodes) != 2:
            raise ValueError(f"BinaryOperator must have 2 children: {expr_node}")

        lhs_expr = parse_expression(inner_nodes[0])
        rhs_expr = parse_expression(inner_nodes[1])

        if isinstance(lhs_expr, IntegerLiteral) ^ isinstance(rhs_expr, IntegerLiteral):
            return BinaryOperatorWithImmediate(opcode, lhs_expr, rhs_expr)
        return BinaryOperator(opcode, lhs_expr, rhs_expr)

    raise ValueError(f"Unsupported expression node: {kind}")


# -----------------------------------------------------------------------------
# AST Parser (JSON -> Dataclasses)
# -----------------------------------------------------------------------------

def parse_ast(ast_json: Dict) -> TranslationUnit:
    """Convert a Clang JSON AST into dataclasses."""
    tu = TranslationUnit()

    for decl in ast_json.get("inner", []):
        if decl.get("kind") != "FunctionDecl":
            continue
        func_name = decl["name"]
        compound_stmt = None

        for inner in decl.get("inner", []):
            if inner.get("kind") != "CompoundStmt":
                continue
            compound_stmt = CompoundStmt()

            for stmt in inner.get("inner", []):
                if stmt["kind"] == "DeclStmt":
                    for var_decl in stmt.get("inner", []):
                        if var_decl.get("kind") == "VarDecl":
                            init_expr = None
                            if "inner" in var_decl and var_decl["inner"]:
                                init_expr = parse_expression(var_decl["inner"][0])
                            compound_stmt.stmts.append(VarDecl(var_decl["name"], init_expr))
                elif stmt["kind"] == "BinaryOperator" and stmt["opcode"] == "=":
                    lhs = stmt["inner"][0]
                    rhs = stmt["inner"][1]
                    if lhs.get("kind") != "DeclRefExpr":
                        raise ValueError(f"Unsupported assignment LHS: {lhs['kind']}")
                    var_name = lhs.get("name") or lhs.get("referencedDecl", {}).get("name")
                    if not var_name:
                        raise ValueError("Cannot resolve variable name in assignment LHS")
                    rhs_expr = parse_expression(rhs)
                    compound_stmt.stmts.append(AssignStmt(var_name, rhs_expr))
                elif stmt["kind"] == "ReturnStmt":
                    return_expr = None
                    if "inner" in stmt and stmt["inner"]:
                        return_expr = parse_expression(stmt["inner"][0])
                    compound_stmt.stmts.append(ReturnStmt(return_expr))
                else:
                    pass

        if compound_stmt:
            tu.decls.append(FunctionDecl(func_name, compound_stmt))

    return tu


# -----------------------------------------------------------------------------
# Pretty-Printing Utilities
# -----------------------------------------------------------------------------

def pretty_print_translation_unit(tu: TranslationUnit) -> str:
    """Reconstruct a C-like program from the dataclasses."""
    lines: List[str] = []
    for func in tu.decls:
        params = ", ".join(f"int {p}" for p in func.params)
        lines.append(f"int {func.name}({params}) {{")
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
                    lines.append("    return;")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


def pretty_print_expression(expr: Expression) -> str:
    """Convert an Expression into a C-style string."""
    if isinstance(expr, IntegerLiteral):
        return str(expr.value)
    if isinstance(expr, DeclRef):
        return expr.name
    if isinstance(expr, BinaryOperator):
        lhs = pretty_print_expression(expr.lhs)
        rhs = pretty_print_expression(expr.rhs)
        return f"({lhs} {expr.opcode} {rhs})"
    if isinstance(expr, BinaryOperatorWithImmediate):
        lhs = pretty_print_expression(expr.lhs)
        rhs = pretty_print_expression(expr.rhs)
        return f"({lhs} {expr.opcode} {rhs})"
    return "<unsupported_expr>"

