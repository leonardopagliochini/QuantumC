"""Execute the full pipeline on every C source in ``c_code``.

This helper runs :func:`astJsonGen` to convert the sources to JSON, then
translates each JSON file to classical and quantum MLIR using
:func:`generate_all` and finally checks that the two variants produce the
same result via :func:`compare_all`.
"""
from __future__ import annotations

from astJsonGen import astJsonGen
from run_all_pipeline import generate_all
from test_mlir_equivalence import compare_all


def run_tests() -> None:
    """Regenerate artifacts and compare results for all test programs."""
    astJsonGen(input_dir="c_code")
    generate_all(json_dir="json_out", out_dir="mlir_out")
    compare_all(out_dir="mlir_out")


if __name__ == "__main__":
    run_tests()
