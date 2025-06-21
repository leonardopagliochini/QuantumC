# =============================================================================
# QuantumIR Pipeline Driver
# =============================================================================

"""Command-line interface driving the MLIR generation pipeline.

The :class:`QuantumIR` class orchestrates all phases: parsing the JSON AST into
dataclasses, lowering them to MLIR, enforcing write-in-place semantics on the
quantum dialect, and finally printing the results. This module also acts as a
small CLI entry point wiring those pieces together when executed as a script.
"""

from __future__ import annotations
import json
import os
import sys

from xdsl.ir import Block, Region, Operation
from xdsl.dialects.builtin import ModuleOp
from xdsl.printer import Printer
from quantum_dialect import _annotate_value


from c_ast import TranslationUnit, parse_ast, pretty_print_translation_unit
from mlir_generator import MLIRGenerator

from quantum_translate import QuantumTranslator


class QuantumPrinter(Printer):
    """Printer annotating SSA values with register information."""

    def _print_results(self, op: Operation) -> None:  # type: ignore[override]
        results = op.results
        if len(results) == 0:
            return
        for i, res in enumerate(results):
            if i != 0:
                self.print_string(", ")
            self.print_ssa_value(res)
            self.print_string(_annotate_value(res))
        self.print_string(" = ")

    # ------------------------------------------------------------------
    def print_op(self, op: Operation) -> None:  # type: ignore[override]
        """Print an operation followed by an optional comment."""
        comment = op.attributes.pop("c_comment", None)
        super().print_op(op)
        if comment is not None:
            self.print_string(f"  // {comment}")
        if comment is not None:
            op.attributes["c_comment"] = comment

class QuantumIR:
    """High-level pipeline orchestrating JSON -> MLIR generation.

    The methods of this class mirror the individual stages of the translation
    pipeline so that scripts can invoke them separately or run the entire flow.
    """

    def __init__(self, json_path: str = "json_out/try.json", output_dir: str = "output"):
        """Initialize paths and load the input JSON.

        Parameters
        ----------
        json_path:
            Location of the input AST in JSON format.
        output_dir:
            Directory where artifacts produced by the pipeline will be written.
        """
        # Path to the input JSON file
        self.json_path = json_path
        # Directory where pipeline artifacts would be stored (currently unused)
        self.output_dir = output_dir
        # root node of the parsed AST when translated in dataclasses
        self.root: TranslationUnit | None = None
        # MLIR module for classic MLIR
        self.module: ModuleOp | None = None
        # MLIR module after write-in-place enforcement
        self.write_in_place_module: ModuleOp | None = None

        if not os.path.exists(self.json_path):
            raise FileNotFoundError(f"Input JSON file not found: {self.json_path}")
        os.makedirs(self.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    def run_dataclass(self) -> None:
        """Parse the JSON AST into dataclasses.

        The JSON file referenced by ``self.json_path`` is read and converted into
        the dataclass representation defined in :mod:`c_ast`.
        """
        # Load the JSON representation produced by Clang.
        with open(self.json_path) as f:
            ast_json = json.load(f)
        # Convert the raw JSON into the lightweight dataclass form.
        self.root = parse_ast(ast_json)
        print("AST successfully parsed into dataclasses.")

    def pretty_print_source(self) -> None:
        """Output the reconstructed C-like source.

        Raises
        ------
        RuntimeError
            If :meth:`run_dataclass` has not been called yet.
        """
        if self.root is None:
            raise RuntimeError("Must call run_dataclass first")
        print("=== Pretty Printed C Source ===")
        # Use the pretty-printer from :mod:`c_ast` to reconstruct the C source.
        print(pretty_print_translation_unit(self.root))
        print("=" * 35)

    def run_generate_ir(self) -> None:
        """Generate MLIR from the dataclasses.

        Raises
        ------
        RuntimeError
            If :meth:`run_dataclass` has not been called first.
        """
        if self.root is None:
            raise RuntimeError("Must call run_dataclass first")
        generator = MLIRGenerator()
        self.module = ModuleOp([])
        # Lower each function in the translation unit to MLIR and add it to the module.
        for func in self.root.decls:
            op = generator.generate_function(func)
            self.module.regions[0].blocks[0].add_op(op)
        print("MLIR IR successfully generated.")

    def visualize_ir(self) -> None:
        """Print the generated MLIR.

        Raises
        ------
        RuntimeError
            If :meth:`run_generate_ir` has not been executed.
        """
        if self.module is None:
            raise RuntimeError("Must call run_generate_ir first")
        # Dump the module using the xDSL printer.
        QuantumPrinter().print_op(self.module)
        print()

    def run_enforce_write_in_place(self) -> None:
        """Translate classical MLIR and enforce write-in-place semantics.

        Raises
        ------
        RuntimeError
            If :meth:`run_generate_ir` has not been executed.
        """
        if self.module is None:
            raise RuntimeError("Must call run_generate_ir first")
        
        # Run the translator to produce quantum-inspired operations.
        translator = QuantumTranslator(self.module)

        self.write_in_place_module = translator.translate()
        # Verify that all write-in-place invariants hold.
        self.write_in_place_module.verify()
        print("Write-in-place MLIR successfully generated.")

    def visualize_write_in_place_ir(self) -> None:
        """Print the IR after write-in-place enforcement."""
        if self.write_in_place_module is None:
            raise RuntimeError("Must call run_enforce_write_in_place first")
        # Display the module that uses the enforced dialect.
        QuantumPrinter().print_op(self.write_in_place_module)


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
        pipeline.run_enforce_write_in_place()
        pipeline.visualize_write_in_place_ir()
    except Exception as e:
        print("Error in the execution of the program:", e)
        raise

