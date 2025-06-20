"""Legacy entry point re-exporting the refactored modules."""

from c_ast import *
from dialect_ops import *
from mlir_generator import MLIRGenerator
from pipeline import QuantumIR

__all__ = [
    # AST
    "TranslationUnit",
    "FunctionDecl",
    "VarDecl",
    "AssignStmt",
    "ReturnStmt",
    "Expression",
    "IntegerLiteral",
    "DeclRef",
    "BinaryOperator",
    "BinaryOperatorWithImmediate",
    "parse_ast",
    "pretty_print_translation_unit",
    # Ops
    "AddiImmOp",
    "SubiImmOp",
    "MuliImmOp",
    "DivSImmOp",
    # Generator and Pipeline
    "MLIRGenerator",
    "QuantumIR",
]
