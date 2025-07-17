"""Stand-alone test for the ``divu`` helper with binary logging."""

from qiskit import QuantumCircuit
from q_arithmetics import set_number_of_bits, initialize_variable, measure, divu
import utils_test as tu

TOTAL_QUBITS = 12

def main():
    n = TOTAL_QUBITS // 3
    rows = []
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
            quot, _ = divu(qc, ar, br)
            measure(qc, quot)
            res_bits, res = tu.run_circuit(qc, signed=False)[f"{quot.name}_measure"]
            exp = a // b
            exp_bin = tu.to_binary_unsigned(exp, n)
            rows.append(("divu", a, a_bin, b, b_bin, exp, exp_bin, res, res_bits, res == exp))
    tu.print_table(rows, csv_path="test_log/test_divu.csv")

if __name__ == "__main__":
    main()
