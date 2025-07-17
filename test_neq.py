"""Stand-alone test for the ``not_equal`` helper with binary logging."""

from qiskit import QuantumCircuit
from q_arithmetics import set_number_of_bits, initialize_variable, measure_single, not_equal
import utils_test as tu

TOTAL_QUBITS = 8


def main():
    n = TOTAL_QUBITS // 2
    rows = []
    vals = list(tu.range_signed(n))
    total = len(vals) * len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(f"neq: testing a and b in range {min_val}..{max_val}, {total} operations")
    for a in vals:
        for b in vals:
            print(f"neq: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            a_bin = tu.to_binary(a, n)
            b_bin = tu.to_binary(b, n)
            ar = initialize_variable(qc, a, "a")
            br = initialize_variable(qc, b, "b")
            out = not_equal(qc, ar, br)
            measure_single(qc, out, out._register.name + "_measure")
            res_bits, res = tu.run_circuit(qc)[f"{out._register.name}_measure"]
            exp = 1 if a != b else 0
            exp_bin = str(exp)
            rows.append(("neq", a, a_bin, b, b_bin, exp, exp_bin, res, res_bits, res == exp))
    tu.print_table(rows, csv_path="test_log/test_neq.csv")


if __name__ == "__main__":
    main()
