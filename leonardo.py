import json
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union

from xdsl.ir import Block, Region
from xdsl.context import Context  # MLContext is deprecated
from xdsl.dialects.builtin import ModuleOp, IntegerAttr, i32
from xdsl.dialects.func import FuncOp
from xdsl.dialects.arith import ConstantOp, SubiOp, AddiOp, MuliOp, DivSIOp
from xdsl.printer import Printer

@dataclass
class IntegerLiteral:
    value: int

@dataclass
class BinaryOperator:
    opcode: str
    lhs: 'Expression'
    rhs: 'Expression'

Expression = Union[IntegerLiteral, BinaryOperator]

@dataclass
class VarDecl:
    name: str
    init: Optional[Expression] = None

@dataclass
class ReturnStmt:
    value: Optional[Expression] = None

@dataclass
class CompoundStmt:
    stmts: List[Union[VarDecl, ReturnStmt]] = field(default_factory=list)

@dataclass
class FunctionDecl:
    name: str
    body: CompoundStmt

@dataclass
class TranslationUnit:
    decls: List[FunctionDecl] = field(default_factory=list)

class MLIRGenerator:
    def __init__(self):
        self.symbol_table: Dict[str, Union[ConstantOp, SubiOp, AddiOp, MuliOp, DivSIOp]] = {}
        self.current_block: Optional[Block] = None
        self.ssa_counter = 0

    def emit_constant(self, value: int) -> ConstantOp:
        const_op = ConstantOp.from_int_and_width(value, 32)
        self.current_block.add_op(const_op)
        return const_op


    def process_expression(self, expr: Expression):
        if isinstance(expr, IntegerLiteral):
            return self.emit_constant(expr.value)

        elif isinstance(expr, BinaryOperator):
            lhs_op = self.process_expression(expr.lhs)
            rhs_op = self.process_expression(expr.rhs)

            if expr.opcode == '+':
                op = AddiOp(lhs_op.results[0], rhs_op.results[0])
            elif expr.opcode == '-':
                op = SubiOp(lhs_op.results[0], rhs_op.results[0])
            elif expr.opcode == '*':
                op = MuliOp(lhs_op.results[0], rhs_op.results[0])
            elif expr.opcode == '/':
                op = DivSIOp(lhs_op.results[0], rhs_op.results[0])
            else:
                raise ValueError(f"Unsupported operator: {expr.opcode}")

            self.current_block.add_op(op)
            return op

        raise TypeError(f"Unsupported expression type: {type(expr)}")

    def generate_function(self, func: FunctionDecl) -> FuncOp:
        block = Block()
        self.current_block = block
        self.symbol_table.clear()
        self.ssa_counter = 0

        for stmt in func.body.stmts:
            if isinstance(stmt, VarDecl) and stmt.init:
                op = self.process_expression(stmt.init)
                self.symbol_table[stmt.name] = op

            elif isinstance(stmt, ReturnStmt) and stmt.value:
                op = self.process_expression(stmt.value)

        func_type = [i32]
        return FuncOp(func.name, ([], func_type), Region([block]))

def parse_ast(ast_json: dict) -> TranslationUnit:
    tu = TranslationUnit()
    for decl in ast_json.get("inner", []):
        if decl["kind"] == "FunctionDecl" and decl["name"] == "main":
            compound_stmt = None
            for inner in decl.get("inner", []):
                if inner["kind"] == "CompoundStmt":
                    compound_stmt = CompoundStmt()
                    for stmt in inner.get("inner", []):
                        if stmt["kind"] == "DeclStmt":
                            for var_decl in stmt.get("inner", []):
                                if var_decl["kind"] == "VarDecl":
                                    init_expr = None
                                    if "inner" in var_decl and var_decl["inner"]:
                                        expr_node = var_decl["inner"][0]
                                        if expr_node["kind"] == "BinaryOperator":
                                            lhs = IntegerLiteral(int(expr_node["inner"][0]["value"]))
                                            rhs = IntegerLiteral(int(expr_node["inner"][1]["value"]))
                                            init_expr = BinaryOperator(
                                                expr_node["opcode"],
                                                lhs,
                                                rhs
                                            )
                                        elif expr_node["kind"] == "IntegerLiteral":
                                            init_expr = IntegerLiteral(int(expr_node["value"]))
                                    compound_stmt.stmts.append(
                                        VarDecl(var_decl["name"], init_expr)
                                    )
                        elif stmt["kind"] == "ReturnStmt":
                            return_expr = None
                            if "inner" in stmt and stmt["inner"]:
                                expr_node = stmt["inner"][0]
                                if expr_node["kind"] == "IntegerLiteral":
                                    return_expr = IntegerLiteral(int(expr_node["value"]))
                            compound_stmt.stmts.append(ReturnStmt(return_expr))
            if compound_stmt:
                tu.decls.append(FunctionDecl(decl["name"], compound_stmt))
    return tu

def main():
    if len(sys.argv) < 2:
        print("Usage: python c_to_mlir.py <input.json>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        ast_json = json.load(f)

    translation_unit = parse_ast(ast_json)

    if not translation_unit.decls:
        print("No functions found in AST")
        return

    mlir_generator = MLIRGenerator()
    ctx = Context()
    module = ModuleOp([])

    for func in translation_unit.decls:
        func_op = mlir_generator.generate_function(func)
        module.regions[0].blocks[0].add_op(func_op)

    printer = Printer()
    printer.print_op(module)
    print()

if __name__ == "__main__":
    main()