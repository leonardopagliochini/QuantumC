from q_arithmetics import *

def test_initialize_and_measure(value):
    qc = QuantumCircuit()
    reg = initialize_variable(qc, value, "a")
    measure(qc, reg)
    print(f"\nTest: Initialize {value}")
    result = simulate(qc, shots=1)
    assert result == value, f"Expected {value}, got {result}"


def test_add(a, b):
    set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    b_reg = initialize_variable(qc, b, "b")
    result_reg = add(qc, a_reg, b_reg)
    measure(qc, result_reg)
    print(f"\nTest: {a} + {b}")
    result = simulate(qc, shots=1)
    expected = (a + b) % (1 << NUMBER_OF_BITS)
    if expected >= 2**(NUMBER_OF_BITS - 1):
        expected -= 1 << NUMBER_OF_BITS
    assert result == expected, f"Expected {expected}, got {result}"


def test_addi(a, b):
    set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    result_reg = addi(qc, a_reg, b)
    measure(qc, result_reg)
    print(f"\nTest: {a} + {b} (addi)")
    result = simulate(qc, shots=1)
    expected = (a + b) % (1 << NUMBER_OF_BITS)
    if expected >= 2**(NUMBER_OF_BITS - 1):
        expected -= 1 << NUMBER_OF_BITS
    assert result == expected, f"Expected {expected}, got {result}"


def test_sub(a, b):
    set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    b_reg = initialize_variable(qc, b, "b")
    result_reg = sub(qc, a_reg, b_reg)
    measure(qc, result_reg)
    print(f"\nTest: {a} - {b}")
    result = simulate(qc, shots=1)
    expected = (a - b) % (1 << NUMBER_OF_BITS)
    if expected >= 2**(NUMBER_OF_BITS - 1):
        expected -= 1 << NUMBER_OF_BITS
    assert result == expected, f"Expected {expected}, got {result}"


def test_subi(a, b):
    set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    result_reg = subi(qc, a_reg, b)
    measure(qc, result_reg)
    print(f"\nTest: {a} - {b} (subi)")
    result = simulate(qc, shots=1)
    expected = (a - b) % (1 << NUMBER_OF_BITS)
    if expected >= 2**(NUMBER_OF_BITS - 1):
        expected -= 1 << NUMBER_OF_BITS
    assert result == expected, f"Expected {expected}, got {result}"


def test_mul(a, b):
    set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    b_reg = initialize_variable(qc, b, "b")
    result_reg = mul(qc, a_reg, b_reg)
    measure(qc, result_reg)
    print(f"\nTest: {a} * {b}")
    result = simulate(qc, shots=1)
    expected = (a * b) % (1 << NUMBER_OF_BITS)
    if expected >= 2**(NUMBER_OF_BITS - 1):
        expected -= 1 << NUMBER_OF_BITS
    assert result == expected, f"Expected {expected}, got {result}"


def test_muli(a, b):
    set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    result_reg = muli(qc, a_reg, b)
    measure(qc, result_reg)
    print(f"\nTest: {a} * {b} (muli)")
    result = simulate(qc, shots=1)
    expected = (a * b) % (1 << NUMBER_OF_BITS)
    if expected >= 2**(NUMBER_OF_BITS - 1):
        expected -= 1 << NUMBER_OF_BITS
    assert result == expected, f"Expected {expected}, got {result}"


def test_divi(a, b):
    set_number_of_bits(6)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    result_reg = divi(qc, a_reg, b)
    measure(qc, result_reg)
    print(f"\nTest: {a} / {b} (divi)")
    result = simulate(qc, shots=1)
    expected = int(a / b)  # truncate towards zero
    assert result == expected, f"Expected {expected}, got {result}"


if __name__ == "__main__":
    test_initialize_and_measure(3)
    test_initialize_and_measure(-2)

    test_add(2, 3)
    test_add(-2, 1)
    test_add(-3, -2)

    test_addi(1, 2)
    test_addi(-1, -2)

    test_sub(3, 1)
    test_sub(-2, 2)

    test_subi(2, 1)
    test_subi(-1, -2)

    test_mul(2, 3)
    test_mul(-2, 2)

    test_muli(2, 3)
    test_muli(-2, -1)

    test_divi(6, 2)
    test_divi(-4, 2)
    test_divi(7, -2)
