from qiskit import QuantumCircuit
from q_arithmetics import set_number_of_bits, initialize_variable, measure, abs_val
import test_utils as tu

TOTAL_QUBITS = 8


def main():
    n = TOTAL_QUBITS // 2
    rows = []
    vals = list(tu.range_signed(n))
    total = len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(f"abs: testing a in range {min_val}..{max_val}, {total} operations")
    for a in vals:
        set_number_of_bits(n)
        qc = QuantumCircuit()
        a_bin = tu.to_binary(a, n)
        ar = initialize_variable(qc, a, "a")
        out = abs_val(qc, ar)
        measure(qc, out)
        res_bits, res = tu.run_circuit(qc, signed=False)[f"{out.name}_measure"]
        exp = abs(a)
        exp_bin = tu.to_binary(exp, n)
        rows.append(("abs", a, a_bin, '', '', exp, exp_bin, res, res_bits, res == exp))
    tu.print_table(rows, csv_path="test_log/test_abs.csv")


if __name__ == "__main__":
    main()
