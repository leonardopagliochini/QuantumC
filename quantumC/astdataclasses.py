import os
import json
from dataclasses import dataclass, fields
from typing import List, Optional, Union, Any, Dict
from IPython.display import Image, display


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

@dataclass
class DeclRefExpr(ASTNode):
    # "referencedDecl" often has { "id", "kind", "name", ... }
    name: str = None
    type: Dict = None
    valueCategory: str = None
    referencedDecl: Dict = None

@dataclass
class ImplicitCastExpr(ASTNode):
    type: Dict = None
    castKind: str = None
    valueCategory: str = None
    inner: List[ASTNode] = None




class ASTProcessor:
    json_path: str  # Type hint for json_path
    basename: str  # Type hint for basename
    img_out_dir: str  # Type hint for img_out_dir
    txt_out_dir: str  # Type hint for txt_out_dir
    root: 'TranslationUnitDecl'  # Type hint for root

    

    # --------------------
    # INITIALIZATION
    # --------------------

    def __init__(self, json_path: str):
        """
        Initialize the ASTProcessor class.

        Args:
            json_path (str): Path to the JSON file containing the AST.
        """
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"JSON file not found: {json_path}")

        self.json_path = json_path
        self.basename = os.path.splitext(os.path.basename(json_path))[0]  # Store the basename as an attribute

        # Ensure the output directory exists
        self.output_dir = "output"
        self.img_out_dir = os.path.join(self.output_dir, "img_out")
        self.txt_out_dir = os.path.join(self.output_dir, "txt_out")

        os.makedirs(self.img_out_dir, exist_ok=True)
        os.makedirs(self.txt_out_dir, exist_ok=True)

        # Read and parse JSON
        json_content = self.read_json_file(json_path)
        self.root = self.json_to_dataclass(json_content)

        print(f"ASTProcessor initialized for {self.basename}")

    def read_json_file(self, file_path: str) -> str:
        """Reads the content of a JSON file."""
        with open(file_path, 'r') as file:
            return file.read()

    def from_dict(self, data: Union[Dict, List]) -> Union['ASTNode', List, Any]:
        """
        Convert JSON (dictionary or list) into the corresponding dataclasses.
        """
        if isinstance(data, list):
            return [self.from_dict(item) for item in data]
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
                inner=self.from_dict(data.get('inner', [])), 
                **common
            )
        elif kind == 'TypedefDecl':
            return TypedefDecl(
                name=data.get('name'),
                type=data.get('type'),
                isImplicit=data.get('isImplicit', False),
                inner=self.from_dict(data.get('inner', [])),
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
                inner=self.from_dict(data.get('inner', [])),
                **common
            )
        elif kind == 'CompoundStmt':
            return CompoundStmt(
                inner=self.from_dict(data.get('inner', [])), 
                **common
            )
        elif kind == 'DeclStmt':
            return DeclStmt(
                inner=self.from_dict(data.get('inner', [])), 
                **common
            )
        elif kind == 'VarDecl':
            # Parse 'inner' array first
            var_inner = self.from_dict(data.get('inner', []))
            # Check the 'init' field
            var_init_data = data.get('init')
            if isinstance(var_init_data, dict):
                var_init = self.from_dict(var_init_data)
            else:
                var_init = None
                if isinstance(var_inner, list) and len(var_inner) == 1:
                    possible_init = var_inner[0]
                    if isinstance(possible_init, (BinaryOperator, IntegerLiteral, CompoundStmt, DeclStmt, VarDecl)):
                        var_init = possible_init

            return VarDecl(
                name=data.get('name'),
                type=data.get('type'),
                init=var_init if var_init is not None else var_init_data,
                inner=var_inner,
                **common
            )
        elif kind == 'BinaryOperator':
            return BinaryOperator(
                opcode=data.get('opcode'),
                type=data.get('type'),
                valueCategory=data.get('valueCategory'),
                inner=self.from_dict(data.get('inner', [])),
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
                inner=self.from_dict(data.get('inner', [])), 
                **common
            )
        elif kind == 'DeclRefExpr':
            return DeclRefExpr(
                name=data.get('name'),
                type=data.get('type'),
                valueCategory=data.get('valueCategory'),
                referencedDecl=data.get('referencedDecl'),
                **common
            )

        elif kind == 'ImplicitCastExpr':
            return ImplicitCastExpr(
                type=data.get('type'),
                castKind=data.get('castKind'),
                valueCategory=data.get('valueCategory'),
                inner=self.from_dict(data.get('inner', [])),
                **common
            )

        else:
            # Catch-all
            return ASTNode(**common)

    def json_to_dataclass(self, json_content: str) -> 'TranslationUnitDecl':
        """Converts the JSON content to a dataclass."""
        data = json.loads(json_content)
        return self.from_dict(data)


    # --------------------
    # TEXTUAL REPRESENTATION (DEBUGGING)
    # --------------------

    def format_ast(self, node: Union['ASTNode', List, Any], indent: int = 0) -> List[str]:
        """
        Create a textual tree representation of the AST for debugging/inspection.
        """
        lines = []
        indent_str = ' ' * indent
        
        # If this is a list, recurse on each item
        if isinstance(node, list):
            for item in node:
                lines.extend(self.format_ast(item, indent))
            return lines
        
        # If it's not an ASTNode, just print the raw data
        if not isinstance(node, ASTNode):
            lines.append(f"{indent_str}{node}")
            return lines

        # Print the node's kind and ID
        lines.append(f"{indent_str}{node.kind} [id={node.id}]")
        
        if isinstance(node, TranslationUnitDecl):
            for decl in node.inner or []:
                lines.extend(self.format_ast(decl, indent + 2))
        elif isinstance(node, FunctionDecl):
            lines.append(f"{indent_str}  Name: {node.name}")
            if node.type:
                lines.append(f"{indent_str}  Type: {node.type.get('qualType', 'unknown')}")
            for stmt in node.inner or []:
                lines.extend(self.format_ast(stmt, indent + 2))
        elif isinstance(node, CompoundStmt):
            for child in node.inner or []:
                lines.extend(self.format_ast(child, indent + 2))
        elif isinstance(node, DeclStmt):
            for decl in node.inner or []:
                lines.extend(self.format_ast(decl, indent + 2))
        elif isinstance(node, VarDecl):
            lines.append(f"{indent_str}  Name: {node.name}")
            if node.type:
                lines.append(f"{indent_str}  Type: {node.type.get('qualType', 'unknown')}")
            if node.init:
                lines.append(f"{indent_str}  Init:")
                lines.extend(self.format_ast(node.init, indent + 4))
        elif isinstance(node, BinaryOperator):
            lines.append(f"{indent_str}  Op: {node.opcode}")
            if node.inner:
                if len(node.inner) > 0:
                    lines.append(f"{indent_str}  LHS:")
                    lines.extend(self.format_ast(node.inner[0], indent + 4))
                if len(node.inner) > 1:
                    lines.append(f"{indent_str}  RHS:")
                    lines.extend(self.format_ast(node.inner[1], indent + 4))
        elif isinstance(node, IntegerLiteral):
            lines.append(f"{indent_str}  Value: {node.value}")
        elif isinstance(node, ReturnStmt):
            if node.inner:
                lines.append(f"{indent_str}  Return:")
                lines.extend(self.format_ast(node.inner[0], indent + 4))
        elif isinstance(node, DeclRefExpr):
            lines.append(f"{indent_str}  Name: {node.name}")
            if node.type:
                lines.append(f"{indent_str}  Type: {node.type.get('qualType', 'unknown')}")
            # If you want to show which VarDecl it references:
            if node.referencedDecl:
                lines.append(f"{indent_str}  references: {node.referencedDecl.get('name')} (id={node.referencedDecl.get('id')})")

        elif isinstance(node, ImplicitCastExpr):
            if node.type:
                lines.append(f"{indent_str}  Type: {node.type.get('qualType', 'unknown')}")
            if node.castKind:
                lines.append(f"{indent_str}  CastKind: {node.castKind}")
            # Recurse on inner
            for child in node.inner or []:
                lines.extend(self.format_ast(child, indent + 2))

        return lines


    # --------------------
    # AST TO GRAPHVIZ
    # --------------------

    # def ast_to_graphviz(self, node: ASTNode, graph: graphviz.Digraph, parent_id: str = None, edge_label: str = "") -> None:
    #     """
    #     Recursively add AST nodes to Graphviz diagram with enhanced operator visualization
    #     and handle all statement types (CompoundStmt, DeclStmt, etc.).
    #     """
    #     node_id = str(id(node))
        
    #     # Default label is just the node's kind:
    #     label = f"{node.kind}"

    #     # Add more descriptive labels for certain node types
    #     if isinstance(node, BinaryOperator):
    #         label = f"Binary Operator\n{node.opcode}"
    #     elif isinstance(node, IntegerLiteral):
    #         label = f"Integer Literal\n{node.value}"
    #     elif isinstance(node, VarDecl):
    #         label = f"Variable Declaration\n{node.name}"
    #     elif isinstance(node, CompoundStmt):
    #         label = f"Compound Statement"
    #     elif isinstance(node, DeclStmt):
    #         label = f"Declaration Statement"

    #     # Optionally add type info if available
    #     if hasattr(node, 'type') and node.type:
    #         qual = node.type.get('qualType', 'unknown')
    #         label += f"\nType: {qual}"

    #     # Create the Graphviz node
    #     graph.node(node_id, label=label)

    #     # Link to the parent, if any
    #     if parent_id:
    #         graph.edge(parent_id, node_id, label=edge_label)

    #     # ------------------
    #     # RECURSE
    #     # ------------------
    #     if isinstance(node, TranslationUnitDecl) and node.inner:
    #         for child in node.inner:
    #             self.ast_to_graphviz(child, graph, node_id)

    #     elif isinstance(node, FunctionDecl) and node.inner:
    #         for child in node.inner:
    #             self.ast_to_graphviz(child, graph, node_id)

    #     elif isinstance(node, CompoundStmt) and node.inner:
    #         for child in node.inner:
    #             self.ast_to_graphviz(child, graph, node_id)

    #     elif isinstance(node, DeclStmt) and node.inner:
    #         for decl in node.inner:
    #             self.ast_to_graphviz(decl, graph, node_id)

    #     elif isinstance(node, VarDecl) and node.init:
    #         if isinstance(node.init, ASTNode):
    #             self.ast_to_graphviz(node.init, graph, node_id, "init")

    #     elif isinstance(node, BinaryOperator) and node.inner:
    #         if len(node.inner) > 0:
    #             self.ast_to_graphviz(node.inner[0], graph, node_id, "LHS")
    #         if len(node.inner) > 1:
    #             self.ast_to_graphviz(node.inner[1], graph, node_id, "RHS")

    #     elif isinstance(node, ReturnStmt) and node.inner:
    #         self.ast_to_graphviz(node.inner[0], graph, node_id, "value")
    #     elif isinstance(node, DeclRefExpr):
    #         label = f"DeclRefExpr\n{node.name}"
    #         if hasattr(node, 'type') and node.type:
    #             label += f"\nType: {node.type.get('qualType', 'unknown')}"
    #         if node.referencedDecl:
    #             label += f"\nref -> {node.referencedDecl.get('name','?')}"
    #         graph.node(node_id, label=label)
    #         # Link to parent if needed
    #         if parent_id:
    #             graph.edge(parent_id, node_id, edge_label)

    #     elif isinstance(node, ImplicitCastExpr):
    #         label = f"ImplicitCastExpr"
    #         if node.castKind:
    #             label += f"\n({node.castKind})"
    #         if hasattr(node, 'type') and node.type:
    #             label += f"\nType: {node.type.get('qualType','unknown')}"
    #         graph.node(node_id, label=label)
    #         if parent_id:
    #             graph.edge(parent_id, node_id, edge_label)

    #         # Recurse
    #         for child in node.inner or []:
    #             self.ast_to_graphviz(child, graph, node_id)


    # # --------------------
    # # DISPLAY IMG
    # # --------------------

    # def show_ast_image(self, root: ASTNode) -> Image:
    #     """
    #     Return an inline image (IPython.display.Image) for the *entire* AST.
    #     """
    #     dot = graphviz.Digraph(comment='AST')
    #     dot.attr(rankdir='TB', splines='ortho')
    #     dot.attr('node', shape='box', style='rounded,filled', 
    #              fontname='Helvetica', fillcolor='#E0E0E0')
    #     dot.attr('edge', arrowsize='0.7', fontname='Helvetica')
        
    #     # Generate the AST Graphviz representation
    #     self.ast_to_graphviz(root, dot)
        
    #     # Return the inline image
    #     png_data = dot.pipe(format='png')
    #     return Image(png_data)

    # def show_ast_image_from_function(self, func_node: ASTNode) -> Image:
    #     """
    #     Return an inline image (IPython.display.Image) for a *single function* subtree.
    #     """
    #     dot = graphviz.Digraph(comment='Function AST')
    #     dot.attr(rankdir='TB', splines='ortho')
    #     dot.attr('node', shape='box', style='rounded,filled', 
    #              fontname='Helvetica', fillcolor='#E0E0E0')
    #     dot.attr('edge', arrowsize='0.7', fontname='Helvetica')
        
    #     # Generate the AST Graphviz representation for the function subtree
    #     self.ast_to_graphviz(func_node, dot)
        
    #     # Return the inline image
    #     png_data = dot.pipe(format='png')
    #     return Image(png_data)



    # # --------------------
    # # SAVE IMG
    # # --------------------

    # def save_ast_image(self, root: ASTNode, output_path: str = None) -> None:
    #     """
    #     Create and save a Graphviz-based AST visualization (PNG file).
    #     If no output_path is provided, it saves as {basename}_ast_img.png in 'output/img_out/' directory.
    #     """
    #     # Ensure img_out directory exists inside the output directory
    #     output_dir = os.path.join("output", "img_out")
    #     if not os.path.exists(output_dir):
    #         os.makedirs(output_dir)

    #     # Use basename from JSON filename if no output_path is provided
    #     if not output_path:
    #         output_path = os.path.join(output_dir, f"{self.basename}_ast_img")

    #     dot = graphviz.Digraph(comment='AST', format='png')
    #     dot.attr(rankdir='TB', splines='ortho')
    #     dot.attr('node', shape='box', style='rounded,filled', 
    #             fontname='Helvetica', fillcolor='#E0E0E0')
    #     dot.attr('edge', arrowsize='0.7', fontname='Helvetica')

    #     # Generate the AST Graphviz representation
    #     self.ast_to_graphviz(root, dot)
        
    #     # Render and save the image
    #     dot.render(output_path, cleanup=True)
    #     print(f"AST visualization saved to {output_path}.png")


    # def save_ast_image_from_function(self, func_node: ASTNode, output_path: str = None) -> None:
    #     """
    #     Create and save a Graphviz-based AST visualization *starting from the function node*.
    #     If no output_path is provided, it saves as {basename}_ast_img_from_function.png in 'output/img_out/' directory.
    #     """
    #     # Ensure img_out directory exists inside the output directory
    #     output_dir = os.path.join("output", "img_out")
    #     if not os.path.exists(output_dir):
    #         os.makedirs(output_dir)

    #     # Use basename from JSON filename if no output_path is provided
    #     if not output_path:
    #         output_path = os.path.join(output_dir, f"{self.basename}_ast_img_from_function")

    #     dot = graphviz.Digraph(comment='Function AST', format='png')
    #     dot.attr(rankdir='TB', splines='ortho')
    #     dot.attr('node', shape='box', style='rounded,filled', 
    #             fontname='Helvetica', fillcolor='#E0E0E0')
    #     dot.attr('edge', arrowsize='0.7', fontname='Helvetica')

    #     # Generate the AST Graphviz representation starting from the function node
    #     self.ast_to_graphviz(func_node, dot)

    #     # Render and save the image
    #     dot.render(output_path, cleanup=True)
    #     print(f"Function-only AST visualization saved to {output_path}.png")


    # --------------------
    # SAVE TXT INSTANCES
    # --------------------

    def write_ast_instances_txt(self, root: ASTNode, file_path: str = None):
        """
        Recursively traverse the AST, writing each node's kind, ID, and attributes
        (including any children) to a .txt file. This captures the *actual parsed*
        instances, not just the dataclass definitions.
        """
        # Ensure txt_out directory exists inside the output directory
        output_dir = os.path.join("output", "txt_out")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Use basename from JSON filename if no file_path is provided
        if not file_path:
            file_path = os.path.join(output_dir, f"{self.basename}_ast_instances.txt")

        visited = set()

        def dump_node(node: ASTNode, depth: int = 0):
            if not node:
                return

            # Use id(node) for visited-check, so no "unhashable type" error
            if id(node) in visited:
                return
            visited.add(id(node))

            indent = "  " * depth

            # Append info to the file
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"{indent}Node kind: {node.kind}\n")
                f.write(f"{indent}  id: {node.id}\n")
                for field in fields(node):
                    field_name = field.name
                    value = getattr(node, field_name)

                    # If it's another ASTNode, just indicate its kind & ID
                    if isinstance(value, ASTNode):
                        f.write(f"{indent}  {field_name}: [ASTNode: {value.kind}, id={value.id}]\n")
                    else:
                        # Could be a dict, list, string, or None
                        f.write(f"{indent}  {field_name}: {value}\n")
                f.write("\n")

            # Now recurse into any child fields that might hold ASTNodes
            for field in fields(node):
                val = getattr(node, field.name)
                if isinstance(val, ASTNode):
                    dump_node(val, depth + 1)
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, ASTNode):
                            dump_node(item, depth + 1)

        # Overwrite/clear file initially
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("=== AST Instances Dump ===\n\n")

        # Start recursion from the root
        dump_node(root, 0)

        print(f"AST instances have been written to '{file_path}'")
