from qiskit import QuantumCircuit, QuantumRegister
from q_arithmetics_controlled import set_number_of_bits, initialize_variable, measure, div_controlled
import utils_test as tu

TOTAL_QUBITS = 12


def main():
    n = TOTAL_QUBITS // 3
    rows = []
    vals = [-2, -1, 1, 2]
    print("div_controlled: testing a,b in {-2,-1,1,2}, control in {0,1}")
    for ctrl_val in [0, 1]:
        for a in vals:
            for b in vals:
                if b == 0:
                    continue
                print(f"div_controlled: a={a}, b={b}, control={ctrl_val}")
                set_number_of_bits(n)
                qc = QuantumCircuit()
                a_bin = tu.to_binary(a, n)
                b_bin = tu.to_binary(b, n)
                ar = initialize_variable(qc, a, "a")
                br = initialize_variable(qc, b, "b")
                ctrl = QuantumRegister(1, "ctrl")
                qc.add_register(ctrl)
                if ctrl_val == 1:
                    qc.x(ctrl[0])
                quot, rem = div_controlled(qc, ar, br, ctrl[0])
                measure(qc, quot)
                measure(qc, rem)
                values = tu.run_circuit(qc)
                q_bits, q_val = values[f"{quot.name}_measure"]
                r_bits, r_val = values[f"{rem.name}_measure"]
                if ctrl_val == 1:
                    exp_q = int(a / b)
                    exp_r = a - exp_q * b
                else:
                    exp_q = 0
                    exp_r = 0
                exp_q_bin = tu.to_binary(exp_q, n)
                exp_r_bin = tu.to_binary(exp_r, n)
                rows.append(("div_controlled", ctrl_val, a, a_bin, b, b_bin, exp_q, exp_q_bin, exp_r, exp_r_bin, q_val, q_bits, r_val, r_bits, (q_val == exp_q) and (r_val == exp_r)))
    tu.print_table(rows, csv_path="test_log/test_div_controlled.csv", headers=[
        "op","ctrl","a_dec","a_bin","b_dec","b_bin","exp_q_dec","exp_q_bin","exp_r_dec","exp_r_bin","meas_q_dec","meas_q_bin","meas_r_dec","meas_r_bin","ok"])


if __name__ == "__main__":
    main()
