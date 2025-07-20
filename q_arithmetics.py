"""Utility functions implementing arithmetic and comparison on quantum data."""

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit.circuit.library.standard_gates import PhaseGate
from qiskit.circuit.library import QFT, RGQFTMultiplier
from qiskit.providers.basic_provider import BasicSimulator
import numpy as np
try:
    from qiskit_aer import AerSimulator
except Exception:  # pragma: no cover - optional dependency
    AerSimulator = None

NUMBER_OF_BITS = 4

def set_number_of_bits(n):
    """
    Set the number of bits for two's complement representation.
    This function should be called before any other operations.
    
    Args:
        n (int): The number of bits to use for two's complement representation.
    """
    global NUMBER_OF_BITS
    if n <= 0:
        raise ValueError("Number of bits must be a positive integer.")
    NUMBER_OF_BITS = n


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

def add_in_place(qc, a_reg, b_reg):
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

def add(qc, a_reg, b_reg):
    n = len(a_reg)

    # Generate a unique name
    existing_names = {reg.name for reg in qc.qregs}
    index = 0
    while f"sum{index}" in existing_names:
        index += 1
    sum_name = f"sum{index}"

    s_reg = QuantumRegister(n, name=sum_name)
    qc.add_register(s_reg)

    # Apply QFT to s_reg (output register)
    qc.append(QFT(n, do_swaps=False), s_reg)

    # Apply controlled phase gates from a_reg and b_reg into s_reg
    for i in range(n):
        for j in range(n):
            if j <= i:
                angle = 2 * np.pi / (2 ** (i - j + 1))
                qc.cp(angle, a_reg[j], s_reg[i])
                qc.cp(angle, b_reg[j], s_reg[i])

    # Inverse QFT
    qc.append(QFT(n, do_swaps=False).inverse(), s_reg)

    return s_reg

def addi_in_place(qc, qreg, b):
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
    addi_in_place(qc, qreg, 1)

    return qreg

def addi(qc, a_reg, b):
    """
    Add a classical integer b to a quantum register a_reg,
    storing the result in a new quantum register (non-in-place).
    Leaves a_reg unchanged. Supports two's complement.

    Args:
        qc (QuantumCircuit): The quantum circuit to modify.
        a_reg (QuantumRegister): The quantum register to which b will be added.
        b (int): The classical integer to add.

    Returns:
        QuantumRegister: A new quantum register containing the result (a + b).
    """
    n = len(a_reg)
    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"sum{idx}" in existing:
        idx += 1
    s_reg = QuantumRegister(n, name=f"sum{idx}")
    qc.add_register(s_reg)

    # Apply QFT to s_reg (output register)
    qc.append(QFT(n, do_swaps=False), s_reg)

    # Add classical value b via phase rotations to s_reg
    b_bin = int_to_twos_complement(b)
    b_int = int(''.join(str(x) for x in b_bin[::-1]), 2)
    b_val = b_int if b >= 0 else b_int - (1 << n)

    for j in range(n):
        angle = (b_val * 2 * np.pi) / (2 ** (j + 1))
        qc.p(angle, s_reg[j])

    # Add a_reg to s_reg via controlled rotations
    for i in range(n):
        for j in range(n):
            if j <= i:
                angle = 2 * np.pi / (2 ** (i - j + 1))
                qc.cp(angle, a_reg[j], s_reg[i])

    # Inverse QFT
    qc.append(QFT(n, do_swaps=False).inverse(), s_reg)

    return s_reg



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

def twos_to_sign_magnitude(qc, qreg):
    """Convert ``qreg`` from two's complement to sign+magnitude representation.

    A new 1-qubit register is appended to ``qc`` storing the sign bit.  ``qreg``
    is modified in place to hold the absolute value of the original integer.

    Returns
    -------
    QuantumRegister
        The newly created sign register.
    """

    n = len(qreg)
    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"sign{idx}" in existing:
        idx += 1
    sign = QuantumRegister(1, name=f"sign{idx}")
    qc.add_register(sign)

    qc.cx(qreg[n - 1], sign[0])
    _controlled_invert_in_place(qc, qreg, sign[0])
    return sign


def sign_magnitude_to_twos(qc, mag_reg, sign_reg):
    """Convert sign+magnitude representation back to two's complement."""

    _controlled_invert_in_place(qc, mag_reg, sign_reg[0])
    return mag_reg


