
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.circuit.library.standard_gates import PhaseGate
from qiskit.circuit.library import QFT
from .q_arithmetics import *
from .q_arithmetics import _sub_in_place, _controlled_add_in_place
import numpy as np

NUMBER_OF_BITS = 4

def int_to_twos_complement(value):
    if value < 0:
        value = (1 << NUMBER_OF_BITS) + value
    return [(value >> i) & 1 for i in range(NUMBER_OF_BITS)]


def initialize_variable_controlled(qc, value, control, register_name=None):
    """
    Initialize a new quantum register to a given integer value,
    conditioned on the control qubit being |1⟩.

    If control == 0, the register remains in the |0...0⟩ state.

    Args:
        qc (QuantumCircuit): The quantum circuit to modify.
        value (int): The integer value to conditionally initialize.
        control (Qubit): Control qubit.
        register_name (str, optional): Name of the new register.

    Returns:
        QuantumRegister: The initialized register.
    """
    MIN_VAL = -2**(NUMBER_OF_BITS - 1)
    MAX_VAL = 2**(NUMBER_OF_BITS - 1) - 1
    if value < MIN_VAL or value > MAX_VAL:
        raise ValueError(
            f"Value {value} is out of range for two's complement with {NUMBER_OF_BITS} bits"
        )

    if register_name is None:
        base_name = "qr"
        idx = 0
        existing = {reg.name for reg in qc.qregs}
        while f"{base_name}{idx}" in existing:
            idx += 1
        register_name = f"{base_name}{idx}"

    # Allocate the new quantum register
    new_qreg = QuantumRegister(NUMBER_OF_BITS, name=register_name)
    qc.add_register(new_qreg)

    # Get the 2's complement representation
    bits = int_to_twos_complement(value)

    # For each bit that's 1, apply a controlled X gate
    for i, bit in enumerate(bits):
        if bit == 1:
            qc.cx(control, new_qreg[i])

    return new_qreg

def sign_magnitude_to_twos(qc, qreg, sign_reg, control=None):
    """
    Convert a sign-magnitude encoded number to two's complement in-place.
    If control is provided, operation is conditional on control == 1.
    """
    n = len(qreg)
    for i in range(n):
        if control is None:
            qc.cx(sign_reg[0], qreg[i])
        else:
            qc.ccx(control, sign_reg[0], qreg[i])
    if control is None:
        addi_in_place_controlled(qc, qreg, 1, sign_reg[0])
    else:
        # AND(control, sign_reg[0]) → ancilla
        existing = {reg.name for reg in qc.qregs}
        idx = 0
        while f"condtmp{idx}" in existing:
            idx += 1
        anc = QuantumRegister(1, name=f"condtmp{idx}")
        qc.add_register(anc)
        qc.ccx(control, sign_reg[0], anc[0])
        addi_in_place_controlled(qc, qreg, 1, anc[0])
        qc.cx(control, anc[0])  # uncompute
        qc.cx(sign_reg[0], anc[0])
        qc.ccx(control, sign_reg[0], anc[0])  # reset anc to |0⟩

def twos_to_sign_magnitude(qc, qreg):
    """
    Extract sign bit and prepare sign register.
    Returns: QuantumRegister with 1 qubit (sign bit copied)
    """
    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"signbit{idx}" in existing:
        idx += 1
    sign_reg = QuantumRegister(1, name=f"signbit{idx}")
    qc.add_register(sign_reg)
    qc.cx(qreg[-1], sign_reg[0])  # Copy sign bit

    for i in range(len(qreg)):
        qc.cx(sign_reg[0], qreg[i])
    addi_in_place_controlled(qc, qreg, 1, sign_reg[0])

    return sign_reg


def _controlled_add_in_place(qc, a_reg, b_reg, external_control, control=None):
    """
    Controlled addition of b_reg into a_reg.
    Only applies if both control and external_control == 1.
    If control is None, uses only external_control.
    """
    n = len(a_reg)
    qc.append(QFT(n, do_swaps=False), a_reg)

    for i in range(n):
        for j in range(n):
            if j <= i:
                angle = 2 * np.pi / (2 ** (i - j + 1))
                if control is None:
                    qc.append(PhaseGate(angle).control(2), [external_control, b_reg[j], a_reg[i]])
                else:
                    qc.append(PhaseGate(angle).control(3), [control, external_control, b_reg[j], a_reg[i]])

    qc.append(QFT(n, do_swaps=False).inverse(), a_reg)
    return a_reg


