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
        mod_bits, mod_val = values[f"{ar.name}_measure"]
        sign_val = values[f"{sign.name}_measure"][1]

        exp_sign = 1 if a < 0 else 0
        exp_mod = abs(a)
        exp_mod_bin = tu.to_binary(exp_mod, n)

        ok = (mod_val == exp_mod) and (sign_val == exp_sign)

        rows.append(
            (
                "c2sm",
                a,
                a_bin,
                exp_sign,
                sign_val,
                exp_mod,
                exp_mod_bin,
                mod_val,
                mod_bits,
                ok,
            )
        )

    headers = [
        "op",
        "input_dec",
        "input_bin",
        "expected_sign",
        "measured_sign",
        "expected_mod_dec",
        "expected_mod_bin",
        "measured_mod_dec",
        "measured_mod_bin",
        "ok",
    ]

    tu.print_table(rows, csv_path="test_log/test_c2sm.csv", headers=headers)


if __name__ == "__main__":
    main()
