"""Utility helpers for q_arithmetics tests."""

import csv
import os
from qiskit import transpile
from q_arithmetics import AerSimulator, QasmSimulatorPy, int_to_twos_complement


def range_signed(n):
    """Return all signed integers representable with ``n`` bits."""
    min_val = -(1 << (n - 1))
    max_val = (1 << (n - 1)) - 1
    return range(min_val, max_val + 1)


def range_unsigned(n):
    """Return all unsigned integers representable with ``n`` bits."""
    return range(0, 1 << n)


def twos(value, n):
    """Convert ``value`` to a signed ``n``-bit integer."""
    value %= 1 << n
    if value >= 1 << (n - 1):
        value -= 1 << n
    return value


def to_binary(value, n):
    """Return the two's complement ``n``-bit binary string for ``value``."""
    bits = int_to_twos_complement(value)
    return "".join(str(b) for b in bits[::-1])


def to_binary_unsigned(value, n):
    """Return the ``n``-bit binary string for unsigned ``value``."""
    bits = [(value >> i) & 1 for i in range(n)]
    return "".join(str(b) for b in bits[::-1])


def run_circuit(qc, signed=True):
    """Simulate ``qc`` and return measured registers as (bits, int)."""
    if AerSimulator is not None:
        backend = AerSimulator(method="matrix_product_state")
        compiled = transpile(qc, backend)
    else:
        backend = QasmSimulatorPy()
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
            values[creg.name] = ("".rjust(len(creg), "0"), 0)
            continue
        unsigned = int(reg_bits, 2)
        if signed and reg_bits[0] == "1" and len(creg) > 1:
            sval = unsigned - (1 << len(creg))
        else:
            sval = unsigned
        values[creg.name] = (reg_bits, sval)
    return values


def print_table(rows, csv_path=None, headers=None):
    """Print ``rows`` and optionally write them to ``csv_path``.

    ``rows`` should be a sequence of iterables containing the values to print.
    ``headers`` can be provided to customise the column names.  If omitted,
    the default 10-column format is used for backwards compatibility.
    """

    default_headers = [
        "op",
        "a_dec",
        "a_bin",
        "b_dec",
        "b_bin",
        "expected_dec",
        "expected_bin",
        "measured_dec",
        "measured_bin",
        "ok",
    ]
    if headers is None:
        headers = default_headers

    print("| " + " | ".join(headers) + " |")

    writer = None
    if csv_path:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        file = open(csv_path, "w", newline="")
        writer = csv.writer(file)
        writer.writerow(headers)

    for row in rows:
        print("| " + " | ".join(str(x) for x in row) + " |")
        if writer:
            writer.writerow(list(row))

    if writer:
        file.close()

    if any(not r[-1] for r in rows):
        print("Result check: FAIL")
    else:
        print("Result check: PASS")