def add_in_place_controlled(qc, a_reg, b_reg, control):
    n = len(a_reg)
    qc.append(QFT(n, do_swaps=False), a_reg)
    for i in range(n):
        for j in range(n):
            if j <= i:
                angle = (2 * np.pi) / (2 ** (i - j + 1))
                qc.append(PhaseGate(angle).control(2), [control, b_reg[j], a_reg[i]])
    qc.append(QFT(n, do_swaps=False).inverse(), a_reg)
    return a_reg

def add_controlled(qc, a_reg, b_reg, control):
    n = len(a_reg)
    existing_names = {reg.name for reg in qc.qregs}
    idx = 0
    while f"sum{idx}" in existing_names:
        idx += 1
    s_reg = QuantumRegister(n, name=f"sum{idx}")
    qc.add_register(s_reg)
    qc.append(QFT(n, do_swaps=False), s_reg)
    for i in range(n):
        for j in range(n):
            if j <= i:
                angle = 2 * np.pi / (2 ** (i - j + 1))
                qc.append(PhaseGate(angle).control(2), [control, a_reg[j], s_reg[i]])
                qc.append(PhaseGate(angle).control(2), [control, b_reg[j], s_reg[i]])
    qc.append(QFT(n, do_swaps=False).inverse(), s_reg)
    return s_reg

def addi_in_place_controlled(qc, qreg, b, control):
    n = len(qreg)
    b_bin = int_to_twos_complement(b)
    b_int = int(''.join(str(x) for x in b_bin[::-1]), 2)
    b_val = b_int if b >= 0 else b_int - (1 << n)
    qc.append(QFT(n, do_swaps=False), qreg)
    for j in range(n):
        angle = (b_val * 2 * np.pi) / (2 ** (j + 1))
        qc.cp(angle, control, qreg[j])
    qc.append(QFT(n, do_swaps=False).inverse(), qreg)
    return qreg

def addi_controlled(qc, a_reg, b, control):
    n = len(a_reg)
    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"sum{idx}" in existing:
        idx += 1
    s_reg = QuantumRegister(n, name=f"sum{idx}")
    qc.add_register(s_reg)
    b_bin = int_to_twos_complement(b)
    b_int = int(''.join(str(x) for x in b_bin[::-1]), 2)
    b_val = b_int if b >= 0 else b_int - (1 << n)
    qc.append(QFT(n, do_swaps=False), s_reg)
    for j in range(n):
        angle = (b_val * 2 * np.pi) / (2 ** (j + 1))
        qc.cp(angle, control, s_reg[j])
    for i in range(n):
        for j in range(n):
            if j <= i:
                angle = 2 * np.pi / (2 ** (i - j + 1))
                qc.append(PhaseGate(angle).control(2), [control, a_reg[j], s_reg[i]])
    qc.append(QFT(n, do_swaps=False).inverse(), s_reg)
    return s_reg

def invert_controlled(qc, qreg, control):
    for qubit in qreg:
        qc.cx(control, qubit)
    addi_in_place_controlled(qc, qreg, 1, control)
    return qreg

def sub_controlled(qc, a_reg, b_reg, control):
    invert_controlled(qc, b_reg, control)
    result = add_controlled(qc, a_reg, b_reg, control)
    invert_controlled(qc, b_reg, control)
    return result

def subi_controlled(qc, a_reg, b, control):
    return addi_controlled(qc, a_reg, -b, control)

def mul_controlled(qc, a_reg, b_reg, control):
    n = len(a_reg)
    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"prod{idx}" in existing:
        idx += 1
    out_reg = QuantumRegister(n, name=f"prod{idx}")
    qc.add_register(out_reg)
    qc.append(QFT(n, do_swaps=False), out_reg)
    for j in range(1, n + 1):
        for i in range(1, n + 1):
            for k in range(1, n + 1):
                lam = (2 * np.pi) / (2 ** (i + j + k - 2 * n))
                if lam != 0:
                    qc.append(PhaseGate(lam).control(3), [control, a_reg[n - j], b_reg[n - i], out_reg[k - 1]])
    qc.append(QFT(n, do_swaps=False).inverse(), out_reg)
    return out_reg

def muli_controlled(qc, a_reg, c, control, n_output_bits=None):
    n = len(a_reg)
    if n_output_bits is None:
        n_output_bits = n
    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"prod{idx}" in existing:
        idx += 1
    out_reg = QuantumRegister(n_output_bits, name=f"prod{idx}")
    qc.add_register(out_reg)
    qc.append(QFT(n_output_bits, do_swaps=False), out_reg)
    abs_c = abs(c)
    for j in range(n):
        for k in range(n_output_bits):
            angle = (2 * np.pi * abs_c * (2 ** j)) / (2 ** (k + 1))
            angle = angle % (2 * np.pi)
            if angle != 0:
                qc.append(PhaseGate(angle).control(2), [control, a_reg[j], out_reg[k]])
    qc.append(QFT(n_output_bits, do_swaps=False).inverse(), out_reg)
    if c < 0:
        invert_controlled(qc, out_reg, control)
    return out_reg

