
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.circuit.library.standard_gates import PhaseGate
from qiskit.circuit.library import QFT
from q_arithmetics import *
import numpy as np

NUMBER_OF_BITS = 4

def int_to_twos_complement(value):
    if value < 0:
        value = (1 << NUMBER_OF_BITS) + value
    return [(value >> i) & 1 for i in range(NUMBER_OF_BITS)]

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

def mul_controlled(qc, a_reg, b_reg, control, a_val=None, b_val=None):
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
    if a_val is not None and b_val is not None:
        if (a_val < 0) ^ (b_val < 0):
            invert_controlled(qc, out_reg, control)
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
            qc.swap(rem[j], rem[j - 1])
        if i < n:
            qc.swap(rem[0], a_reg[i])
        _sub_in_place(qc, rem, b_reg)
        qc.cx(rem[n - 1], sign[0])
        _controlled_add_in_place(qc, rem, b_reg, sign[0])
        qc.x(qout[i])
        qc.cx(sign[0], qout[i])
        qc.cx(qout[i], sign[0])
        qc.x(sign[0])
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
    qc.cx(sign_a[0], sign_q[0])
    qc.cx(sign_b[0], sign_q[0])
    sign_magnitude_to_twos(qc, qout, sign_q)
    qc.cx(qout[n_output_bits - 1], sign_q[0])
    sign_magnitude_to_twos(qc, rem, sign_a)
    sign_magnitude_to_twos(qc, a_reg, sign_a)
    qc.cx(a_reg[n - 1], sign_a[0])
    sign_magnitude_to_twos(qc, b_reg, sign_b)
    qc.cx(b_reg[n - 1], sign_b[0])
    return qout, rem

def divi_controlled(qc, a_reg, divisor, control, n_output_bits=None):
    if divisor == 0:
        raise ValueError("Division by zero is not allowed.")
    n = len(a_reg)
    if n_output_bits is None:
        n_output_bits = n
    sign_a = twos_to_sign_magnitude(qc, a_reg)
    qout, rem = divu_controlled(qc, a_reg, initialize_variable(qc, abs(divisor), "div"), control, n_output_bits=n_output_bits)
    existing = {reg.name for reg in qc.qregs}
    idx = 0
    while f"signq{idx}" in existing:
        idx += 1
    sign_q = QuantumRegister(1, name=f"signq{idx}")
    qc.add_register(sign_q)
    if divisor < 0:
        qc.x(sign_q[0])
    qc.cx(sign_a[0], sign_q[0])
    sign_magnitude_to_twos(qc, qout, sign_q)
    qc.cx(qout[n_output_bits - 1], sign_q[0])
    sign_magnitude_to_twos(qc, rem, sign_a)
    sign_magnitude_to_twos(qc, a_reg, sign_a)
    qc.cx(a_reg[n - 1], sign_a[0])
    return qout, rem