def abs_val(qc, qreg):
    """Compute the absolute value of ``qreg`` in place and return it."""

    twos_to_sign_magnitude(qc, qreg)
    return qreg

def mul(qc, a_reg, b_reg):
    """
    Multiply two quantum registers using QFT-based logic.
    Result is stored in an n-bit register (i.e. modulo 2^n).

    Args:
        qc (QuantumCircuit): The quantum circuit to modify.
        a_reg (QuantumRegister): First multiplicand (n qubits).
        b_reg (QuantumRegister): Second multiplicand (n qubits).
        a_val (int): Optional known classical value of a (for sign correction).
        b_val (int): Optional known classical value of b.

    Returns:
        QuantumRegister: New n-bit register with the product modulo 2^n.
    """
    n = len(a_reg)
    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"prod{idx}" in existing:
        idx += 1
    out_reg = QuantumRegister(n, name=f"prod{idx}")
    qc.add_register(out_reg)

    # QFT on output
    qc.append(QFT(n, do_swaps=False), out_reg)

    # Controlled-controlled-phase rotations (truncated to n-bit result)
    for j in range(1, n + 1):
        for i in range(1, n + 1):
            for k in range(1, n + 1):  # ⬅️ Only n bits in the result
                lam = (2 * np.pi) / (2 ** (i + j + k - 2 * n))
                if lam != 0:
                    qc.append(PhaseGate(lam).control(2), [a_reg[n - j], b_reg[n - i], out_reg[k - 1]])

    # Inverse QFT
    qc.append(QFT(n, do_swaps=False).inverse(), out_reg)

    return out_reg

def muli(qc, a_reg, c, n_output_bits=None):
    """
    Multiply a quantum register by a classical constant c (can be negative).
    Stores result in a new register of size n_output_bits (default: len(a_reg)).

    Args:
        qc (QuantumCircuit): Circuit to modify.
        a_reg (QuantumRegister): Input register.
        c (int): Classical multiplier.
        n_output_bits (int): Number of bits in output (default = len(a_reg)).

    Returns:
        QuantumRegister: Output register with result (two's complement if needed).
    """
    n = len(a_reg)
    if n_output_bits is None:
        n_output_bits = n

    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"prod{idx}" in existing:
        idx += 1
    out_reg = QuantumRegister(n_output_bits, name=f"prod{idx}")
    qc.add_register(out_reg)

    # QFT
    qc.append(QFT(n_output_bits, do_swaps=False), out_reg)

    # Phase logic
    abs_c = abs(c)
    for j in range(n):
        for k in range(n_output_bits):
            angle = (2 * np.pi * abs_c * (2 ** j)) / (2 ** (k + 1))
            angle = angle % (2 * np.pi)
            if angle != 0:
                qc.cp(angle, a_reg[j], out_reg[k])

    # Inverse QFT
    qc.append(QFT(n_output_bits, do_swaps=False).inverse(), out_reg)

    # Sign correction
    if c < 0:
        invert(qc, out_reg)

    return out_reg


def divu(qc, a_reg, b_reg, n_output_bits=None):
    """
    Divide unsigned ``a_reg`` by unsigned ``b_reg`` using restoring division.

    Returns the quotient and remainder quantum registers. ``a_reg`` and ``b_reg``
    remain unchanged.

    Args:
        qc (QuantumCircuit): The quantum circuit to modify.
        a_reg (QuantumRegister): Dividend register (n qubits).
        b_reg (QuantumRegister): Divisor register (n qubits).
        n_output_bits (int, optional): Width of the output quotient register. Defaults to n.

    Returns:
        tuple: (quotient QuantumRegister, remainder QuantumRegister)
    """
    n = len(a_reg)
    assert len(b_reg) == n, "Registers a_reg and b_reg must have the same length"

    if n_output_bits is None:
        n_output_bits = n

    # Allocate quotient register
    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while (
        f"quotu{idx}" in existing
        or f"rem{idx}" in existing
        or f"sign{idx}" in existing
    ):
        idx += 1
    qout = QuantumRegister(n_output_bits, name=f"quotu{idx}")
    qc.add_register(qout)

    # Allocate remainder and sign ancilla
    rem = QuantumRegister(n, name=f"rem{idx}")
    sign = QuantumRegister(1, name=f"sign{idx}")
    qc.add_register(rem)
    qc.add_register(sign)

    # Begin restoring division algorithm
    for i in reversed(range(n_output_bits)):
        # Shift remainder left by 1
        for j in reversed(range(1, n)):
            qc.swap(rem[j], rem[j - 1])
        if i < n:
            qc.swap(rem[0], a_reg[i])

        # Subtract b from rem
        _sub_in_place(qc, rem, b_reg)

        # If result was negative, restore (conditionally add back)
        qc.cx(rem[n - 1], sign[0])  # MSB is 1 → negative
        _controlled_add_in_place(qc, rem, b_reg, sign[0])

        # Set quotient bit
        qc.x(qout[i])
        qc.cx(sign[0], qout[i])  # qout[i] = 1 if subtraction was successful

        # Uncompute sign flag
        qc.cx(qout[i], sign[0])
        qc.x(sign[0])

    return qout, rem


