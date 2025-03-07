import json
import sys
from dataclasses import dataclass
import graphviz
from typing import List, Optional, Union, Any, Dict

@dataclass
class ASTNode:
    kind: str
    id: Optional[str] = None
    loc: Optional[Dict] = None
    range: Optional[Dict] = None

@dataclass
class Type(ASTNode):
    qualType: Optional[str] = None

@dataclass
class BuiltinType(Type):
    pass

@dataclass
class TranslationUnitDecl(ASTNode):
    inner: List['Decl'] = None

@dataclass
class TypedefDecl(ASTNode):
    name: str = None
    type: Dict = None
    isImplicit: bool = False
    inner: List[ASTNode] = None

@dataclass
class FunctionDecl(ASTNode):
    name: str = None
    mangledName: str = None
    type: Dict = None
    inner: List['Stmt'] = None

@dataclass
class CompoundStmt(ASTNode):
    inner: List['Stmt'] = None

@dataclass
class DeclStmt(ASTNode):
    inner: List['Decl'] = None

@dataclass
class VarDecl(ASTNode):
    name: str = None
    type: Dict = None
    init: Union[str, ASTNode] = None
    inner: List[ASTNode] = None

@dataclass
class BinaryOperator(ASTNode):
    opcode: str = None
    type: Dict = None
    valueCategory: str = None
    inner: List[ASTNode] = None

@dataclass
class IntegerLiteral(ASTNode):
    value: str = None
    type: Dict = None
    valueCategory: str = None

@dataclass
class ReturnStmt(ASTNode):
    inner: List[ASTNode] = None

def read_json_file(file_path: str) -> str:
    with open(file_path, 'r') as file:
        return file.read()

def from_dict(data: Union[Dict, List]) -> Union[ASTNode, List, Any]:
    """
    Convert JSON (dictionary or list) into the corresponding dataclasses.
    """
    if isinstance(data, list):
        return [from_dict(item) for item in data]
    if not isinstance(data, dict):
        return data

    kind = data.get('kind')
    common = {
        'id': data.get('id'),
        'loc': data.get('loc'),
        'range': data.get('range'),
        'kind': kind
    }

    if kind == 'TranslationUnitDecl':
        return TranslationUnitDecl(
            inner=from_dict(data.get('inner', [])), 
            **common
        )

    elif kind == 'TypedefDecl':
        return TypedefDecl(
            name=data.get('name'),
            type=data.get('type'),
            isImplicit=data.get('isImplicit', False),
            inner=from_dict(data.get('inner', [])),
            **common
        )

    elif kind == 'BuiltinType':
        return BuiltinType(
            qualType=data.get('type', {}).get('qualType'),
            **common
        )

    elif kind == 'FunctionDecl':
        return FunctionDecl(
            name=data.get('name'),
            mangledName=data.get('mangledName'),
            type=data.get('type'),
            inner=from_dict(data.get('inner', [])),
            **common
        )

    elif kind == 'CompoundStmt':
        return CompoundStmt(
            inner=from_dict(data.get('inner', [])), 
            **common
        )

    elif kind == 'DeclStmt':
        return DeclStmt(
            inner=from_dict(data.get('inner', [])), 
            **common
        )

    elif kind == 'VarDecl':
        # 1) Parse the 'inner' array first
        var_inner = from_dict(data.get('inner', []))

        # 2) Check the 'init' field
        var_init_data = data.get('init')

        # If init is a dict, parse it directly
        if isinstance(var_init_data, dict):
            var_init = from_dict(var_init_data)
        else:
            # Otherwise, see if there's a single child that is 
            # likely the real initializer (e.g., a BinaryOperator)
            var_init = None
            if isinstance(var_inner, list) and len(var_inner) == 1:
                possible_init = var_inner[0]
                # If the single child is a typical expr node, use it
                if isinstance(possible_init, (BinaryOperator, IntegerLiteral, 
                                              CompoundStmt, DeclStmt, VarDecl)):
                    var_init = possible_init

        return VarDecl(
            name=data.get('name'),
            type=data.get('type'),
            # Use the discovered initializer if available, else fallback
            init=var_init if var_init is not None else var_init_data,
            inner=var_inner,
            **common
        )

    elif kind == 'BinaryOperator':
        return BinaryOperator(
            opcode=data.get('opcode'),
            type=data.get('type'),
            valueCategory=data.get('valueCategory'),
            inner=from_dict(data.get('inner', [])),
            **common
        )

    elif kind == 'IntegerLiteral':
        return IntegerLiteral(
            value=data.get('value'),
            type=data.get('type'),
            valueCategory=data.get('valueCategory'),
            **common
        )

    elif kind == 'ReturnStmt':
        return ReturnStmt(
            inner=from_dict(data.get('inner', [])), 
            **common
        )

    else:
        # Catch-all for any node kind not specifically handled
        return ASTNode(**common)

