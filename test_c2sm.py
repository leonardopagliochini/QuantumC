from qiskit import QuantumCircuit
from qiskit.circuit import QuantumRegister
from q_arithmetics import set_number_of_bits, initialize_variable, measure, measure_single, twos_to_sign_magnitude
import test_utils as tu

TOTAL_QUBITS = 8


def main():
    n = TOTAL_QUBITS // 2
    rows = []
    vals = list(tu.range_signed(n))
    total = len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(f"c2sm: testing a in range {min_val}..{max_val}, {total} operations")
    for a in vals:
        set_number_of_bits(n)
        qc = QuantumCircuit()
        a_bin = tu.to_binary(a, n)
        ar = initialize_variable(qc, a, "a")
        sign = twos_to_sign_magnitude(qc, ar)
        measure(qc, ar)
        measure_single(qc, sign[0], sign.name + "_measure")
        values = tu.run_circuit(qc, signed=False)
        res_bits, res = values[f"{ar.name}_measure"]
        sign_val = values[f"{sign.name}_measure"][1]
        exp = abs(a)
        exp_bin = tu.to_binary(exp, n)
        exp_sign = 1 if a < 0 else 0
        ok = (res == exp) and (sign_val == exp_sign)
        rows.append(("c2sm", a, a_bin, exp_sign, str(exp_sign), exp, exp_bin, res, res_bits, ok))
    tu.print_table(rows, csv_path="test_log/test_c2sm.csv")


if __name__ == "__main__":
    main()
