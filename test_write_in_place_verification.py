from xdsl.dialects.builtin import ModuleOp, i32
from xdsl.dialects.func import FuncOp, ReturnOp
from xdsl.ir import Block, Region
from xdsl.utils.exceptions import VerifyException

from quantum_dialect import QuantumInitOp, QMuliOp

# Build a tiny module with an incorrect write-in-place operation.
block = Block()
init = QuantumInitOp(1, "0", 0, 0)
block.add_op(init)
# Deliberately use the wrong register id and version.
bad = QMuliOp(init.results[0], init.results[0], "1", 0, 0)
block.add_op(bad)
block.add_op(ReturnOp(bad.results[0]))
func = FuncOp("main", ([i32], [i32]), Region([block]))
module = ModuleOp([func])

try:
    module.verify()
    raise SystemExit("verification unexpectedly succeeded")
except VerifyException:
    print("verification failed as expected")
