from qiskit import QuantumCircuit
from qiskit.circuit import QuantumRegister
from q_arithmetics import set_number_of_bits, initialize_variable, measure, measure_single, sign_magnitude_to_twos
import test_utils as tu

TOTAL_QUBITS = 8


def main():
    n = TOTAL_QUBITS // 2
    rows = []
    vals = list(tu.range_signed(n))
    total = len(vals)
    min_val = vals[0]
    max_val = vals[-1]
    print(f"sm2c2: testing a in range {min_val}..{max_val}, {total} operations")
    for a in vals:
        set_number_of_bits(n)
        qc = QuantumCircuit()
        magnitude = abs(a)
        sign_bit = 1 if a < 0 else 0
        mag_bin = tu.to_binary(magnitude, n)
        sign_bin = str(sign_bit)
        mag_reg = QuantumRegister(n, name="m")
        qc.add_register(mag_reg)
        for i in range(n):
            if (magnitude >> i) & 1:
                qc.x(mag_reg[i])
        sign = QuantumRegister(1, name="sign")
        qc.add_register(sign)
        if sign_bit:
            qc.x(sign[0])
        sign_magnitude_to_twos(qc, mag_reg, sign)
        measure(qc, mag_reg)
        measure_single(qc, sign[0], sign.name + "_measure")
        values = tu.run_circuit(qc)
        res_bits, res = values[f"{mag_reg.name}_measure"]
        res_sign = values[f"{sign.name}_measure"][1]
        exp = tu.twos(a, n)
        exp_bin = tu.to_binary(exp, n)
        ok = (res == exp) and (res_sign == sign_bit)
        rows.append(("sm2c2", a, mag_bin, sign_bit, sign_bin, exp, exp_bin, res, res_bits, ok))
    tu.print_table(rows, csv_path="test_log/test_sm2c2.csv")


if __name__ == "__main__":
    main()
