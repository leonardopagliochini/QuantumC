from q_arithmetics import *
import csv

results = []

def binary_repr(value):
    bits = int_to_twos_complement(value)
    return ''.join(str(b) for b in bits[::-1])

def test_initialize_and_measure(value):
    qc = QuantumCircuit()
    reg = initialize_variable(qc, value, "a")
    measure(qc, reg)
    print(f"\nTest: Initialize {value}")
    sim_res = simulate(qc, shots=1)
    result_val = sim_res[reg.name]["value"]
    result_bin = sim_res[reg.name]["binary"]
    if result_val != value:
        print(f"Mismatch: expected {value}, got {result_val}")
    results.append({
        "test": "init",
        "a_dec": value,
        "a_bin": binary_repr(value),
        "b_dec": "",
        "b_bin": "",
        "result_dec": result_val,
        "result_bin": result_bin,
    })


def test_add(a, b):
    set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    b_reg = initialize_variable(qc, b, "b")
    result_reg = add(qc, a_reg, b_reg)
    measure(qc, result_reg)
    print(f"\nTest: {a} + {b}")
    sim_res = simulate(qc, shots=1)
    result_val = sim_res[result_reg.name]["value"]
    result_bin = sim_res[result_reg.name]["binary"]
    expected = (a + b) % (1 << NUMBER_OF_BITS)
    if expected >= 2**(NUMBER_OF_BITS - 1):
        expected -= 1 << NUMBER_OF_BITS
    if result_val != expected:
        print(f"Mismatch: expected {expected}, got {result_val}")
    results.append({
        "test": "add",
        "a_dec": a,
        "a_bin": binary_repr(a),
        "b_dec": b,
        "b_bin": binary_repr(b),
        "result_dec": result_val,
        "result_bin": result_bin,
    })


def test_addi(a, b):
    set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    result_reg = addi(qc, a_reg, b)
    measure(qc, result_reg)
    print(f"\nTest: {a} + {b} (addi)")
    sim_res = simulate(qc, shots=1)
    result_val = sim_res[result_reg.name]["value"]
    result_bin = sim_res[result_reg.name]["binary"]
    expected = (a + b) % (1 << NUMBER_OF_BITS)
    if expected >= 2**(NUMBER_OF_BITS - 1):
        expected -= 1 << NUMBER_OF_BITS
    if result_val != expected:
        print(f"Mismatch: expected {expected}, got {result_val}")
    results.append({
        "test": "addi",
        "a_dec": a,
        "a_bin": binary_repr(a),
        "b_dec": b,
        "b_bin": binary_repr(b),
        "result_dec": result_val,
        "result_bin": result_bin,
    })


def test_sub(a, b):
    set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    b_reg = initialize_variable(qc, b, "b")
    result_reg = sub(qc, a_reg, b_reg)
    measure(qc, result_reg)
    print(f"\nTest: {a} - {b}")
    sim_res = simulate(qc, shots=1)
    result_val = sim_res[result_reg.name]["value"]
    result_bin = sim_res[result_reg.name]["binary"]
    expected = (a - b) % (1 << NUMBER_OF_BITS)
    if expected >= 2**(NUMBER_OF_BITS - 1):
        expected -= 1 << NUMBER_OF_BITS
    if result_val != expected:
        print(f"Mismatch: expected {expected}, got {result_val}")
    results.append({
        "test": "sub",
        "a_dec": a,
        "a_bin": binary_repr(a),
        "b_dec": b,
        "b_bin": binary_repr(b),
        "result_dec": result_val,
        "result_bin": result_bin,
    })


