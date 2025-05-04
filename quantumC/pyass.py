import json
import os
import re
from collections import defaultdict

# Mapping of C binary operators to your RISC-V-like mnemonics
OPERATOR_MAP = {
    '+': 'ADD',
    '-': 'SUB',
    '*': 'MUL',
    '/': 'DIV',
    '%': 'REM',
    '^': 'XOR',
    '|': 'OR',
    '&': 'AND'
}

def new_virtual_register(index, use_qr):
    """Return a virtual register name based on style."""
    return f"qr{index}" if use_qr else chr(ord('a') + index)

def generate_commands_from_node(node, register_counter, variable_env, use_qr, depth=0, debug=False):
    """Recursively generate commands from an AST node."""
    indent = "  " * depth

    if debug:
        print(f"{indent}Processing {node['kind']}")

    if node['kind'] == 'IntegerLiteral':
        if debug:
            print(f"{indent}  → IntegerLiteral value: {node['value']}")
        return [], str(node['value']), register_counter

    if node['kind'] == 'BinaryOperator':
        opcode = node['opcode']
        if debug:
            print(f"{indent}  → BinaryOperator opcode: {opcode}")

        if opcode not in OPERATOR_MAP:
            raise ValueError(f"Unsupported operation '{opcode}' encountered at depth {depth}")

        left_cmds, left_result, register_counter = generate_commands_from_node(
            node['inner'][0], register_counter, variable_env, use_qr, depth+1, debug)
        right_cmds, right_result, register_counter = generate_commands_from_node(
            node['inner'][1], register_counter, variable_env, use_qr, depth+1, debug)

        result_reg = new_virtual_register(register_counter, use_qr)
        register_counter += 1
        inst = OPERATOR_MAP[opcode]

        is_left_imm = left_result.isdigit()
        is_right_imm = right_result.isdigit()

        if is_left_imm and is_right_imm:
            temp_reg = new_virtual_register(register_counter, use_qr)
            register_counter += 1
            li_cmd = f"LI {temp_reg}, {left_result}"
            inst_i = inst + "I"
            op_cmd = f"{inst_i} {result_reg}, {temp_reg}, {right_result}"
            if debug:
                print(f"{indent}  → Emit: {li_cmd}")
                print(f"{indent}  → Emit: {op_cmd}")
            return left_cmds + right_cmds + [li_cmd, op_cmd], result_reg, register_counter

        elif is_right_imm and not is_left_imm:
            inst += "I"
            command = f"{inst} {result_reg}, {left_result}, {right_result}"

        elif is_left_imm and not is_right_imm:
            # Must use LI + regular op to preserve operand order (imm - reg)
            temp_reg = new_virtual_register(register_counter, use_qr)
            register_counter += 1
            li_cmd = f"LI {temp_reg}, {left_result}"
            command = f"{inst} {result_reg}, {temp_reg}, {right_result}"
            if debug:
                print(f"{indent}  → Emit: {li_cmd}")
                print(f"{indent}  → Emit: {command}")
            return left_cmds + right_cmds + [li_cmd, command], result_reg, register_counter

        else:
            command = f"{inst} {result_reg}, {left_result}, {right_result}"

        if debug:
            print(f"{indent}  → Emit: {command}")

        return left_cmds + right_cmds + [command], result_reg, register_counter

    if node['kind'] == 'ImplicitCastExpr':
        if debug:
            print(f"{indent}  → Unwrapping ImplicitCastExpr")
        return generate_commands_from_node(node['inner'][0], register_counter, variable_env, use_qr, depth, debug)

    if node['kind'] == 'ParenExpr':
        if debug:
            print(f"{indent}  → Unwrapping ParenExpr")
        return generate_commands_from_node(node['inner'][0], register_counter, variable_env, use_qr, depth, debug)

    if node['kind'] == 'DeclRefExpr':
        var_name = node['referencedDecl']['name']
        if var_name not in variable_env:
            raise ValueError(f"Reference to unknown variable '{var_name}'")
        reg = variable_env[var_name]
        if debug:
            print(f"{indent}  → DeclRefExpr refers to register: {reg}")
        return [], reg, register_counter

    raise ValueError(f"Unsupported AST node kind: '{node['kind']}' encountered at depth {depth}")


