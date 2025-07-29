from xdsl.dialects.builtin import ModuleOp
from quantum_translate import QuantumTranslator


def generate_quantum_mlir(module: ModuleOp) -> ModuleOp:
    """Translate arithmetic MLIR ``module`` to the custom quantum dialect."""
    translator = QuantumTranslator(module)
    return translator.translate()
