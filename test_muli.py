"""Stand-alone test for the ``muli`` helper with binary logging."""

from qiskit import QuantumCircuit
from q_arithmetics import set_number_of_bits, initialize_variable, measure, muli
import utils_test as tu

TOTAL_QUBITS = 8


def main():
    """Run the muli test and print the result table."""
    n = TOTAL_QUBITS // 2
    rows = []
    vals = list(tu.range_signed(n))
    total = len(vals) * len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(f"muli: testing a and b in range {min_val}..{max_val}, {total} operations")
    for a in vals:
        for b in vals:
            print(f"muli: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            a_bin = tu.to_binary(a, n)
            b_bin = tu.to_binary(b, n)
            ar = initialize_variable(qc, a, "a")
            out = muli(qc, ar, b)
            measure(qc, out)
            res_bits, res = tu.run_circuit(qc)[f"{out.name}_measure"]
            exp = a * b
            overflow = exp < min_val or exp > max_val
            exp_bin = tu.to_binary(exp, n) if not overflow else "overflow"
            ok = overflow or (res == exp)
            rows.append(("muli", a, a_bin, b, b_bin, exp, exp_bin, res, res_bits, ok))
    tu.print_table(rows, csv_path="test_log/test_muli.csv")


if __name__ == "__main__":
    main()
