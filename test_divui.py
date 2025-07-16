"""Stand-alone test for the ``divui`` helper with binary logging."""

from qiskit import QuantumCircuit
from q_arithmetics import set_number_of_bits, initialize_variable, measure, divui
import test_utils as tu

TOTAL_QUBITS = 10


def main():
    """Run the divui test and print the result table."""
    n = TOTAL_QUBITS // 2
    rows = []
    vals = list(tu.range_unsigned(n - 1))
    total = len(vals) * len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(f"divui: testing a and b in range {min_val}..{max_val}, {total} operations")
    for a in vals:
        for b in vals:
            if b == 0:
                continue
            print(f"divui: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            a_bin = tu.to_binary_unsigned(a, n)
            b_bin = tu.to_binary_unsigned(b, n)
            ar = initialize_variable(qc, a, "a")
            out = divui(qc, ar, b, a_val=a)
            measure(qc, out)
            res_bits, res = tu.run_circuit(qc, signed=False)[f"{out.name}_measure"]
            exp = a // b
            exp_bin = tu.to_binary_unsigned(exp, n)
            rows.append(("divui", a, a_bin, b, b_bin, exp, exp_bin, res, res_bits, res == exp))
    tu.print_table(rows, csv_path="test_log/test_divui.csv")


if __name__ == "__main__":
    main()
