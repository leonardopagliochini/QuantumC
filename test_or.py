from qiskit import QuantumCircuit
from q_arithmetics import (
    set_number_of_bits,
    initialize_bit,
    measure_single,
    logical_or as bit_or,
)
import utils_test as tu

TOTAL_QUBITS = 3

def main():
    n = 1
    rows = []
    vals = [0, 1]
    total = len(vals) * len(vals)
    min_val = 0
    max_val = 1
    print(f"or: testing a or b in range {min_val}..{max_val}, {total} operations")
    
    for a in vals:
        for b in vals:
            print(f"or: a={a}, b={b}")
            set_number_of_bits(n)
            qc = QuantumCircuit()

            # LSB of a and b only
            a_bit = a & 1
            b_bit = b & 1
            ar = initialize_bit(qc, a_bit, "a")
            br = initialize_bit(qc, b_bit, "b")

            out = bit_or(qc, ar, br)
            measure_single(qc, out, name="result")

            res_bitstr, res_val = tu.run_circuit(qc)["result"]

            exp = a_bit | b_bit
            exp_bin = tu.to_binary_unsigned(exp, 1)

            rows.append((
                "or",
                a,
                b,
                exp,
                res_val,
                res_val == exp
            ))

    tu.print_table(rows, csv_path="test_log/test_or.csv")

if __name__ == "__main__":
    main()
