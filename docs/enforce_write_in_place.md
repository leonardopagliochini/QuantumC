# Enforcing Write-In-Place

The final translation step rewrites the classical MLIR into a quantum dialect while ensuring every operation writes back into its left operand.  This is performed by `quantum_translate.py` via the `QuantumTranslator` class.

## Concepts
- **Register Identifier** – each integer variable is mapped to a numeric register id.
- **Version** – the version increases whenever a register is overwritten.
- **Path** – when a value with the same id and version must be preserved, an additional path index distinguishes multiple results.

The translator tracks these triples `(id, version, path)` so that no register is clobbered prematurely.  The trait `WriteInPlace` in `quantum_dialect.py` verifies that operations obey the rule: result register id matches the left operand and the version equals the left operand's version + 1.

`QuantumIR.run_enforce_write_in_place` invokes the translator and verifies the resulting module.  `test_write_in_place_verification.py` demonstrates that violating the rule triggers a verification error.
