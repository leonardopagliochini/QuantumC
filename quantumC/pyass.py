import json

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
            # Prefer: LI + *_I
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
            inst += "I"
            command = f"{inst} {result_reg}, {right_result}, {left_result}"

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

    for item in ast.get('inner', []):
        if item['kind'] == 'FunctionDecl' and item.get('name') == 'main':
            for stmt in item.get('inner', []):
                if stmt['kind'] == 'CompoundStmt':
                    for inner_stmt in stmt.get('inner', []):
                        if inner_stmt['kind'] == 'DeclStmt':
                            var_decl = inner_stmt['inner'][0]
                            var_name = var_decl['name']
                            if 'init' in var_decl:
                                cmds, result_reg, register_counter = generate_commands_from_node(
                                    var_decl['inner'][0], register_counter, variable_env, use_qr, depth=0, debug=debug)
                                commands.extend(cmds)
                                variable_env[var_name] = result_reg

    return commands

def generate_riscv_commands(json_path, debug=False, use_qr=True):
    """Main function: given a JSON file path, print the corresponding RISC-V-like commands."""
    with open(json_path, 'r') as f:
        ast = json.load(f)

    commands = extract_commands_from_ast(ast, debug=debug, use_qr=use_qr)

    for cmd in commands:
        print(cmd)