def divui(qc, a_reg, divisor, n_output_bits=None):
    """Divide ``a_reg`` by the classical ``divisor`` using restoring division.

    Returns the quotient and remainder registers.

    Args:
        qc (QuantumCircuit): Circuit to modify.
        a_reg (QuantumRegister): Dividend register.
        divisor (int): Unsigned integer divisor.
        n_output_bits (int, optional): Size of the output register. Defaults to
            ``len(a_reg)``.

    Returns:
        tuple: (quotient_register, remainder_register)
    """

    if divisor == 0:
        raise ValueError("Division by zero is not allowed.")

    n = len(a_reg)
    if n_output_bits is None:
        n_output_bits = n

    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while (
        f"quotu{idx}" in existing
        or f"rem{idx}" in existing
        or f"sign{idx}" in existing
    ):
        idx += 1
    qout = QuantumRegister(n_output_bits, name=f"quotu{idx}")
    qc.add_register(qout)

    rem = QuantumRegister(n, name=f"rem{idx}")
    qc.add_register(rem)

    sign = QuantumRegister(1, name=f"sign{idx}")
    qc.add_register(sign)

    for i in reversed(range(n_output_bits)):
        for j in reversed(range(1, n)):
            qc.swap(rem[j], rem[j - 1])
        if i < n:
            qc.swap(rem[0], a_reg[i])

        addi_in_place(qc, rem, -divisor)

        qc.cx(rem[n - 1], sign[0])

        _controlled_addi_in_place(qc, rem, divisor, sign[0])

        qc.x(qout[i])
        qc.cx(sign[0], qout[i])

        qc.cx(qout[i], sign[0])
        qc.x(sign[0])

    return qout, rem


def div(qc, a_reg, b_reg, n_output_bits=None):
    """Divide signed ``a_reg`` by signed ``b_reg``.

    The operation converts the inputs to sign+magnitude representation,
    performs unsigned restoring division on the magnitudes, and finally
    restores two's complement form on the outputs. The quotient sign is the
    XOR of the input signs, and the remainder sign matches ``a_reg``'s sign.

    Parameters
    ----------
    qc : QuantumCircuit
        Circuit to modify.
    a_reg : QuantumRegister
        Dividend register.
    b_reg : QuantumRegister
        Divisor register.
    n_output_bits : int, optional
        Size of the quotient register (default: ``len(a_reg)``).

    Returns
    -------
    tuple(QuantumRegister, QuantumRegister)
        Quotient and remainder registers in two's complement.
    """
    n = len(a_reg)
    assert len(b_reg) == n
    if n_output_bits is None:
        n_output_bits = n

    # Convert a and b to sign+magnitude
    sign_a = twos_to_sign_magnitude(qc, a_reg)
    sign_b = twos_to_sign_magnitude(qc, b_reg)

    # Perform unsigned division on magnitudes
    qout, rem = divu(qc, a_reg, b_reg, n_output_bits=n_output_bits)

    # Compute quotient sign (XOR of input signs)
    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"signq{idx}" in existing:
        idx += 1
    sign_q = QuantumRegister(1, name=f"signq{idx}")
    qc.add_register(sign_q)
    qc.cx(sign_a[0], sign_q[0])
    qc.cx(sign_b[0], sign_q[0])

    # Convert quotient and remainder back to two's complement
    sign_magnitude_to_twos(qc, qout, sign_q)
    qc.cx(qout[n_output_bits - 1], sign_q[0])

    sign_magnitude_to_twos(qc, rem, sign_a)

    # Restore original a and b from sign+magnitude (optional for reversibility)
    sign_magnitude_to_twos(qc, a_reg, sign_a)
    qc.cx(a_reg[n - 1], sign_a[0])
    sign_magnitude_to_twos(qc, b_reg, sign_b)
    qc.cx(b_reg[n - 1], sign_b[0])

    return qout, rem


