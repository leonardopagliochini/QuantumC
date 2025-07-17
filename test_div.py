"""Stand-alone test for the `div` helper with binary logging."""

from qiskit import QuantumCircuit
from q_arithmetics import (
    set_number_of_bits,
    initialize_variable,
    measure,
    div,
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
    vals = list(tu.range_signed(n))
    total = len(vals) * len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(f"div: testing a and b in range {min_val}..{max_val}, {total} operations")
    for a in vals:
        for b in vals:
            if b == 0:
                continue
            print(f"div: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            a_bin = tu.to_binary(a, n)
            b_bin = tu.to_binary(b, n)
            ar = initialize_variable(qc, a, "a")
            br = initialize_variable(qc, b, "b")
            quot, rem = div(qc, ar, br)
            measure(qc, quot)
            measure(qc, rem)
            values = tu.run_circuit(qc)
            q_bits, q_val = values[f"{quot.name}_measure"]
            r_bits, r_val = values[f"{rem.name}_measure"]

            exp_q = int(a / b)
            exp_r = a - exp_q * b
            overflow_q = exp_q < min_val or exp_q > max_val
            overflow_r = exp_r < min_val or exp_r > max_val
            exp_q_bin = tu.to_binary(exp_q, n) if not overflow_q else "overflow"
            exp_r_bin = tu.to_binary(exp_r, n) if not overflow_r else "overflow"

            ok = (q_val == exp_q) and (r_val == exp_r)

            rows.append(
                (
                    "div",
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
    tu.print_table(rows, csv_path="test_log/test_div.csv", headers=headers)


if __name__ == "__main__":
    main()
