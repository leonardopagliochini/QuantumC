from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit.circuit.library import QFT
import numpy as np
from qiskit_aer import AerSimulator

NUMBER_OF_BITS = 10


def int_to_twos_complement(value):
    """
    Convert an integer to its two's complement binary representation.
    Returns a list of bits (0 or 1), least significant bit first.
    """
    if value < 0:
        value = (1 << NUMBER_OF_BITS) + value
    return [(value >> i) & 1 for i in range(NUMBER_OF_BITS)]

def initialize_variable(qc, value, register_name=None):
    """
    Initialize a new quantum register with a classical integer value.
    If no name is given, generate a unique one.

    Args:
        qc (QuantumCircuit): The quantum circuit to modify.
        value (int): The integer value to initialize the register with.
        register_name (str, optional): The name of the quantum register. If None, a unique name will be generated.

    Returns:
        QuantumRegister: The newly created and initialized register.

    Raises:
        ValueError: If the value is outside the allowed two's complement range.
    """
    MIN_VAL = -2**(NUMBER_OF_BITS - 1)
    MAX_VAL = 2**(NUMBER_OF_BITS - 1) - 1

    if value < MIN_VAL or value > MAX_VAL:
        raise ValueError(
            f"Value {value} is out of range for two's complement representation "
            f"with {NUMBER_OF_BITS} bits: [{MIN_VAL}, {MAX_VAL}]"
        )

    if register_name is None:
        base_name = "qr"
        index = 0
        existing_names = {reg.name for reg in qc.qregs}
        while f"{base_name}{index}" in existing_names:
            index += 1
        register_name = f"{base_name}{index}"

    new_qreg = QuantumRegister(NUMBER_OF_BITS, name=register_name)
    qc.add_register(new_qreg)

    binary_value = int_to_twos_complement(value)

    for i, bit in enumerate(binary_value):
        if bit == 1:
            qc.x(new_qreg[i])

    return new_qreg

def add(qc, a_reg, b_reg):
    """
    Add two quantum registers using a quantum circuit.

    Args:
        qc (QuantumCircuit): The quantum circuit to modify.
        a_reg (QuantumRegister): The first quantum register.
        b_reg (QuantumRegister): The second quantum register.
    
    Returns:
        QuantumRegister: The quantum register containing the result of the addition.
    """

    # Apply QFT to a
    qc.append(QFT(NUMBER_OF_BITS, do_swaps=False), a_reg)

    # Add b into a using controlled phase gates
    for i in range(NUMBER_OF_BITS):
        for j in range(NUMBER_OF_BITS):
            if j <= i:
                angle = (2 * np.pi) / (2 ** (i - j + 1))
                qc.cp(angle, b_reg[j], a_reg[i])

    # Apply inverse QFT
    qc.append(QFT(NUMBER_OF_BITS, do_swaps=False).inverse(), a_reg)
    return a_reg

def addi(qc, qreg, b):
    """
    Add a classical integer to a quantum register using a quantum circuit.

    Args:
        qc (QuantumCircuit): The quantum circuit to modify.
        a_reg (QuantumRegister): The quantum register.
        b (int): The classical integer to add.
    
    Returns:
        QuantumRegister: The quantum register containing the result of the addition.
    """
    b_bin = int_to_twos_complement(b)
    qc.append(QFT(num_qubits=NUMBER_OF_BITS, do_swaps=False), qreg)

    # Add classical value b (2's complement) via controlled phase rotations
    b_int = int(''.join(str(x) for x in b_bin[::-1]), 2)
    if b >= 0:
        b_val = b_int
    else:
        b_val = b_int - (1 << NUMBER_OF_BITS) 

    for j in range(NUMBER_OF_BITS):
        angle = (b_val * 2 * np.pi) / (2 ** (j + 1))
        qc.p(angle, qreg[j])

    # Apply inverse QFT
    qc.append(QFT(num_qubits=NUMBER_OF_BITS, do_swaps=False).inverse(), qreg)
    return qreg

def invert(qc, qreg):
    """
    Invert the sign of a value in two's complement stored in a quantum register:
    apply bitwise NOT and add 1.

    Args:
        qc (QuantumCircuit): The quantum circuit to modify.
        qreg (QuantumRegister): The quantum register to negate.

    Returns:
        QuantumRegister: The modified quantum register (now contains -x).
    """
    # Step 1: Bitwise NOT (apply X to every qubit)
    for qubit in qreg:
        qc.x(qubit)

    # Step 2: Add 1 using addi()
    addi(qc, qreg, 1)

    return qreg


