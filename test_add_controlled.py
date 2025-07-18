from qiskit import QuantumCircuit, QuantumRegister
from q_arithmetics_controlled import set_number_of_bits, initialize_variable, measure, add_controlled
import utils_test as tu

TOTAL_QUBITS = 12


def main():
    n = TOTAL_QUBITS // 3
    rows = []
    vals = [-2, -1, 0, 1, 2]
    print("add_controlled: testing a and b in range -2..2, control=1")
    for a in vals:
        for b in vals:
            print(f"add_controlled: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()
            a_bin = tu.to_binary(a, n)
            b_bin = tu.to_binary(b, n)
            ar = initialize_variable(qc, a, "a")
            br = initialize_variable(qc, b, "b")
            ctrl = QuantumRegister(1, "ctrl")
            qc.add_register(ctrl)
            qc.x(ctrl[0])
            out = add_controlled(qc, ar, br, ctrl[0])
            measure(qc, out)
            res_bits, res = tu.run_circuit(qc)[f"{out.name}_measure"]
            exp = a + b
            exp_bin = tu.to_binary(exp, n)
            rows.append(("add_controlled", a, a_bin, b, b_bin, exp, exp_bin, res, res_bits, res == exp))
    tu.print_table(rows, csv_path="test_log/test_add_controlled.csv")


if __name__ == "__main__":
    main()
