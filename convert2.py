import json
import sys
from dataclasses import dataclass
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
        return TranslationUnitDecl(inner=from_dict(data.get('inner', [])), **common)
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
        return CompoundStmt(inner=from_dict(data.get('inner', [])), **common)
    elif kind == 'DeclStmt':
        return DeclStmt(inner=from_dict(data.get('inner', [])), **common)
    elif kind == 'VarDecl':
        return VarDecl(
            name=data.get('name'),
            type=data.get('type'),
            init=from_dict(data.get('init')) if isinstance(data.get('init'), dict) else data.get('init'),
            inner=from_dict(data.get('inner', [])),
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
        return ReturnStmt(inner=from_dict(data.get('inner', [])), **common)
    else:
        return ASTNode(**common)

def json_to_dataclass(json_content: str) -> TranslationUnitDecl:
    data = json.loads(json_content)
    return from_dict(data)

def format_ast(node: Union[ASTNode, List, Any], indent: int = 0) -> List[str]:
    """Handle both AST nodes and primitive values"""
    lines = []
    indent_str = ' ' * indent
    
    if isinstance(node, list):
        for item in node:
            lines.extend(format_ast(item, indent))
        return lines
    elif not isinstance(node, ASTNode):
        lines.append(f"{indent_str}{node}")
        return lines

    # ASTNode processing
    lines.append(f"{indent_str}{node.kind} [id={node.id}]")
    
    if isinstance(node, TranslationUnitDecl):
        for decl in node.inner or []:
            lines.extend(format_ast(decl, indent + 2))
    elif isinstance(node, FunctionDecl):
        lines.append(f"{indent_str}  Name: {node.name}")
        lines.append(f"{indent_str}  Type: {node.type.get('qualType', 'unknown')}")
        for stmt in node.inner or []:
            lines.extend(format_ast(stmt, indent + 2))
    elif isinstance(node, VarDecl):
        lines.append(f"{indent_str}  Name: {node.name}")
        lines.append(f"{indent_str}  Type: {node.type.get('qualType', 'unknown')}")
        if node.init:
            lines.append(f"{indent_str}  Init:")
            lines.extend(format_ast(node.init, indent + 4))
    elif isinstance(node, BinaryOperator):
        lines.append(f"{indent_str}  Op: {node.opcode}")
        if node.inner:
            lines.append(f"{indent_str}  LHS:")
            lines.extend(format_ast(node.inner[0], indent + 4))
            lines.append(f"{indent_str}  RHS:")
            lines.extend(format_ast(node.inner[1], indent + 4))
    elif isinstance(node, IntegerLiteral):
        lines.append(f"{indent_str}  Value: {node.value}")
    elif isinstance(node, ReturnStmt) and node.inner:
        lines.append(f"{indent_str}  Return:")
        lines.extend(format_ast(node.inner[0], indent + 4))
    
    return lines

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python ast_parser.py <path_to_json>")
        sys.exit(1)

    try:
        json_content = read_json_file(sys.argv[1])
        root = json_to_dataclass(json_content)
        print("\n".join(format_ast(root)))
    except FileNotFoundError:
        print(f"Error: File '{sys.argv[1]}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"JSON Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)