def json_to_dataclass(json_content: str) -> TranslationUnitDecl:
    """
    Convert a JSON string to a TranslationUnitDecl dataclass (root AST node).
    """
    data = json.loads(json_content)
    return from_dict(data)

def format_ast(node: Union[ASTNode, List, Any], indent: int = 0) -> List[str]:
    """
    Create a textual tree representation of the AST for debugging/inspection.
    """
    lines = []
    indent_str = ' ' * indent
    
    # If this is a list, recurse on each item
    if isinstance(node, list):
        for item in node:
            lines.extend(format_ast(item, indent))
        return lines
    
    # If it's not an ASTNode, just print the raw data
    if not isinstance(node, ASTNode):
        lines.append(f"{indent_str}{node}")
        return lines

    # Print the node's kind and ID
    lines.append(f"{indent_str}{node.kind} [id={node.id}]")
    
    # ---------- RECURSION CASES BY NODE TYPE ----------
    
    if isinstance(node, TranslationUnitDecl):
        for decl in node.inner or []:
            lines.extend(format_ast(decl, indent + 2))

    elif isinstance(node, FunctionDecl):
        lines.append(f"{indent_str}  Name: {node.name}")
        # Safely extract type info
        if node.type:
            lines.append(f"{indent_str}  Type: {node.type.get('qualType', 'unknown')}")
        for stmt in node.inner or []:
            lines.extend(format_ast(stmt, indent + 2))

    elif isinstance(node, CompoundStmt):
        # <--- ADD THIS BLOCK for CompoundStmt
        for child in node.inner or []:
            lines.extend(format_ast(child, indent + 2))

    elif isinstance(node, DeclStmt):
        # <--- ADD THIS BLOCK for DeclStmt
        for decl in node.inner or []:
            lines.extend(format_ast(decl, indent + 2))

    elif isinstance(node, VarDecl):
        lines.append(f"{indent_str}  Name: {node.name}")
        if node.type:
            lines.append(f"{indent_str}  Type: {node.type.get('qualType', 'unknown')}")
        if node.init:
            lines.append(f"{indent_str}  Init:")
            lines.extend(format_ast(node.init, indent + 4))

    elif isinstance(node, BinaryOperator):
        lines.append(f"{indent_str}  Op: {node.opcode}")
        if node.inner:
            if len(node.inner) > 0:
                lines.append(f"{indent_str}  LHS:")
                lines.extend(format_ast(node.inner[0], indent + 4))
            if len(node.inner) > 1:
                lines.append(f"{indent_str}  RHS:")
                lines.extend(format_ast(node.inner[1], indent + 4))

    elif isinstance(node, IntegerLiteral):
        lines.append(f"{indent_str}  Value: {node.value}")

    elif isinstance(node, ReturnStmt):
        if node.inner:
            lines.append(f"{indent_str}  Return:")
            lines.extend(format_ast(node.inner[0], indent + 4))

    return lines

