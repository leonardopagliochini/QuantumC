import q_arithmetics as qa
from qiskit.circuit import QuantumCircuit
from qiskit.providers.basic_provider import BasicSimulator


def _run_comp(func, a, b):
    qa.set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = qa.initialize_variable(qc, a)
    b_reg = qa.initialize_variable(qc, b)
    out = func(qc, a_reg, b_reg)
    qa.measure_single(qc, out, "res")
    backend = BasicSimulator()
    tqc = qa.transpile(qc, backend)
    result = backend.run(tqc).result()
    counts = result.get_counts()
    key = max(counts, key=counts.get)
    return int(key)


def test_equal():
    assert _run_comp(qa.equal, 3, 3) == 1
    assert _run_comp(qa.equal, 3, 2) == 0
    assert _run_comp(qa.equal, -2, -2) == 1
    assert _run_comp(qa.equal, -2, 1) == 0


def test_not_equal():
    assert _run_comp(qa.not_equal, 2, 3) == 1
    assert _run_comp(qa.not_equal, -1, -1) == 0


def test_less_than():
    assert _run_comp(qa.less_than, 2, 3) == 1
    assert _run_comp(qa.less_than, -3, -2) == 1
    assert _run_comp(qa.less_than, 3, 2) == 0
    assert _run_comp(qa.less_than, 2, -1) == 0


def test_greater_than():
    assert _run_comp(qa.greater_than, 3, 2) == 1
    assert _run_comp(qa.greater_than, -2, -3) == 1
    assert _run_comp(qa.greater_than, 2, 3) == 0


def test_less_equal():
    assert _run_comp(qa.less_equal, 2, 2) == 1
    assert _run_comp(qa.less_equal, 2, 3) == 1
    assert _run_comp(qa.less_equal, 3, 2) == 0


def test_greater_equal():
    assert _run_comp(qa.greater_equal, 2, 2) == 1
    assert _run_comp(qa.greater_equal, 3, 2) == 1
    assert _run_comp(qa.greater_equal, 1, 2) == 0

