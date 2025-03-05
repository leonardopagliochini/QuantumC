#!/usr/bin/env python3

import json
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ClangASTNode:
    """
    A generic container for Clang AST JSON nodes.
    We store typical fields like 'id', 'kind', 'name', 'type', etc.
    'extra' catches any additional fields not explicitly handled.
    """
    id: Optional[str] = None
    kind: Optional[str] = None
    name: Optional[str] = None
    mangledName: Optional[str] = None
    opcode: Optional[str] = None
    init: Optional[str] = None
    size: Optional[int] = None
    isImplicit: Optional[bool] = None

    # For loc, range, type, etc., we'll store them as dicts.
    loc: Dict[str, Any] = field(default_factory=dict)
    range: Dict[str, Any] = field(default_factory=dict)
    type: Dict[str, Any] = field(default_factory=dict)

    # 'inner' is a list of child nodes (recursively ClangASTNode).
    inner: List['ClangASTNode'] = field(default_factory=list)

    # 'extra' holds any additional fields we haven't explicitly parsed.
    extra: Dict[str, Any] = field(default_factory=dict)


def parse_clang_ast(node_data: Dict[str, Any]) -> ClangASTNode:
    """
    Recursively parse a dictionary from Clang JSON AST into a ClangASTNode instance.
    """
    # Extract known fields (pop them out of the dict if present)
    node_id = node_data.pop("id", None)
    kind = node_data.pop("kind", None)
    name = node_data.pop("name", None)
    mangled_name = node_data.pop("mangledName", None)
    opcode = node_data.pop("opcode", None)
    init_val = node_data.pop("init", None)
    size_val = node_data.pop("size", None)
    is_implicit = node_data.pop("isImplicit", None)

    loc = node_data.pop("loc", {})
    rng = node_data.pop("range", {})
    node_type = node_data.pop("type", {})

    # Handle child nodes recursively
    inner_list = []
    if "inner" in node_data:
        raw_inner = node_data.pop("inner")
        if isinstance(raw_inner, list):
            for child_data in raw_inner:
                if isinstance(child_data, dict):
                    child_node = parse_clang_ast(child_data)
                    inner_list.append(child_node)
                else:
                    # If it's not a dict, we just ignore or put in 'extra'
                    pass

    # Anything left goes into 'extra'
    extra = node_data

    return ClangASTNode(
        id=node_id,
        kind=kind,
        name=name,
        mangledName=mangled_name,
        opcode=opcode,
        init=init_val,
        size=size_val,
        isImplicit=is_implicit,
        loc=loc,
        range=rng,
        type=node_type,
        inner=inner_list,
        extra=extra
    )


def parse_clang_ast_from_file(json_file_path: str) -> ClangASTNode:
    """
    Load a JSON file and parse its contents as a Clang AST node.
    Assumes the top-level JSON is a dictionary.
    """
    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return parse_clang_ast(data)


def main():
    if len(sys.argv) < 2:
        print("Usage: python clang_ast_parser.py path/to/clang_ast.json")
        sys.exit(1)

    json_file = sys.argv[1]
    root_node = parse_clang_ast_from_file(json_file)
    print("Successfully parsed AST from:", json_file)
    print("\nRoot node (dataclass):")
    print(root_node)

    # Example: you can navigate the AST. For instance:
    # if root_node.inner:
    #     print("\nFirst child's kind:", root_node.inner[0].kind)


if __name__ == "__main__":
    main()