def divi(qc, a_reg, divisor, n_output_bits=None):
    """Divide signed ``a_reg`` by signed integer ``divisor``.

    The implementation mirrors :func:`div` but with a classical divisor.

    Parameters
    ----------
    qc : QuantumCircuit
        Circuit to modify.
    a_reg : QuantumRegister
        Dividend register (two's complement).
    divisor : int
        Classical signed divisor.
    n_output_bits : int, optional
        Size of the quotient register (default: ``len(a_reg)``).

    Returns
    -------
    tuple(QuantumRegister, QuantumRegister)
        Quotient and remainder registers (two's complement).
    """

    if divisor == 0:
        raise ValueError("Division by zero is not allowed.")

    n = len(a_reg)
    if n_output_bits is None:
        n_output_bits = n

    # Convert a to sign+magnitude
    sign_a = twos_to_sign_magnitude(qc, a_reg)

    # Divide magnitudes using unsigned divui
    qout, rem = divui(qc, a_reg, abs(divisor), n_output_bits=n_output_bits)

    # Compute quotient sign
    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"signq{idx}" in existing:
        idx += 1
    sign_q = QuantumRegister(1, name=f"signq{idx}")
    qc.add_register(sign_q)

    if divisor < 0:
        qc.x(sign_q[0])
    qc.cx(sign_a[0], sign_q[0])

    # Convert back to two's complement
    sign_magnitude_to_twos(qc, qout, sign_q)
    qc.cx(qout[n_output_bits - 1], sign_q[0])

    sign_magnitude_to_twos(qc, rem, sign_a)

    # Optionally restore input (for reversibility)
    sign_magnitude_to_twos(qc, a_reg, sign_a)
    qc.cx(a_reg[n - 1], sign_a[0])

    return qout, rem


def _controlled_addi_in_place(qc, qreg, value, control):
    """Add ``value`` to ``qreg`` controlled by ``control`` qubit.

    This helper uses the QFT based addition logic from :func:`addi_in_place`
    but applies the phase rotations only when ``control`` is ``|1>``.  The
    function assumes that ``qreg`` is ``len(qreg)`` qubits long and that the
    global :data:`NUMBER_OF_BITS` matches this size.
    """

    n = len(qreg)
    qc.append(QFT(n, do_swaps=False), qreg)

    b_bin = int_to_twos_complement(value)
    b_int = int("".join(str(x) for x in b_bin[::-1]), 2)
    b_val = b_int if value >= 0 else b_int - (1 << n)

    for j in range(n):
        angle = (b_val * 2 * np.pi) / (2 ** (j + 1))
        if angle != 0:
            qc.cp(angle, control, qreg[j])

    qc.append(QFT(n, do_swaps=False).inverse(), qreg)


def _sub_in_place(qc, a_reg, b_reg):
    """Subtract ``b_reg`` from ``a_reg`` in place."""

    n = len(a_reg)
    assert len(b_reg) == n

    qc.append(QFT(n, do_swaps=False), a_reg)
    for i in range(n):
        for j in range(n):
            if j <= i:
                angle = -(2 * np.pi) / (2 ** (i - j + 1))
                qc.cp(angle, b_reg[j], a_reg[i])
    qc.append(QFT(n, do_swaps=False).inverse(), a_reg)
    return a_reg


def _controlled_add_in_place(qc, a_reg, b_reg, control):
    """Add ``b_reg`` to ``a_reg`` controlled by ``control``."""

    n = len(a_reg)
    assert len(b_reg) == n

    qc.append(QFT(n, do_swaps=False), a_reg)
    for i in range(n):
        for j in range(n):
            if j <= i:
                angle = 2 * np.pi / (2 ** (i - j + 1))
                gate = PhaseGate(angle).control(2)
                qc.append(gate, [control, b_reg[j], a_reg[i]])
    qc.append(QFT(n, do_swaps=False).inverse(), a_reg)
    return a_reg


def _controlled_invert_in_place(qc, qreg, control):
    """Negate ``qreg`` conditioned on ``control`` being ``|1>``."""

    for qubit in qreg:
        qc.cx(control, qubit)
    _controlled_addi_in_place(qc, qreg, 1, control)
    return qreg


