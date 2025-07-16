"""Stand-alone test for the ``mul`` helper with binary logging."""

from qiskit import QuantumCircuit
from q_arithmetics import set_number_of_bits, initialize_variable, measure, mul
import test_utils as tu

TOTAL_QUBITS = 12


def main():
    """Run the multiplication test and print the result table."""
    n = TOTAL_QUBITS // 3
    rows = []
    vals = list(tu.range_signed(n))
    total = len(vals) * len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(f"mul: testing a and b in range {min_val}..{max_val}, {total} operations")
    for a in vals:
        for b in vals:
            print(f"mul: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            a_bin = tu.to_binary(a, n)
            b_bin = tu.to_binary(b, n)
            ar = initialize_variable(qc, a, "a")
            br = initialize_variable(qc, b, "b")
            out = mul(qc, ar, br)
            measure(qc, out)
            res_bits, res = tu.run_circuit(qc)[f"{out.name}_measure"]
            exp = tu.twos(a * b, n)
            exp_bin = tu.to_binary(exp, n)
            rows.append(("mul", a, a_bin, b, b_bin, exp, exp_bin, res, res_bits, res == exp))
    tu.print_table(rows, csv_path="test_log/test_mul.csv")


if __name__ == "__main__":
    main()
