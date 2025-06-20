"""Legacy entry point re-exporting the refactored modules.

This module collects the most commonly used classes and functions from the
project and exposes them through ``__all__`` so that existing scripts can simply
``import mlir_pipeline`` without having to know the new module layout.
"""

# Import the concrete implementations from the refactored modules.
from c_ast import *
from dialect_ops import *
from mlir_generator import MLIRGenerator
from pipeline import QuantumIR

# Re-export the most frequently used names so that ``import mlir_pipeline``
# provides a compact public API for simple scripts.
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
