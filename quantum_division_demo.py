"""Demonstration of integer division using Qiskit-based helpers."""

from qiskit.circuit import QuantumCircuit, QuantumRegister
import q_arithmetics as qa


def build_division_circuit(dividend: int, divisor: int) -> QuantumCircuit:
    """Create a circuit dividing ``dividend`` by ``divisor``.

    Registers for dividend and divisor are initialized with classical values and
    passed to :func:`q_arithmetics.div`. The quotient and remainder registers are
    instantiated beforehand and populated by the function.

    Parameters
    ----------
    dividend : int
        Dividend for the operation.
    divisor : int
        Classical divisor.

    Returns
    -------
    QuantumCircuit
        Circuit containing the computation with measurements of quotient and
        remainder.
    """
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

    return circuit


if __name__ == "__main__":
    demo_circuit = build_division_circuit(6, 2)
    qa.simulate(demo_circuit)
