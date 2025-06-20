"""Utility script to generate AST JSON files for all C sources."""

from astJsonGen import astJsonGen

# Launch and create AST JSON for each file in ``c_code``
astJsonGen(input_dir="c_code")