def equal(qc, a_reg, b_reg):
    """Return a qubit set to ``|1>`` if ``a_reg == b_reg``."""

    n = len(a_reg)
    assert len(b_reg) == n

    xor_reg = QuantumRegister(n, name="xor")
    qc.add_register(xor_reg)
    for i in range(n):
        qc.cx(a_reg[i], xor_reg[i])
        qc.cx(b_reg[i], xor_reg[i])

    out = QuantumRegister(1, name="eq")
    qc.add_register(out)

    # out = 1 if all xor_reg bits are 0
    for qubit in xor_reg:
        qc.x(qubit)
    qc.x(out[0])
    qc.mcx(xor_reg, out[0])
    qc.x(out[0])
    for qubit in xor_reg:
        qc.x(qubit)
    return out[0]



def not_equal(qc, a_reg, b_reg):
    """
    Compares a != b and stores result in a single qubit.
    """
    eq = equal(qc, a_reg, b_reg)
    neq = QuantumRegister(1, name='neq')
    qc.add_register(neq)
    qc.x(neq[0])       # start in |1>
    qc.cx(eq, neq[0])  # flip to 0 if eq is 1 → result = not(eq)
    return neq[0]

def less_than(qc, a_reg, b_reg):
    """
    Compares a < b (signed) and stores the result in a single qubit.
    """
    n = len(a_reg)
    assert len(b_reg) == n

    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"bneg{idx}" in existing:
        idx += 1
    tmp_b = QuantumRegister(n, name=f"bneg{idx}")
    qc.add_register(tmp_b)
    for i in range(n):
        qc.cx(b_reg[i], tmp_b[i])
    invert(qc, tmp_b)  # compute -b

    diff = add(qc, a_reg, tmp_b)

    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"lt{idx}" in existing:
        idx += 1
    out = QuantumRegister(1, name=f"lt{idx}")
    qc.add_register(out)
    qc.cx(diff[n - 1], out[0])  # MSB = 1 → negative → a < b

    invert(qc, tmp_b)  # restore b
    return out[0]

def greater_than(qc, a_reg, b_reg):
    """Return a qubit set to ``|1>`` if ``a_reg`` is strictly greater than ``b_reg``."""

    return less_than(qc, b_reg, a_reg)

def less_equal(qc, a_reg, b_reg):
    """
    Compares a <= b and returns a single qubit with result.
    """
    gt = greater_than(qc, a_reg, b_reg)
    le = QuantumRegister(1, name='le')
    qc.add_register(le)
    qc.x(le[0])       # start in |1>
    qc.cx(gt, le[0])  # flip to 0 if gt is 1 → a <= b ⇔ not (a > b)
    return le[0]

def greater_equal(qc, a_reg, b_reg):
    """
    Compares a >= b and returns a single qubit with result.
    """
    lt = less_than(qc, a_reg, b_reg)
    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"ge{idx}" in existing:
        idx += 1
    ge = QuantumRegister(1, name=f"ge{idx}")
    qc.add_register(ge)
    qc.x(ge[0])
    qc.cx(lt, ge[0])
    return ge[0]

def measure_single(qc, qubit, name="result"):
    """Attach a classical bit measuring ``qubit`` to ``qc``."""

    creg = ClassicalRegister(1, name=name)
    qc.add_register(creg)
    qc.measure(qubit, creg[0])

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
    if AerSimulator is not None:
        backend = AerSimulator(method="matrix_product_state")
        transpiled = transpile(qc, backend)
    else:
        backend = BasicSimulator()
        transpiled = transpile(qc, backend)
    job = backend.run(transpiled, shots=shots)
    counts = job.result().get_counts()

    # Get most frequent measurement result
    most_common = max(counts, key=counts.get)
    bitstring = most_common.replace(' ', '')  # Qiskit returns MSB leftmost

    print(f"Measured bitstring: {bitstring}")

    offset = 0
    for creg in reversed(qc.cregs):
        reg_size = len(creg)
        reg_bits = bitstring[offset:offset + reg_size]
        offset += reg_size

        unsigned = int(reg_bits, 2)
        if reg_bits and reg_bits[0] == '1' and reg_size > 1:
            signed = unsigned - (1 << reg_size)
        else:
            signed = unsigned

        print(f"Register {creg.name}: binary = {reg_bits}, value (2's complement) = {signed}")

    return signed





