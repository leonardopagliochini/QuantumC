"""Exhaustive tests for the arithmetic helpers.

The number of qubits available for each test is limited by the
``TOTAL_QUBITS`` constant.  For every operation we determine how many
qubits are required for the operands and run the circuit for all
possible inputs that fit in that space.  If ``TOTAL_QUBITS`` exceeds the
simulator capability the tests will fail.
"""

import csv
import os
from qiskit import QuantumCircuit, QuantumRegister, transpile
from q_arithmetics import (
    set_number_of_bits,
    initialize_variable,
    measure,
    add,
    addi,
    sub,
    subi,
    mul,
    muli,
    div_unsigned,
    divi,
    AerSimulator,
    BasicSimulator,
    NUMBER_OF_BITS,
)
import q_arithmetics as qa

# Available qubits for each circuit.  This should be kept small so that
# exhaustive testing finishes quickly and stays within simulator limits.
TOTAL_QUBITS = 10


def _range_signed(n):
    """Return all signed integers representable with ``n`` bits."""
    min_val = -(1 << (n - 1))
    max_val = (1 << (n - 1)) - 1
    return range(min_val, max_val + 1)


def _twos(value, n):
    """Convert ``value`` to a signed ``n``-bit integer."""
    value %= 1 << n
    if value >= 1 << (n - 1):
        value -= 1 << n
    return value


def _run_circuit(qc):
    """Simulate ``qc`` and return a dictionary of measured registers."""
    if AerSimulator is not None:
        backend = AerSimulator(method="matrix_product_state")
        compiled = transpile(qc, backend)
    else:
        backend = BasicSimulator()
        compiled = transpile(qc, backend)
    result = backend.run(compiled, shots=1).result()
    counts = result.get_counts()
    bitstring = max(counts, key=counts.get).replace(" ", "")
    offset = 0
    values = {}
    for creg in reversed(qc.cregs):
        reg_bits = bitstring[offset:offset + len(creg)]
        offset += len(creg)
        if len(reg_bits) == 0:
            values[creg.name] = 0
            continue
        unsigned = int(reg_bits, 2)
        if reg_bits[0] == "1" and len(creg) > 1:
            values[creg.name] = unsigned - (1 << len(creg))
        else:
            values[creg.name] = unsigned
    return values


