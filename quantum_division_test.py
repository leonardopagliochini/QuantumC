"""Test suite for the `div` helper in q_arithmetics."""

from qiskit.circuit import QuantumCircuit, QuantumRegister
from qiskit.providers.basic_provider import BasicSimulator
from qiskit import transpile
import q_arithmetics as qa


def run_division(dividend: int, divisor: int):
    """Return quotient and remainder from the quantum division circuit."""
    n_bits = max(dividend.bit_length(), divisor.bit_length()) + 1
    qa.set_number_of_bits(n_bits)
    circuit = QuantumCircuit()

    dividend_reg = qa.initialize_variable(circuit, dividend, "n")
    divisor_reg = qa.initialize_variable(circuit, divisor, "d")

    quotient_reg = QuantumRegister(qa.NUMBER_OF_BITS - 1, name="q")
    remainder_reg = QuantumRegister(qa.NUMBER_OF_BITS, name="r")
    circuit.add_register(quotient_reg)
    circuit.add_register(remainder_reg)

    qa.div(circuit, dividend_reg, divisor_reg, quotient_reg, remainder_reg)

    qa.measure(circuit, quotient_reg)
    qa.measure(circuit, remainder_reg)

    if qa.AerSimulator is not None:
        backend = qa.AerSimulator(method="matrix_product_state")
        compiled = transpile(circuit, backend)
    else:
        backend = BasicSimulator()
        compiled = circuit

    result = backend.run(compiled, shots=1).result()
    counts = result.get_counts()
    bitstring = max(counts, key=counts.get).replace(" ", "")

    offset = 0
    values = {}
    for creg in reversed(circuit.cregs):
        reg_bits = bitstring[offset:offset + len(creg)]
        offset += len(creg)
        unsigned = int(reg_bits, 2) if reg_bits else 0
        if creg.name not in {"q_measure", "r_measure"} \
                and reg_bits and reg_bits[0] == "1" and len(creg) > 1:
            values[creg.name] = unsigned - (1 << len(creg))
        else:
            values[creg.name] = unsigned

    return values.get("q_measure", 0), values.get("r_measure", 0)


def main():
    cases = [
        (6, 2),
        (7, 3),
        (5, 2),
        (8, 2),
        (3, 2),
        (1, 1),
        (0, 1),
        (7, 1),
    ]

    rows = []
    for dividend, divisor in cases:
        q_res, r_res = run_division(dividend, divisor)
        py_q = dividend // divisor
        py_r = dividend % divisor
        rows.append((dividend, divisor, py_q, py_r, q_res, r_res,
                     q_res == py_q and r_res == py_r))

    print("| dividend | divisor | expected q | expected r | measured q | measured r | correct |")
    for row in rows:
        print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} |")

    # Demonstrate overflow detection
    try:
        qa.set_number_of_bits(2)
        circuit = QuantumCircuit()
        qa.initialize_variable(circuit, 4)
    except ValueError as exc:
        print("Overflow test ->", exc)


if __name__ == "__main__":
    main()