def sub(qc, a_reg, b_reg):
    """
    Subtract the contents of b_reg from a_reg using two's complement:
    a - b = a + (-b)

    Args:
        qc (QuantumCircuit): The quantum circuit to modify.
        a_reg (QuantumRegister): The minuend register (a).
        b_reg (QuantumRegister): The subtrahend register (b).
    
    Returns:
        QuantumRegister: The register containing the result (in a_reg).
    """
    # Invert the sign of b (i.e., compute -b)
    invert(qc, b_reg)

    # Add -b to a
    result = add(qc, a_reg, b_reg)

    # Invert the sign of b back to its original value
    invert(qc, b_reg)
    return result

def subi(qc, qreg, b):
    """
    Subtract a classical integer from a quantum register using two's complement:
    a - b = a + (-b)

    Args:
        qc (QuantumCircuit): The quantum circuit to modify.
        qreg (QuantumRegister): The quantum register to subtract from.
        b (int): The classical integer to subtract.
    
    Returns:
        QuantumRegister: The quantum register containing the result.
    """
    return addi(qc, qreg, -b)


def mul(qc, a_reg, b_reg):
    """
    Multiply two quantum registers using a shift-and-add quantum circuit.

    Args:
        qc (QuantumCircuit): The quantum circuit to modify.
        a_reg (QuantumRegister): The multiplicand register.
        b_reg (QuantumRegister): The multiplier register.

    Returns:
        QuantumRegister: The result register containing the product.
    """
    result_size = 2 * NUMBER_OF_BITS
    result_reg = QuantumRegister(result_size, name="product")
    qc.add_register(result_reg)

    for i in range(NUMBER_OF_BITS):
        # Create a temporary shifted version of a_reg mapped to result_reg[i:i+N]
        shifted_a_indices = list(range(i, i + NUMBER_OF_BITS))
        if max(shifted_a_indices) >= result_size:
            continue  # Skip if out of bounds

        # Temporary QFT on target slice of result_reg
        target_slice = [result_reg[j] for j in shifted_a_indices]
        qc.append(QFT(NUMBER_OF_BITS, do_swaps=False), target_slice)

        for m in range(NUMBER_OF_BITS):
            for n in range(NUMBER_OF_BITS):
                if n <= m:
                    angle = (2 * np.pi) / (2 ** (m - n + 1))
                    qc.cp(angle, b_reg[i], result_reg[i + m])  # Controlled on b[i]

        qc.append(QFT(NUMBER_OF_BITS, do_swaps=False).inverse(), target_slice)

    return result_reg



def measure(qc, qreg):
    """
    Measure a quantum register and store the result in a classical register.

    Args:
        qc (QuantumCircuit): The quantum circuit to modify.
        qreg (QuantumRegister): The quantum register to measure.
    """
    c_reg = ClassicalRegister(len(qreg), name=qreg.name+'_measure')
    qc.add_register(c_reg)
    qc.measure(qreg, c_reg)

def simulate(qc, shots=1024):
    """
    Simulate the quantum circuit and print the interpreted two's complement value
    for each measured quantum register.

    Args:
        qc (QuantumCircuit): The quantum circuit to simulate.
        shots (int): The number of shots for the simulation.
    """
    backend = AerSimulator(method='matrix_product_state')
    transpiled = transpile(qc, backend)
    job = backend.run(transpiled, shots=shots)
    counts = job.result().get_counts()

    # Get most frequent measurement result
    most_common = max(counts, key=counts.get)
    bitstring = most_common.replace(' ', '')  # Qiskit returns MSB leftmost

    print(f"Measured bitstring: {bitstring}")

    offset = 0
    for reg in reversed(qc.qregs):  # Reverse: Qiskit stacks qubits from last to first
        reg_size = len(reg)
        reg_bits = bitstring[offset:offset + reg_size]
        offset += reg_size

        if len(reg_bits) < reg_size:
            print(f"Register {reg.name}: not fully measured or missing.")
            continue

        # Interpret as two's complement
        unsigned = int(reg_bits, 2)
        if reg_bits[0] == '1':
            signed = unsigned - (1 << reg_size)
        else:
            signed = unsigned

        print(f"Register {reg.name}: binary = {reg_bits}, value (2's complement) = {signed}")





