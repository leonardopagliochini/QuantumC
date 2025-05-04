import os
import re
import sys
import subprocess
import json

def execute_quantum_instructions(file_path):
    registers = {}
    def get_val(x): return int(x) if x.lstrip('-').isdigit() else registers.get(x, 0)

    with open(file_path, 'r') as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("Total virtual")]

    for line in lines:
        tokens = re.split(r'[,\s]+', line)
        instr, args = tokens[0], tokens[1:]

        if instr == "LI":
            registers[args[0]] = int(args[1])
        elif instr == "MOV":
            registers[args[0]] = get_val(args[1])
        elif instr.startswith("ADD"):
            registers[args[0]] = get_val(args[1]) + get_val(args[2])
        elif instr.startswith("SUB"):
            registers[args[0]] = get_val(args[1]) - get_val(args[2])
        elif instr.startswith("MUL"):
            registers[args[0]] = get_val(args[1]) * get_val(args[2])
        elif instr.startswith("DIV"):
            divisor = get_val(args[2])
            registers[args[0]] = get_val(args[1]) // divisor if divisor != 0 else 0
        elif instr.startswith("REM"):
            divisor = get_val(args[2])
            registers[args[0]] = get_val(args[1]) % divisor if divisor != 0 else 0
        elif instr.startswith("XOR"):
            registers[args[0]] = get_val(args[1]) ^ get_val(args[2])
        elif instr.startswith("OR"):
            registers[args[0]] = get_val(args[1]) | get_val(args[2])
        elif instr.startswith("AND"):
            registers[args[0]] = get_val(args[1]) & get_val(args[2])
        else:
            raise ValueError(f"Unsupported instruction: {instr}")
    return registers


def run_c_code_and_extract_output(c_path):
    exe_path = c_path.replace(".c", "")
    compile_cmd = ["gcc", c_path, "-o", exe_path]
    run_cmd = [f"./{exe_path}"]

    subprocess.run(compile_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = subprocess.run(run_cmd, check=True, capture_output=True, text=True)

    output = result.stdout
    os.remove(exe_path)

    values = {}
    for line in output.strip().splitlines():
        match = re.match(r"(\w+)\s*=\s*(-?\d+)", line.strip())
        if match:
            var, val = match.groups()
            values[var] = int(val)
    return values


def compare_results(virtual_regs, expected_values, varmap):
    print("\n✅ Final virtual register states:")
    for reg in sorted(virtual_regs):
        print(f"{reg}: {virtual_regs[reg]}")

    print("\n🔍 Comparing with C output:")
    mismatches = 0
    for var, expected_val in expected_values.items():
        reg = varmap.get(var, None)
        if not reg:
            print(f"⚠️ Variable {var} not found in varmap!")
            mismatches += 1
            continue
        actual_val = virtual_regs.get(reg, None)
        status = "✅ OK" if actual_val == expected_val else f"❌ MISMATCH (got {actual_val})"
        if actual_val != expected_val:
            mismatches += 1
        print(f"{var} ({reg}) = {expected_val} → {status}")
    if mismatches == 0:
        print("\n🎉 All results match!")
    else:
        print(f"\n⚠️ {mismatches} mismatch(es) found.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_quantum_v.py <base_filename> (no extension)")
        sys.exit(1)

    base = sys.argv[1]
    folder = "fake_v"
    quantum_path = os.path.join(folder, f"irep_{base}_quantum_only.txt")
    c_path = os.path.join("c_code", f"{base}.c")
    varmap_path = os.path.join(folder, f"irep_{base}_varmap.json")

    try:
        with open(varmap_path, 'r') as f:
            varmap = json.load(f)
        quantum_result = execute_quantum_instructions(quantum_path)
        expected = run_c_code_and_extract_output(c_path)
        compare_results(quantum_result, expected, varmap)
    except Exception as e:
        print(f"❌ Error: {e}")