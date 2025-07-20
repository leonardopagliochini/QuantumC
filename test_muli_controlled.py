from qiskit import QuantumCircuit, QuantumRegister
from q_arithmetics_controlled import set_number_of_bits, initialize_variable, measure, muli_controlled
import utils_test as tu

TOTAL_QUBITS = 8


def main():
    n = TOTAL_QUBITS // 2
    rows = []
    vals = [-2, -1, 0, 1, 2]
    consts = [-2, -1, 1, 2]
    print("muli_controlled: testing a in range -2..2 and c in {-2,-1,1,2}, control in {0,1}")
    for ctrl_val in [0, 1]:
        for a in vals:
            for c in consts:
                print(f"muli_controlled: a={a}, c={c}, control={ctrl_val}")
                set_number_of_bits(n)
                qc = QuantumCircuit()
                a_bin = tu.to_binary(a, n)
                c_bin = tu.to_binary(c, n)
                ar = initialize_variable(qc, a, "a")
                ctrl = QuantumRegister(1, "ctrl")
                qc.add_register(ctrl)
                if ctrl_val == 1:
                    qc.x(ctrl[0])
                out = muli_controlled(qc, ar, c, ctrl[0])
                measure(qc, out)
                res_bits, res = tu.run_circuit(qc)[f"{out.name}_measure"]
                exp = a * c if ctrl_val == 1 else 0
                exp_bin = tu.to_binary(exp, n)
                rows.append(("muli_controlled", ctrl_val, a, a_bin, c, c_bin, exp, exp_bin, res, res_bits, res == exp))
    tu.print_table(
        rows,
        csv_path="test_log/test_muli_controlled.csv",
        headers=[
            "op",
            "ctrl",
            "a_dec",
            "a_bin",
            "c_dec",
            "c_bin",
            "expected_dec",
            "expected_bin",
            "measured_dec",
            "measured_bin",
            "ok",
        ],
    )


if __name__ == "__main__":
    main()
