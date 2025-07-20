from qiskit import QuantumCircuit, QuantumRegister
from q_arithmetics_controlled import set_number_of_bits, initialize_variable, measure, addi_controlled
import utils_test as tu

TOTAL_QUBITS = 8


def main():
    n = TOTAL_QUBITS // 2
    rows = []
    vals = [-2, -1, 0, 1, 2]
    print("addi_controlled: testing a and b in range -2..2, control in {0,1}")
    for ctrl_val in [0, 1]:
        for a in vals:
            for b in vals:
                print(f"addi_controlled: a={a}, b={b}, control={ctrl_val}")
                set_number_of_bits(n)
                qc = QuantumCircuit()
                a_bin = tu.to_binary(a, n)
                b_bin = tu.to_binary(b, n)
                ar = initialize_variable(qc, a, "a")
                ctrl = QuantumRegister(1, "ctrl")
                qc.add_register(ctrl)
                if ctrl_val == 1:
                    qc.x(ctrl[0])
                out = addi_controlled(qc, ar, b, ctrl[0])
                measure(qc, out)
                res_bits, res = tu.run_circuit(qc)[f"{out.name}_measure"]
                exp = a + b if ctrl_val == 1 else 0
                exp_bin = tu.to_binary(exp, n)
                rows.append(("addi_controlled", ctrl_val, a, a_bin, b, b_bin, exp, exp_bin, res, res_bits, res == exp))
    tu.print_table(
        rows,
        csv_path="test_log/test_addi_controlled.csv",
        headers=[
            "op",
            "ctrl",
            "a_dec",
            "a_bin",
            "b_dec",
            "b_bin",
            "expected_dec",
            "expected_bin",
            "measured_dec",
            "measured_bin",
            "ok",
        ],
    )


if __name__ == "__main__":
    main()
