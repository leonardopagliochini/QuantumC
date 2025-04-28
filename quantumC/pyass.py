
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

def new_virtual_register(index):
    """Return a new virtual register name based on an index."""
    return chr(ord('a') + index)

def generate_commands_from_node(node, register_counter, variable_env, depth=0, debug=False):
    """Recursively generate commands from an AST node."""
    indent = "  " * depth  # two spaces per level for pretty debug print

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

        # Recurse on operands
        left_cmds, left_result, register_counter = generate_commands_from_node(
            node['inner'][0], register_counter, variable_env, depth=depth+1, debug=debug)
        right_cmds, right_result, register_counter = generate_commands_from_node(
            node['inner'][1], register_counter, variable_env, depth=depth+1, debug=debug)

        # Assign a new virtual register
        result_reg = new_virtual_register(register_counter)
        register_counter += 1

        inst = OPERATOR_MAP[opcode]
        command = f"{inst} {result_reg}, {left_result}, {right_result}"

        if debug:
            print(f"{indent}  → Emit: {command}")

        return left_cmds + right_cmds + [command], result_reg, register_counter

    if node['kind'] == 'ImplicitCastExpr':
        if debug:
            print(f"{indent}  → Unwrapping ImplicitCastExpr")
        return generate_commands_from_node(node['inner'][0], register_counter, variable_env, depth=depth, debug=debug)

    if node['kind'] == 'ParenExpr':
        if debug:
            print(f"{indent}  → Unwrapping ParenExpr")
        return generate_commands_from_node(node['inner'][0], register_counter, variable_env, depth=depth, debug=debug)

    if node['kind'] == 'DeclRefExpr':
        var_name = node['referencedDecl']['name']
        if var_name not in variable_env:
            raise ValueError(f"Reference to unknown variable '{var_name}'")
        reg = variable_env[var_name]
        if debug:
            print(f"{indent}  → DeclRefExpr refers to register: {reg}")
        return [], reg, register_counter

    raise ValueError(f"Unsupported AST node kind: '{node['kind']}' encountered at depth {depth}")

def extract_commands_from_ast(ast, debug=False):
    """Extracts and returns the list of commands from the full AST."""
    commands = []
    register_counter = 0
    variable_env = {}  # maps variable name → register

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
                                    var_decl['inner'][0], register_counter, variable_env, depth=0, debug=debug)
                                commands.extend(cmds)
                                variable_env[var_name] = result_reg  # Map var name → register

    return commands
