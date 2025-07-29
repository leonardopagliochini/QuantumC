"""Utility script to generate AST JSON files for all C sources.

Running this module executes :func:`astJsonGen` to iterate over the ``c_code``
directory, invoke ``clang`` on every ``.c`` file and produce a corresponding
JSON AST dump under ``json_out``.  It is meant to be a simple convenience entry
point for refreshing the test inputs.
"""

from .astJsonGen import astJsonGen

# Invoke ``clang`` on all sources found under ``c_code`` and write their JSON
# AST representation next to them under ``json_out``.  This module can be run as
# a standalone script for convenience when updating the repository inputs.
astJsonGen(input_dir="c_code")