def extract_commands_from_ast(ast, debug=False, use_qr=True):
    """Extracts and returns the list of commands from the full AST."""
    commands = []
    register_counter = 0
    variable_env = {}

    def process_stmt(node):
        nonlocal register_counter, commands

        if node['kind'] == 'DeclStmt':
            for var_decl in node.get('inner', []):
                var_name = var_decl['name']
                if 'init' in var_decl:
                    cmds, result_reg, register_counter = generate_commands_from_node(
                        var_decl['inner'][0], register_counter, variable_env, use_qr, depth=0, debug=debug)
                    commands.extend(cmds)
                    variable_env[var_name] = result_reg
                else:
                    # Uninitialized variable: reserve it without a register yet
                    variable_env[var_name] = None

        elif node['kind'] == 'BinaryOperator' and node.get('opcode') == '=':
            lhs = node['inner'][0]
            rhs = node['inner'][1]
            if lhs['kind'] == 'DeclRefExpr':
                var_name = lhs['referencedDecl']['name']
                cmds, result_reg, register_counter = generate_commands_from_node(
                    rhs, register_counter, variable_env, use_qr, depth=0, debug=debug)
                commands.extend(cmds)
                variable_env[var_name] = result_reg

        elif 'inner' in node:
            for child in node['inner']:
                process_stmt(child)

    for item in ast.get('inner', []):
        if item['kind'] == 'FunctionDecl' and item.get('name') == 'main':
            for stmt in item.get('inner', []):
                if stmt['kind'] == 'CompoundStmt':
                    for inner_stmt in stmt.get('inner', []):
                        process_stmt(inner_stmt)

    return commands


def generate_riscv_commands(json_path, debug=False, use_qr=True, out_folder="fake_v"):
    """Main function: given a JSON file path, print and save the RISC-V-like commands."""
    with open(json_path, 'r') as f:
        ast = json.load(f)

    commands = extract_commands_from_ast(ast, debug=debug, use_qr=use_qr)

    for cmd in commands:
        print(cmd)

    os.makedirs(out_folder, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(json_path))[0]
    output_path = os.path.join(out_folder, f"irep_{base_name}.txt")

    with open(output_path, 'w') as out_file:
        for cmd in commands:
            out_file.write(cmd + '\n')


def quantumize_irep(base_name: str, folder: str = "fake_v"):
    input_path = os.path.join(folder, f"irep_{base_name}.txt")
    output_path = os.path.join(folder, f"irep_{base_name}_quantum.txt")

    if not os.path.exists(input_path):
        print(f"❌ Error: {input_path} does not exist.")
        return

    with open(input_path, 'r') as f:
        original_lines = [line.strip() for line in f if line.strip()]

    reg_use_counts = defaultdict(int)
    all_regs = set()

    # First pass: count how many times each register is used
    for line in original_lines:
        tokens = re.split(r'[,\s]+', line)
        for tok in tokens[1:]:  # Skip the opcode
            if tok.startswith("qr") and tok[2:].isdigit():
                reg_use_counts[tok] += 1
                all_regs.add(tok)

    quantum_lines = []
    reg_counter = max((int(r[2:]) for r in all_regs), default=-1) + 1

    for line in original_lines:
        tokens = re.split(r'[,\s]+', line)
        instr = tokens[0]
        args = tokens[1:]
        quantum_instrs = []

        if instr == "LI":
            # Format: LI dest, value
            dest, imm = args
            quantum_instrs.append(f"LI {dest}, {imm}")
            reg_use_counts[dest] -= 1

        elif instr.endswith('I'):
            # Format: *_I dest, reg, imm → overwrite reg
            _, reg, imm = args
            quantum_instrs.append(f"{instr} {reg}, {reg}, {imm}")
            reg_use_counts[reg] -= 1

        else:
            # Format: OPCODE dest, left, right
            dest, left, right = args

            # If right is reused later, we must copy it before overwriting
            if reg_use_counts[right] > 1:
                temp_reg = f"qr{reg_counter}"
                reg_counter += 1
                quantum_instrs.append(f"MOV {temp_reg}, {right}")
                right = temp_reg  # Use the copy instead
            quantum_instrs.append(f"{instr} {right}, {left}, {right}")
            reg_use_counts[right] -= 1

        quantum_lines.append((line, quantum_instrs))

    os.makedirs(folder, exist_ok=True)

    with open(output_path, 'w') as out:
        for orig, qlines in quantum_lines:
            print(f"{orig:<40} |  {qlines[0]}")
            out.write(f"{orig:<40} |  {qlines[0]}\n")
            for q in qlines[1:]:
                print(f"{'':<40} |  {q}")
                out.write(f"{'':<40} |  {q}\n")

    print(f"\n✅ Total virtual registers used: {reg_counter}")
    with open(output_path, 'a') as out:
        out.write(f"\nTotal virtual registers used: {reg_counter}\n")
