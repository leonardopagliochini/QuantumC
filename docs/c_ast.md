# `c_ast.py` -- Detailed Overview

This document provides an in-depth description of the `c_ast.py` module and its
role within the **QuantumC** compilation pipeline.  The explanations are based
on the repository documentation and the implementation found in the source
files.

## 1. Context and Purpose

`c_ast.py` defines a lightweight Abstract Syntax Tree (AST) for a restricted
subset of the C language.  The rest of the project converts this AST first into
standard MLIR and then into a custom quantum dialect.  The overall workflow is
summarized in the repository [README](../README.md):

1. C sources are dumped to JSON via `clang -ast-dump=json`.
2. `pipeline.py` invokes `parse_ast` from `c_ast.py` to build the dataclass AST.
3. `mlir_generator.py` lowers this AST to classical MLIR.
4. `quantum_translate.py` converts the MLIR into quantum operations.

Consequently, `c_ast.py` forms the **front-end** of the pipeline, isolating the
parsing logic from later compiler stages.

## 2. AST Node Classes

The module represents C constructs using `dataclasses`.  Expressions inherit
from the abstract base class `Expression` and include:

- **`IntegerLiteral`** – integer constants.
- **`DeclRef`** – references to previously declared variables.
- **`BinaryOperator`** – binary operations where both operands are expressions.
- **`BinaryOperatorWithImmediate`** – binary operations with exactly one
  immediate operand.  This distinction allows later passes to generate special
  MLIR instructions with an immediate value.
- **`UnaryOperator`** – unary operations such as negation or logical NOT.

Statements and structural nodes are represented by:

- **`VarDecl`** – variable declarations, optionally with an initializer.
- **`AssignStmt`** – assignments to a variable.
- **`ReturnStmt`** – return from a function.
- **`IfStmt`** – conditional execution with optional `else`.
- **`ForStmt`** – `for` loops with explicit initialization, condition and
  increment statements.
- **`CompoundStmt`** – a sequence of statements.
- **`FunctionDecl`** – a function body and parameter list.
- **`TranslationUnit`** – the top-level container for all functions.

These structures faithfully match the subset of C handled by the rest of the
compiler.

## 3. Supported C Subset

The parser recognizes the following features:

- **Integer variables only** – all types are implicitly `int`.
- **Arithmetic operations** – addition, subtraction, multiplication and signed
  division (`+`, `-`, `*`, `/`).
- **Comparisons** – equality and relational operators (`==`, `!=`, `<`, `<=`,
  `>`, `>=`).
 - **Unary operators** – unary plus, negation (`-`), logical NOT (`!`), bitwise NOT (`~`), and pre/post increment/decrement.
- **Assignments** and **variable declarations** with optional initializers.
- **`if` statements** including chained `else if` and `else` branches.
- **`for` loops** with explicit initialization, condition and increment.
- **`return` statements**.
- **Parenthesised expressions** and implicit casts emitted by Clang are
  transparently handled during parsing.

Pointers, arrays, floating point types, function calls, and other advanced C
features are **not** supported.  Only the listed constructs appear in the test
programs under `c_code/`.

## 4. Parsing the JSON AST

`parse_ast(ast_json)` builds a `TranslationUnit` from the JSON emitted by
Clang.  It iterates over top-level declarations, searches for each function's
`CompoundStmt` body and delegates to `parse_statement` for every contained
statement.  Expression nodes are processed by `parse_expression`.

### 4.1 Expression Parsing

`parse_expression` dispatches on the `"kind"` field of a JSON node.  It ignores
`ImplicitCastExpr` and `ParenExpr` wrappers before handling the actual
construct.  For example:

- `IntegerLiteral` nodes become `IntegerLiteral(value)`.
- `DeclRefExpr` nodes resolve the referenced variable name to create
  `DeclRef(name)`.
- `BinaryOperator` nodes recursively parse both operands.  When exactly one
  operand is an `IntegerLiteral`, the function emits a
  `BinaryOperatorWithImmediate` instead of the generic form.  This design is
  important for later stages that generate special immediate instructions.
- `UnaryOperator` nodes store the opcode and operand.

Any unsupported node results in a `ValueError`, making the accepted grammar
explicit.

### 4.2 Statement Parsing

`parse_statement` recognises declarations, assignments, `return`, `if` and `for`
statements.  Conditional statements are parsed recursively so that `else if`
forms create nested `IfStmt` instances.  The `ForStmt` parser filters out
extraneous JSON nodes, converts the initializer (either `VarDecl` or
`AssignStmt`), and builds the loop body as a `CompoundStmt`.

## 5. Pretty Printing

Besides parsing, the module can reconstruct a C-like source listing.  Functions
`pretty_print_expression`, `pretty_print_statement` and
`pretty_print_translation_unit` walk the dataclasses and emit formatted text.
This capability is primarily used for debugging and validation of the parser.

## 6. Integration with the Pipeline

Once `parse_ast` produces a `TranslationUnit`, `pipeline.py` passes it to
`mlir_generator.py`.  The generator traverses the dataclasses to emit classical
MLIR operations.  For example, `BinaryOperatorWithImmediate` leads to the custom
`iarith.*_imm` ops defined in `dialect_ops.py`.  `quantum_translate.py` then
consumes this MLIR to build quantum circuits.  Thus `c_ast.py` supplies the
structural information on which all later transformations rely.

## 7. Constraints and Design Choices

- **Single integer type** – simplifying the type system keeps the parser
  lightweight and avoids dealing with casts.
- **No pointer aliasing or side effects** – enables straightforward lowering to
  SSA form.
- **Immediate detection** – separating `BinaryOperatorWithImmediate` allows the
  MLIR generator to directly emit operations with constant operands, reducing the
  need for temporary SSA values.
- **Loop unrolling** – `mlir_generator.py` limits automatic unrolling to
  `MAX_UNROLL = 10` iterations (see `mlir_generator.py`).  The AST itself does
  not encode unrolling; it merely preserves the loop structure.
- **Error checking** – the parser raises descriptive exceptions when encountering
  unsupported constructs, making limitations explicit.

## 8. Conclusion

`c_ast.py` encapsulates the front-end of the **QuantumC** prototype.  By mapping
Clang's verbose JSON into concise dataclasses, it enables the subsequent
translation to MLIR and ultimately to a quantum circuit representation.  The
module supports a pragmatic subset of C focused on integer arithmetic and simple
control flow, sufficient for experimenting with quantum-friendly compilation
strategies while keeping the overall system manageable.