def _test_add():
    """Exhaustively test addition.

    The function prints which operands are tested and how many
    combinations will be executed before running the circuits.
    """
    n = TOTAL_QUBITS // 3
    rows = []
    vals = list(_range_signed(n))
    total = len(vals) * len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(
        f"add: testing a and b in range {min_val}..{max_val}, {total} operations"
    )
    for a in vals:
        for b in vals:
            print(f"add: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            ar = initialize_variable(qc, a, "a")
            br = initialize_variable(qc, b, "b")
            out = add(qc, ar, br)
            measure(qc, out)
            res = _run_circuit(qc)[f"{out.name}_measure"]
            exp = _twos(a + b, n)
            rows.append(("add", a, b, exp, res, res == exp))
    return rows


def _test_addi():
    """Exhaustively test addition with a classical constant."""
    n = TOTAL_QUBITS // 2
    rows = []
    vals = list(_range_signed(n))
    total = len(vals) * len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(
        f"addi: testing a and b in range {min_val}..{max_val}, {total} operations"
    )
    for a in vals:
        for b in vals:
            print(f"addi: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            ar = initialize_variable(qc, a, "a")
            out = addi(qc, ar, b)
            measure(qc, out)
            res = _run_circuit(qc)[f"{out.name}_measure"]
            exp = _twos(a + b, n)
            rows.append(("addi", a, b, exp, res, res == exp))
    return rows


def _test_sub():
    """Exhaustively test subtraction."""
    n = TOTAL_QUBITS // 3
    rows = []
    vals = list(_range_signed(n))
    total = len(vals) * len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(
        f"sub: testing a and b in range {min_val}..{max_val}, {total} operations"
    )
    for a in vals:
        for b in vals:
            print(f"sub: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            ar = initialize_variable(qc, a, "a")
            br = initialize_variable(qc, b, "b")
            out = sub(qc, ar, br)
            measure(qc, out)
            res = _run_circuit(qc)[f"{out.name}_measure"]
            exp = _twos(a - b, n)
            rows.append(("sub", a, b, exp, res, res == exp))
    return rows


def _test_subi():
    """Exhaustively test subtraction by a classical constant."""
    n = TOTAL_QUBITS // 2
    rows = []
    vals = list(_range_signed(n))
    total = len(vals) * len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(
        f"subi: testing a and b in range {min_val}..{max_val}, {total} operations"
    )
    for a in vals:
        for b in vals:
            print(f"subi: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            ar = initialize_variable(qc, a, "a")
            out = subi(qc, ar, b)
            measure(qc, out)
            res = _run_circuit(qc)[f"{out.name}_measure"]
            exp = _twos(a - b, n)
            rows.append(("subi", a, b, exp, res, res == exp))
    return rows


def _test_mul():
    """Exhaustively test multiplication."""
    n = TOTAL_QUBITS // 3
    rows = []
    vals = list(_range_signed(n))
    total = len(vals) * len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(
        f"mul: testing a and b in range {min_val}..{max_val}, {total} operations"
    )
    for a in vals:
        for b in vals:
            print(f"mul: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            ar = initialize_variable(qc, a, "a")
            br = initialize_variable(qc, b, "b")
            out = mul(qc, ar, br)
            measure(qc, out)
            res = _run_circuit(qc)[f"{out.name}_measure"]
            exp = _twos(a * b, n)
            rows.append(("mul", a, b, exp, res, res == exp))
    return rows


def _test_muli():
    """Exhaustively test multiplication by a classical constant."""
    n = TOTAL_QUBITS // 2
    rows = []
    vals = list(_range_signed(n))
    total = len(vals) * len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(
        f"muli: testing a and b in range {min_val}..{max_val}, {total} operations"
    )
    for a in vals:
        for b in vals:
            print(f"muli: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            ar = initialize_variable(qc, a, "a")
            out = muli(qc, ar, b)
            measure(qc, out)
            res = _run_circuit(qc)[f"{out.name}_measure"]
            exp = _twos(a * b, n)
            rows.append(("muli", a, b, exp, res, res == exp))
    return rows


def _test_division():
    """Exhaustively test the ``div`` helper."""
    # total qubits = 2(n^2 + n -1)
    n = 1
    while 2 * (n * n + n - 1) <= TOTAL_QUBITS:
        n += 1
    n -= 1
    rows = []
    min_a = 0
    max_a = (1 << (n - 1)) - 1
    min_b = 1
    max_b = (1 << (n - 1)) - 1
    total = (max_a - min_a + 1) * (max_b - min_b + 1)
    print(
        f"div: testing a in {min_a}..{max_a} and b in {min_b}..{max_b}, {total} operations"
    )
    for a in range(min_a, max_a + 1):
        for b in range(min_b, max_b + 1):
            print(f"div: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            dividend = initialize_variable(qc, a, "n")
            divisor = initialize_variable(qc, b, "d")
            quot = QuantumRegister(n - 1, name="q")
            rem = QuantumRegister(n, name="r")
            qc.add_register(quot)
            qc.add_register(rem)
            div_unsigned(qc, dividend, divisor, quot, rem)
            measure(qc, quot)
            measure(qc, rem)
            res = _run_circuit(qc)
            q_res = res.get("q_measure", 0)
            r_res = res.get("r_measure", 0)
            exp_q = a // b
            exp_r = a % b
            ok = q_res == exp_q and r_res == exp_r
            rows.append(("div", a, b, f"({exp_q},{exp_r})", f"({q_res},{r_res})", ok))
    return rows


def _test_divi():
    """Exhaustively test division by a classical constant."""
    n = TOTAL_QUBITS // 3
    rows = []
    vals = list(_range_signed(n))
    min_val = vals[0]
    max_val = vals[-1]
    # exclude zero for divisor
    b_vals = [v for v in vals if v != 0]
    total = len(vals) * len(b_vals)
    print(
        f"divi: testing a in {min_val}..{max_val} and b in {min_val}..{max_val} (excluding 0), {total} operations"
    )
    for a in vals:
        for b in b_vals:
            print(f"divi: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            ar = initialize_variable(qc, a, "a")
            out = divi(qc, ar, b)
            measure(qc, out)
            res = _run_circuit(qc)[f"{out.name}_measure"]
            exp = int(a / b)
            rows.append(("divi", a, b, exp, res, res == exp))
    return rows


def _print_table(rows, csv_path=None):
    """Print results and optionally save them to ``csv_path``."""
    print("| op | a | b | expected | measured | ok |")
    writer = None
    if csv_path:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        file = open(csv_path, "w", newline="")
        writer = csv.writer(file)
        writer.writerow(["op", "a", "b", "expected", "measured", "ok"])
    for op, a, b, exp, res, ok in rows:
        print(f"| {op} | {a} | {b} | {exp} | {res} | {ok} |")
        if writer:
            writer.writerow([op, a, b, exp, res, ok])
    if writer:
        file.close()
    if any(not r[-1] for r in rows):
        print("Result check: FAIL")
    else:
        print("Result check: PASS")


if __name__ == "__main__":
    all_rows = []
    all_rows += _test_add()
    all_rows += _test_addi()
    all_rows += _test_sub()
    all_rows += _test_subi()
    all_rows += _test_mul()
    all_rows += _test_muli()
    all_rows += _test_division()
    all_rows += _test_divi()
    _print_table(all_rows, csv_path="test_log/test_arithmetics.csv")


