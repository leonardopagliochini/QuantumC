"""Stand-alone test for the ``divi`` helper with binary logging."""

from qiskit import QuantumCircuit
from q_arithmetics import set_number_of_bits, initialize_variable, measure, divi
import test_utils as tu

TOTAL_QUBITS = 12


def main():
    """Run the divi test and print the result table."""
    n = TOTAL_QUBITS // 3
    rows = []
    vals = list(tu.range_signed(n))
    min_val = vals[0]
    max_val = vals[-1]
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
            a_bin = tu.to_binary(a, n)
            b_bin = tu.to_binary(b, n)
            ar = initialize_variable(qc, a, "a")
            out = divi(qc, ar, b)
            measure(qc, out)
            res_bits, res = tu.run_circuit(qc)[f"{out.name}_measure"]
            exp = int(a / b)
            exp = tu.twos(exp, n)
            exp_bin = tu.to_binary(exp, n)
            rows.append(("divi", a, a_bin, b, b_bin, exp, exp_bin, res, res_bits, res == exp))
    tu.print_table(rows, csv_path="test_log/test_divi.csv")


if __name__ == "__main__":
    main()
