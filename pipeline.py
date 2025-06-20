# =============================================================================
# QuantumIR Pipeline Driver
# =============================================================================

from __future__ import annotations
import json
import os
import sys

from xdsl.ir import Block, Region
from xdsl.dialects.builtin import ModuleOp
from xdsl.printer import Printer

from c_ast import TranslationUnit, parse_ast, pretty_print_translation_unit
from mlir_generator import MLIRGenerator


class QuantumIR:
    """High-level pipeline orchestrating JSON -> MLIR generation."""

    def __init__(self, json_path: str = "json_out/try.json", output_dir: str = "output"):
        self.json_path = json_path
        self.output_dir = output_dir
        self.root: TranslationUnit | None = None
        self.module: ModuleOp | None = None
        self.quantum_module: ModuleOp | None = None

        if not os.path.exists(self.json_path):
            raise FileNotFoundError(f"Input JSON file not found: {self.json_path}")
        os.makedirs(self.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    def run_dataclass(self) -> None:
        """Parse the JSON AST into dataclasses."""
        with open(self.json_path) as f:
            ast_json = json.load(f)
        self.root = parse_ast(ast_json)
        print("AST successfully parsed into dataclasses.")

    def pretty_print_source(self) -> None:
        """Output the reconstructed C-like source."""
        if self.root is None:
            raise RuntimeError("Must call run_dataclass first")
        print("=== Pretty Printed C Source ===")
        print(pretty_print_translation_unit(self.root))
        print("=" * 35)

    def run_generate_ir(self) -> None:
        """Generate MLIR from the dataclasses."""
        if self.root is None:
            raise RuntimeError("Must call run_dataclass first")
        generator = MLIRGenerator()
        self.module = ModuleOp([])
        for func in self.root.decls:
            op = generator.generate_function(func)
            self.module.regions[0].blocks[0].add_op(op)
        print("MLIR IR successfully generated.")

    def visualize_ir(self) -> None:
        """Print the generated MLIR."""
        if self.module is None:
            raise RuntimeError("Must call run_generate_ir first")
        Printer().print_op(self.module)
        print()

    def run_generate_quantum_ir(self) -> None:
        """Translate standard MLIR to the quantum dialect."""
        if self.module is None:
            raise RuntimeError("Must call run_generate_ir first")
        from quantum_translate import QuantumTranslator
        translator = QuantumTranslator(self.module)
        self.quantum_module = translator.translate()
        print("Quantum MLIR successfully generated.")

    def visualize_quantum_ir(self) -> None:
        if self.quantum_module is None:
            raise RuntimeError("Must call run_generate_quantum_ir first")
        Printer().print_op(self.quantum_module)
        print()


if __name__ == "__main__":
    try:
        input_json_path = sys.argv[1] if len(sys.argv) > 1 else "json_out/try.json"
        pipeline = QuantumIR(json_path=input_json_path)
        print()
        pipeline.run_dataclass()
        print()
        pipeline.pretty_print_source()
        pipeline.run_generate_ir()
        pipeline.visualize_ir()
        pipeline.run_generate_quantum_ir()
        pipeline.visualize_quantum_ir()
    except Exception as e:
        print("Error in the execution of the program:", e)
        raise