def divu_controlled(qc, a_reg, b_reg, control, n_output_bits=None):
    n = len(a_reg)
    assert len(b_reg) == n
    if n_output_bits is None:
        n_output_bits = n

    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while (
        f"quotu{idx}" in existing or f"rem{idx}" in existing or f"sign{idx}" in existing
    ):
        idx += 1

    qout = QuantumRegister(n_output_bits, name=f"quotu{idx}")
    rem = QuantumRegister(n, name=f"rem{idx}")
    sign = QuantumRegister(1, name=f"sign{idx}")
    qc.add_register(qout)
    qc.add_register(rem)
    qc.add_register(sign)

    for i in reversed(range(n_output_bits)):
        for j in reversed(range(1, n)):
            qc.cswap(control, rem[j], rem[j - 1])
        if i < n:
            qc.cswap(control, rem[0], a_reg[i])
        _sub_in_place(qc, rem, b_reg, control=control)
        qc.ccx(control, rem[n - 1], sign[0])
        _controlled_add_in_place(qc, rem, b_reg, sign[0], control=control)
        qc.cx(control, qout[i])
        qc.ccx(control, sign[0], qout[i])
        qc.ccx(control, qout[i], sign[0])
        qc.cx(control, sign[0])

    return qout, rem


def div_controlled(qc, a_reg, b_reg, control, n_output_bits=None):
    n = len(a_reg)
    if n_output_bits is None:
        n_output_bits = n

    sign_a = twos_to_sign_magnitude(qc, a_reg)
    sign_b = twos_to_sign_magnitude(qc, b_reg)

    qout, rem = divu_controlled(qc, a_reg, b_reg, control, n_output_bits=n_output_bits)

    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"signq{idx}" in existing:
        idx += 1

    sign_q = QuantumRegister(1, name=f"signq{idx}")
    qc.add_register(sign_q)

    qc.ccx(control, sign_a[0], sign_q[0])
    qc.ccx(control, sign_b[0], sign_q[0])

    sign_magnitude_to_twos(qc, qout, sign_q, control=control)
    qc.ccx(control, qout[n_output_bits - 1], sign_q[0])
    sign_magnitude_to_twos(qc, rem, sign_a, control=control)
    sign_magnitude_to_twos(qc, a_reg, sign_a, control=control)
    qc.ccx(control, a_reg[n - 1], sign_a[0])
    sign_magnitude_to_twos(qc, b_reg, sign_b, control=control)
    qc.ccx(control, b_reg[n - 1], sign_b[0])

    return qout, rem

def _sub_in_place(qc, a_reg, b_reg, control=None):
    """
    Subtract b_reg from a_reg in-place using inverse QFT adder.
    If control is provided, operation is done only if control == 1.
    """
    n = len(a_reg)
    qc.append(QFT(n, do_swaps=False), a_reg)

    for i in range(n):
        for j in range(n):
            if j <= i:
                angle = -2 * np.pi / (2 ** (i - j + 1))
                if control is None:
                    qc.cp(angle, b_reg[j], a_reg[i])
                else:
                    qc.append(PhaseGate(angle).control(2), [control, b_reg[j], a_reg[i]])

    qc.append(QFT(n, do_swaps=False).inverse(), a_reg)
    return a_reg


def divi_controlled(qc, a_reg, divisor, control, n_output_bits=None):
    if divisor == 0:
        raise ValueError("Division by zero is not allowed.")
    n = len(a_reg)
    if n_output_bits is None:
        n_output_bits = n

    sign_a = twos_to_sign_magnitude(qc, a_reg)

    b_reg = initialize_variable_controlled(qc, abs(divisor), control, "divi")

    qout, rem = divu_controlled(qc, a_reg, b_reg, control, n_output_bits=n_output_bits)

    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"signq{idx}" in existing:
        idx += 1

    sign_q = QuantumRegister(1, name=f"signq{idx}")
    qc.add_register(sign_q)

    if divisor < 0:
        qc.cx(control, sign_q[0])
    qc.ccx(control, sign_a[0], sign_q[0])

    sign_magnitude_to_twos(qc, qout, sign_q, control=control)
    qc.ccx(control, qout[n_output_bits - 1], sign_q[0])
    sign_magnitude_to_twos(qc, rem, sign_a, control=control)
    sign_magnitude_to_twos(qc, a_reg, sign_a, control=control)
    qc.ccx(control, a_reg[n - 1], sign_a[0])

    return qout, rem