def test_subi(a, b):
    set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    result_reg = subi(qc, a_reg, b)
    measure(qc, result_reg)
    print(f"\nTest: {a} - {b} (subi)")
    sim_res = simulate(qc, shots=1)
    result_val = sim_res[result_reg.name]["value"]
    result_bin = sim_res[result_reg.name]["binary"]
    expected = (a - b) % (1 << NUMBER_OF_BITS)
    if expected >= 2**(NUMBER_OF_BITS - 1):
        expected -= 1 << NUMBER_OF_BITS
    if result_val != expected:
        print(f"Mismatch: expected {expected}, got {result_val}")
    results.append({
        "test": "subi",
        "a_dec": a,
        "a_bin": binary_repr(a),
        "b_dec": b,
        "b_bin": binary_repr(b),
        "result_dec": result_val,
        "result_bin": result_bin,
    })


def test_mul(a, b):
    set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    b_reg = initialize_variable(qc, b, "b")
    result_reg = mul(qc, a_reg, b_reg)
    measure(qc, result_reg)
    print(f"\nTest: {a} * {b}")
    sim_res = simulate(qc, shots=1)
    result_val = sim_res[result_reg.name]["value"]
    result_bin = sim_res[result_reg.name]["binary"]
    expected = (a * b) % (1 << NUMBER_OF_BITS)
    if expected >= 2**(NUMBER_OF_BITS - 1):
        expected -= 1 << NUMBER_OF_BITS
    if result_val != expected:
        print(f"Mismatch: expected {expected}, got {result_val}")
    results.append({
        "test": "mul",
        "a_dec": a,
        "a_bin": binary_repr(a),
        "b_dec": b,
        "b_bin": binary_repr(b),
        "result_dec": result_val,
        "result_bin": result_bin,
    })


def test_muli(a, b):
    set_number_of_bits(4)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    result_reg = muli(qc, a_reg, b)
    measure(qc, result_reg)
    print(f"\nTest: {a} * {b} (muli)")
    sim_res = simulate(qc, shots=1)
    result_val = sim_res[result_reg.name]["value"]
    result_bin = sim_res[result_reg.name]["binary"]
    expected = (a * b) % (1 << NUMBER_OF_BITS)
    if expected >= 2**(NUMBER_OF_BITS - 1):
        expected -= 1 << NUMBER_OF_BITS
    if result_val != expected:
        print(f"Mismatch: expected {expected}, got {result_val}")
    results.append({
        "test": "muli",
        "a_dec": a,
        "a_bin": binary_repr(a),
        "b_dec": b,
        "b_bin": binary_repr(b),
        "result_dec": result_val,
        "result_bin": result_bin,
    })


def test_divi(a, b):
    set_number_of_bits(6)
    qc = QuantumCircuit()
    a_reg = initialize_variable(qc, a, "a")
    result_reg = divi(qc, a_reg, b)
    measure(qc, result_reg)
    print(f"\nTest: {a} / {b} (divi)")
    sim_res = simulate(qc, shots=1)
    result_val = sim_res[result_reg.name]["value"]
    result_bin = sim_res[result_reg.name]["binary"]
    expected = int(a / b)  # truncate towards zero
    if result_val != expected:
        print(f"Mismatch: expected {expected}, got {result_val}")
    results.append({
        "test": "divi",
        "a_dec": a,
        "a_bin": binary_repr(a),
        "b_dec": b,
        "b_bin": binary_repr(b),
        "result_dec": result_val,
        "result_bin": result_bin,
    })


def print_summary():
    if not results:
        return
    headers = ["test", "a_dec", "a_bin", "b_dec", "b_bin", "result_dec", "result_bin"]
    row_fmt = "{:<8} {:>6} {:>8} {:>6} {:>8} {:>10} {:>12}"
    print("\nSummary:")
    print(row_fmt.format("Test", "A(dec)", "A(bin)", "B(dec)", "B(bin)", "Res(dec)", "Res(bin)"))
    for r in results:
        print(row_fmt.format(
            r["test"],
            r.get("a_dec", ""),
            r.get("a_bin", ""),
            r.get("b_dec", ""),
            r.get("b_bin", ""),
            r["result_dec"],
            r["result_bin"],
        ))
    with open("test_results.csv", "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        for r in results:
            writer.writerow(r)


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

    print_summary()