def ast_to_graphviz(node: ASTNode, graph: graphviz.Digraph, parent_id: str = None, edge_label: str = "") -> None:
    """
    Recursively add AST nodes to Graphviz diagram with enhanced operator visualization
    and handle all statement types (CompoundStmt, DeclStmt, etc.).
    """
    node_id = str(id(node))
    
    # Default label is just the node's kind:
    label = f"{node.kind}"

    # Add more descriptive labels for certain node types
    if isinstance(node, BinaryOperator):
        label = f"Binary Operator\n{node.opcode}"
    elif isinstance(node, IntegerLiteral):
        label = f"Integer Literal\n{node.value}"
    elif isinstance(node, VarDecl):
        label = f"Variable Declaration\n{node.name}"
    elif isinstance(node, CompoundStmt):
        label = f"Compound Statement"
    elif isinstance(node, DeclStmt):
        label = f"Declaration Statement"

    # Optionally add type info if available
    if hasattr(node, 'type') and node.type:
        label += f"\nType: {node.type.get('qualType', 'unknown')}"

    # Create the Graphviz node
    graph.node(node_id, label=label)

    # Link to the parent, if any
    if parent_id:
        graph.edge(parent_id, node_id, label=edge_label)

    # ------------------
    # RECURSION by TYPE
    # ------------------
    if isinstance(node, TranslationUnitDecl) and node.inner:
        for child in node.inner:
            ast_to_graphviz(child, graph, node_id)

    elif isinstance(node, FunctionDecl) and node.inner:
        for child in node.inner:
            ast_to_graphviz(child, graph, node_id)

    elif isinstance(node, CompoundStmt) and node.inner:
        # Recurse into each statement inside the compound
        for child in node.inner:
            ast_to_graphviz(child, graph, node_id)

    elif isinstance(node, DeclStmt) and node.inner:
        # Recurse into each declaration
        for decl in node.inner:
            ast_to_graphviz(decl, graph, node_id)

    elif isinstance(node, VarDecl) and node.init:
        # If the init is a real ASTNode, descend into it
        if isinstance(node.init, ASTNode):
            ast_to_graphviz(node.init, graph, node_id, "init")

    elif isinstance(node, BinaryOperator) and node.inner:
        # Typically 2 children (LHS, RHS)
        if len(node.inner) > 0:
            ast_to_graphviz(node.inner[0], graph, node_id, "LHS")
        if len(node.inner) > 1:
            ast_to_graphviz(node.inner[1], graph, node_id, "RHS")

    elif isinstance(node, ReturnStmt) and node.inner:
        ast_to_graphviz(node.inner[0], graph, node_id, "value")

def save_ast_image(root: ASTNode, output_path: str = "ast") -> None:
    """
    Create and save a Graphviz-based AST visualization (PNG file).
    """
    dot = graphviz.Digraph(comment='AST', format='png')
    dot.attr(rankdir='TB', splines='ortho')  # Layout top to bottom
    dot.attr('node', shape='box', style='rounded,filled', 
             fontname='Helvetica', fillcolor='#E0E0E0')
    dot.attr('edge', arrowsize='0.7', fontname='Helvetica')
    
    ast_to_graphviz(root, dot)
    
    dot.render(output_path, cleanup=True)
    print(f"AST visualization saved to {output_path}.png")

def save_ast_image_from_function(func_node: ASTNode, output_path: str = "ast_func") -> None:
    """
    Create and save a Graphviz-based AST visualization *starting from the function node*.
    """
    dot = graphviz.Digraph(comment='Function AST', format='png')
    dot.attr(rankdir='TB', splines='ortho')  # Layout top to bottom
    dot.attr('node', shape='box', style='rounded,filled', 
             fontname='Helvetica', fillcolor='#E0E0E0')
    dot.attr('edge', arrowsize='0.7', fontname='Helvetica')
    
    # Build the sub-AST graph from just this function node:
    ast_to_graphviz(func_node, dot)
    
    dot.render(output_path, cleanup=True)
    print(f"Function-only AST visualization saved to {output_path}.png")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python ast_parser.py <path_to_json> [output_image]")
        sys.exit(1)

    try:
        json_content = read_json_file(sys.argv[1])
        root = json_to_dataclass(json_content)
        
        print("Text representation:")
        print("\n".join(format_ast(root)))
        
        # 1) Generate the FULL AST image (unchanged, as you had before)
        output_image = sys.argv[2] if len(sys.argv) > 2 else "ast"
        save_ast_image(root, output_image)
        
        # 2) Find the function node you care about (e.g., 'main'):
        main_func = None
        if isinstance(root, TranslationUnitDecl) and root.inner:
            for child in root.inner:
                # If you're specifically looking for the 'main' function:
                if isinstance(child, FunctionDecl) and child.name == "main":
                    main_func = child
                    break
        
        # If found, generate a second image focusing on that function only:
        if main_func is not None:
            save_ast_image_from_function(main_func, "ast_func")
        else:
            print("No function named 'main' found in the AST.")
        
    except FileNotFoundError:
        print(f"Error: File '{sys.argv[1]}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"JSON Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

