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
import re
from io import StringIO

from xdsl.ir import Block, Region, Operation
import pandas as pd
from xdsl.dialects.builtin import ModuleOp
from xdsl.printer import Printer
from quantum_dialect import _annotate_value


from c_ast import TranslationUnit, parse_ast, pretty_print_translation_unit
from mlir_generator import MLIRGenerator

from quantum_translate import QuantumTranslator
from paths_dataframe import build_paths_dataframe
from ssa_dag import build_dag, visualize_dag, enforce_constraints


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


def pretty_print_mlir_lines(lines: list[str]) -> str:
    """Return MLIR lines with columns aligned for readability."""
    pattern = re.compile(
        r"^(\s*)(%\d+)(?:\s+({[^}]+}))?\s*=\s*(\S+)\s*(.*?)\s*(:(?:\s*[^/]+))?\s*(//.*)?$"
    )
    entries: list[tuple[str, str, str, str, str, str, str]] = []
    flags: list[bool] = []
    for line in lines:
        m = pattern.match(line)
        if m:
            indent, ssa, attr, op, args, ty, cmt = m.groups()
            entries.append(
                (
                    indent,
                    ssa.strip(),
                    (attr or "").strip(),
                    op.strip(),
                    args.strip(),
                    (ty or "").strip(),
                    (cmt or "").strip(),
                )
            )
            flags.append(True)
        else:
            entries.append((line, "", "", "", "", "", ""))
            flags.append(False)

    widths = [0, 0, 0, 0, 0]
    for entry, is_op in zip(entries, flags):
        if not is_op:
            continue
        _, ssa, attr, op, args, ty, _ = entry
        widths[0] = max(widths[0], len(ssa))
        widths[1] = max(widths[1], len(attr))
        widths[2] = max(widths[2], len(op))
        widths[3] = max(widths[3], len(args))
        widths[4] = max(widths[4], len(ty))

    result_lines: list[str] = []
    for entry, is_op in zip(entries, flags):
        if not is_op:
            result_lines.append(entry[0])
            continue
        indent, ssa, attr, op, args, ty, cmt = entry
        formatted = (
            indent
            + ssa.ljust(widths[0])
            + "  "
            + attr.ljust(widths[1])
            + "  =  "
            + op.ljust(widths[2])
            + "  "
            + args.ljust(widths[3])
            + "  "
            + ty.ljust(widths[4])
        )
        if cmt:
            formatted += "  " + cmt
        result_lines.append(formatted.rstrip())

    return "\n".join(result_lines)

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
        # DataFrame visualizing register paths
        self.paths_df: pd.DataFrame | None = None
        # SSA DAG built from the write-in-place IR
        self.dag = None
        # Module after enforcing additional quantum constraints
        self.compliant_module: ModuleOp | None = None
        # DataFrame for the compliant module
        self.compliant_df: pd.DataFrame | None = None

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
        buf = StringIO()
        QuantumPrinter(stream=buf).print_op(self.module)
        formatted = pretty_print_mlir_lines(buf.getvalue().splitlines())
        print("=== Classical MLIR ===")
        print(formatted)
        print("=" * 35)
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
        # Build the register usage dataframe for later inspection
        self.paths_df = build_paths_dataframe(self.write_in_place_module)
        print("Write-in-place MLIR successfully generated.")

    def visualize_write_in_place_ir(self) -> None:
        """Print the IR after write-in-place enforcement."""
        if self.write_in_place_module is None:
            raise RuntimeError("Must call run_enforce_write_in_place first")
        buf = StringIO()
        QuantumPrinter(stream=buf).print_op(self.write_in_place_module)
        formatted = pretty_print_mlir_lines(buf.getvalue().splitlines())
        print("=== Write-In-Place MLIR ===")
        print(formatted)
        print("=" * 35)

    def visualize_paths_dataframe(self) -> None:
        """Display a dataframe of register usage across timesteps."""
        if self.paths_df is None:
            raise RuntimeError("Must call run_enforce_write_in_place first")
        with pd.option_context("display.max_columns", None, "display.width", None):
            print("=== Register Paths DataFrame ===")
            print(self.paths_df.fillna(""))
            print("=" * 35)

    # ------------------------------------------------------------------
    def build_ssa_dag(self) -> None:
        """Construct the SSA DAG from the write-in-place module."""
        if self.write_in_place_module is None:
            raise RuntimeError("Must call run_enforce_write_in_place first")
        self.dag = build_dag(self.write_in_place_module)

    def visualize_dag(self, filename: str) -> None:
        """Save an image of the SSA DAG to ``filename``."""
        if self.dag is None:
            raise RuntimeError("Must call build_ssa_dag first")
        visualize_dag(self.dag, filename)

    def run_enforce_quantum_constraints(self) -> None:
        """Rewrite the DAG to satisfy quantum constraints."""
        if self.write_in_place_module is None:
            raise RuntimeError("Must call run_enforce_write_in_place first")
        self.compliant_module = enforce_constraints(self.write_in_place_module)
        self.compliant_df = build_paths_dataframe(self.compliant_module)
        self.dag = build_dag(self.compliant_module)

    def visualize_compliant_dataframe(self) -> None:
        """Display the register table after constraint enforcement."""
        if self.compliant_df is None:
            raise RuntimeError("Must call run_enforce_quantum_constraints first")
        with pd.option_context("display.max_columns", None, "display.width", None):
            print("=== Quantum-Compliant DataFrame ===")
            print(self.compliant_df.fillna(""))
            print("=" * 35)


if __name__ == "__main__":
    try:
        input_json_path = sys.argv[1] if len(sys.argv) > 1 else "json_out/test_paths.json"
        pipeline = QuantumIR(json_path=input_json_path)
        print()
        pipeline.run_dataclass()
        print()
        pipeline.pretty_print_source()
        pipeline.run_generate_ir()
        pipeline.visualize_ir()
        pipeline.run_enforce_write_in_place()
        pipeline.visualize_write_in_place_ir()
        pipeline.visualize_paths_dataframe()
        pipeline.build_ssa_dag()
        pipeline.visualize_dag("output/dag_before.png")
        pipeline.run_enforce_quantum_constraints()
        pipeline.visualize_dag("output/dag_after.png")
        pipeline.visualize_compliant_dataframe()
    except Exception as e:
        print("Error in the execution of the program:", e)
        raise

