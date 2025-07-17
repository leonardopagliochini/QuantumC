"""Stand-alone test for the ``divu`` helper with binary logging."""

from qiskit import QuantumCircuit
from q_arithmetics import (
    set_number_of_bits,
    initialize_variable,
    measure,
    divu,
)
import utils_test as tu

TOTAL_QUBITS = 12

def main():
    n = TOTAL_QUBITS // 3
    rows = []
    headers = [
        "op",
        "a_dec",
        "a_bin",
        "b_dec",
        "b_bin",
        "exp_q_dec",
        "exp_q_bin",
        "exp_r_dec",
        "exp_r_bin",
        "meas_q_dec",
        "meas_q_bin",
        "meas_r_dec",
        "meas_r_bin",
        "ok",
    ]
    vals = list(tu.range_unsigned(n - 1))
    total = len(vals) * len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(f"divu: testing a and b in range {min_val}..{max_val}, {total} operations")
    for a in vals:
        for b in vals:
            if b == 0:
                continue
            print(f"divu: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            a_bin = tu.to_binary_unsigned(a, n)
            b_bin = tu.to_binary_unsigned(b, n)
            ar = initialize_variable(qc, a, "a")
            br = initialize_variable(qc, b, "b")
            quot, rem = divu(qc, ar, br)
            measure(qc, quot)
            measure(qc, rem)
            values = tu.run_circuit(qc, signed=False)
            q_bits, q_val = values[f"{quot.name}_measure"]
            r_bits, r_val = values[f"{rem.name}_measure"]

            exp_q = a // b
            exp_q_bin = tu.to_binary_unsigned(exp_q, n)
            exp_r = a % b
            exp_r_bin = tu.to_binary_unsigned(exp_r, n)

            ok = (q_val == exp_q) and (r_val == exp_r)

            rows.append(
                (
                    "divu",
                    a,
                    a_bin,
                    b,
                    b_bin,
                    exp_q,
                    exp_q_bin,
                    exp_r,
                    exp_r_bin,
                    q_val,
                    q_bits,
                    r_val,
                    r_bits,
                    ok,
                )
            )
    tu.print_table(rows, csv_path="test_log/test_divu.csv", headers=headers)

if __name__ == "__main__":
    main()
