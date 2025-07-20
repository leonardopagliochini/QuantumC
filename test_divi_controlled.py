from qiskit import QuantumCircuit, QuantumRegister
from q_arithmetics_controlled import set_number_of_bits, initialize_variable, measure, divi_controlled
import utils_test as tu

TOTAL_QUBITS = 8


def main():
    n = TOTAL_QUBITS // 2
    rows = []
    vals = [-2, -1, 0, 1, 2]
    divisors = [-2, -1, 1, 2]
    print("divi_controlled: testing a in -2..2 and divisor in {-2,-1,1,2}, control in {0,1}")
    for ctrl_val in [0, 1]:
        for a in vals:
            for d in divisors:
                print(f"divi_controlled: a={a}, divisor={d}, control={ctrl_val}")
                set_number_of_bits(n)
                qc = QuantumCircuit()
                a_bin = tu.to_binary(a, n)
                d_bin = tu.to_binary(d, n)
                ar = initialize_variable(qc, a, "a")
                ctrl = QuantumRegister(1, "ctrl")
                qc.add_register(ctrl)
                if ctrl_val == 1:
                    qc.x(ctrl[0])
                quot, rem = divi_controlled(qc, ar, d, ctrl[0])
                measure(qc, quot)
                measure(qc, rem)
                values = tu.run_circuit(qc)
                q_bits, q_val = values[f"{quot.name}_measure"]
                r_bits, r_val = values[f"{rem.name}_measure"]
                if ctrl_val == 1:
                    exp_q = int(a / d)
                    exp_r = a - exp_q * d
                else:
                    exp_q = 0
                    exp_r = 0
                exp_q_bin = tu.to_binary(exp_q, n)
                exp_r_bin = tu.to_binary(exp_r, n)
                rows.append(("divi_controlled", ctrl_val, a, a_bin, d, d_bin, exp_q, exp_q_bin, exp_r, exp_r_bin, q_val, q_bits, r_val, r_bits, (q_val == exp_q) and (r_val == exp_r)))
    tu.print_table(rows, csv_path="test_log/test_divi_controlled.csv", headers=["op","ctrl","a_dec","a_bin","d_dec","d_bin","exp_q_dec","exp_q_bin","exp_r_dec","exp_r_bin","meas_q_dec","meas_q_bin","meas_r_dec","meas_r_bin","ok"])


if __name__ == "__main__":
    main()
