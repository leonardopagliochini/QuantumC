# MLIR Generator

## Introduction

`mlir_generator.py` converts the abstract syntax tree (AST) of a small subset of C into [MLIR](https://mlir.llvm.org/) using the xDSL Python framework.  The script fits in a larger pipeline that first parses C sources to JSON, lowers them to classical MLIR, and finally translates them to a custom quantum dialect before circuit generation.  The overall flow is summarised in the project README:

```
1. Generate AST  – generate_ast.py uses Clang to convert the C programs in c_code/ into JSON files under json_out/
2. Lower to MLIR – pipeline.py (class QuantumIR) parses the JSON using c_ast.py, lowers it to MLIR via mlir_generator.py and prints the result.
3. Translate to quantum MLIR – the same pipeline instance calls quantum_translate.py to replace arithmetic operations with quantum dialect ones defined in quantum_dialect.py and dialect_ops.py.
4. Build circuits – circuit_pipeline.py extends the previous step by interpreting the quantum MLIR with Qiskit helpers.
```

(The above is extracted from lines 100–112 of `README.md`.)

Within this flow, `mlir_generator.py` is responsible for producing well‑formed MLIR from the dataclass AST representation provided by `c_ast.py`.

## Supported C Subset

The front‑end recognises a minimal imperative language consisting of integer expressions and structured control flow.  The supported constructs include:

- **Integer literals and variable references** (`IntegerLiteral`, `DeclRef`).
- **Binary arithmetic operations** `+`, `-`, `*`, `/` and comparison operators `==`, `!=`, `<`, `<=`, `>`, `>=` (`BinaryOperator`).
- **Binary operations with one immediate operand** (e.g. `a + 3`) via `BinaryOperatorWithImmediate`.
- **Logical conjunction and disjunction** in `if` conditions through `&&` and `||` (rewritten into nested `if`).
- **Variable declarations**, **assignments**, and **returns**.
- **Structured `if`/`else` statements** and **`for` loops** with initialization, condition, increment and body.

All variables and expressions operate on 32‑bit integers; no other data types are currently handled.  Functions take integer parameters and return a single `i32` value.

## Core Data Structures

`MLIRGenerator` maintains three pieces of state while lowering:

1. **`symbol_table`** – maps variable names to the most recent SSA value representing their contents.
2. **`current_block`** – the block into which new operations are emitted.
3. **`function_region`** – the region holding all blocks for the function being generated.

These fields are initialised in the constructor and reset for every function.

```python
11  class MLIRGenerator:
12      def __init__(self) -> None:
13          self.symbol_table: dict[str, SSAValue | None] = {}
14          self.current_block: Block | None = None
15          self.function_region: Region | None = None
```

(Excerpt from `mlir_generator.py` lines 11‑15.)

## Expression Lowering

The method `process_expression` recursively translates AST expressions into SSA values.  Integer constants become `arith.constant` operations.  Variable references look up the corresponding value in the symbol table and raise an error if used before initialisation.  Binary operators are mapped to arithmetic or comparison ops from the standard dialect.

```python
17  def process_expression(self, expr: Expression) -> SSAValue:
18      if isinstance(expr, IntegerLiteral):
19          op = ConstantOp.from_int_and_width(expr.value, 32)
20          self.current_block.add_op(op)
21          return op.results[0]
...
28      if isinstance(expr, BinaryOperator):
29          lhs_val = self.process_expression(expr.lhs)
30          rhs_val = self.process_expression(expr.rhs)
31          arith_map = {'+': AddiOp, '-': SubiOp, '*': MuliOp, '/': DivSIOp}
32          cmp_map = {'==': "eq", '!=': "ne", '<': "slt", '<=': "sle", '>': "sgt", '>=': "sge"}
33
34          if expr.opcode in arith_map:
35              op = arith_map[expr.opcode](lhs_val, rhs_val)
36              self.current_block.add_op(op)
37              return op.results[0]
38          elif expr.opcode in cmp_map:
39              op = CmpiOp(lhs_val, rhs_val, cmp_map[expr.opcode])
40              self.current_block.add_op(op)
41              return op.results[0]
```

(Code from lines 17‑41 of `mlir_generator.py`.)

When one operand is an immediate constant, the generator emits specialised operations from `dialect_ops.py` such as `iarith.addi_imm` or `iarith.muli_imm`.  Immediate values on the left are only allowed for commutative operators:

```python
44  if isinstance(expr, BinaryOperatorWithImmediate):
...
61      # immediate on the left
62      if isinstance(expr.lhs, IntegerLiteral):
63          imm_val = expr.lhs.value
...
66          if expr.opcode in ('+', '*'):  # commutative
67              op = arith_map[expr.opcode](rhs_val, imm_val)
...
73      elif isinstance(expr.rhs, IntegerLiteral):
74          lhs_val = self.process_expression(expr.lhs)
75          imm_val = expr.rhs.value
```

(From `mlir_generator.py` lines 44‑75.)

## Statement Lowering

### `if` Statements

`lower_if` translates conditional branches.  Compound boolean expressions using `&&` or `||` are rewritten into nested `if` constructs so that each branch is guarded by a single comparison.  New basic blocks are created for the `then` and `else` parts and connected via the custom `cf.cond_br` operation defined in `dialect_ops.py`.

```python
96  def lower_if(self, stmt: IfStmt, tail: list) -> None:
97      if isinstance(stmt.condition, BinaryOperator) and stmt.condition.opcode in ("&&", "||"):
...
122      cond_val = self.process_expression(stmt.condition)
123      then_block = Block()
124      else_block = Block()
125      self.function_region.add_block(then_block)
126      self.function_region.add_block(else_block)
128      self.current_block.add_op(CondBranchOp(cond_val, then_block, [], else_block, []))
```

(From lines 96‑128 of `mlir_generator.py`.)

Each branch is lowered with its own symbol-table snapshot so that assignments do not leak across control‑flow edges.

### `for` Loops

`lower_for` implements naïve loop unrolling.  The initializer may be a variable declaration or an assignment.  After evaluating the loop condition, a conditional branch transfers control either to the loop body or to the code following the loop.  The body is emitted repeatedly up to `MAX_UNROLL` iterations (default 10).  After each iteration the increment expression is evaluated and the condition rechecked.

```python
143  def lower_for(self, stmt: ForStmt, tail: list) -> None:
144      if isinstance(stmt.init, VarDecl):
145          self.symbol_table[stmt.init.name] = self.process_expression(stmt.init.init)
146      elif isinstance(stmt.init, AssignStmt):
147          self.symbol_table[stmt.init.name] = self.process_expression(stmt.init.value)
...
159      for _ in range(MAX_UNROLL):
160          self.current_block = then_block
161          self._lower_block(stmt.body.stmts)
...
166          cond_val = self.process_expression(stmt.condition)
167          next_then = Block()
168          next_else = Block()
169          self.function_region.add_block(next_then)
170          self.function_region.add_block(next_else)
171          self.current_block.add_op(CondBranchOp(cond_val, next_then, [], next_else, []))
```

(From lines 143‑171 of `mlir_generator.py`.)

Because loops are unrolled a fixed number of times, only small iteration counts are faithfully represented.  There is no support for dynamic looping beyond the unroll limit.

### Basic Block Processing

The private method `_lower_block` walks a list of statements.  It handles nested control flow by recursively invoking `lower_if` and `lower_for`.  Straightline code consisting of declarations, assignments and returns is emitted directly.

```python
178  def _lower_block(self, stmts: list) -> None:
179      i = 0
180      while i < len(stmts):
181          stmt = stmts[i]
182          if isinstance(stmt, IfStmt):
183              self.lower_if(stmt, stmts[i+1:])
184              return
185          elif isinstance(stmt, ForStmt):
186              self.lower_for(stmt, stmts[i+1:])
187              return
188          elif isinstance(stmt, VarDecl):
189              self.symbol_table[stmt.name] = self.process_expression(stmt.init) if stmt.init else None
190          elif isinstance(stmt, AssignStmt):
191              self.symbol_table[stmt.name] = self.process_expression(stmt.value)
192          elif isinstance(stmt, ReturnStmt):
193              ret_val = self.process_expression(stmt.value) if stmt.value else []
194              self.current_block.add_op(ReturnOp(ret_val))
195              return
196          i += 1
```

(From lines 178‑196 of `mlir_generator.py`.)

## Function Generation

`generate_function` resets the generator state, creates an entry block and invokes `_lower_block` on the function body.  Every function is assigned an MLIR type `(i32, i32, ..., i32) -> (i32)` matching the number of parameters.

```python
198  def generate_function(self, func: FunctionDecl) -> FuncOp:
199      self.symbol_table.clear()
200      entry_block = Block()
201      self.function_region = Region()
202      self.function_region.add_block(entry_block)
203      self.current_block = entry_block
204      self._lower_block(func.body.stmts)
205      func_type = ([i32] * len(func.params), [i32])
206      return FuncOp(func.name, func_type, self.function_region)
```

(Lines 198‑206 of `mlir_generator.py`.)

## Constraints and Limitations

- **Type system** – only 32‑bit integers are supported throughout the pipeline.
- **Variable use** – references to undeclared or uninitialised variables raise an error during lowering.
- **Looping** – `for` loops are unrolled up to `MAX_UNROLL` iterations; remaining iterations are not represented.
- **No function calls or pointers** – the front‑end handles a single function at a time with no call graph.
- **Limited boolean logic** – complex expressions are reduced to comparisons combined with `&&`/`||` in `if` conditions.

## Role in the Compiler

`mlir_generator.py` forms the bridge between the JSON‑derived dataclasses and the MLIR infrastructure used by the rest of the project.  After the generator produces classical MLIR, `quantum_translate.py` converts each arithmetic and branching construct into quantum operations while managing register allocation.  The resulting module can then be interpreted to create a quantum circuit or compared against a purely classical execution for testing purposes.  In this sense, `MLIRGenerator` provides the structural skeleton that the later quantum translation relies on.

## Conclusion

The current implementation demonstrates how a restricted subset of C can be systematically lowered into MLIR using xDSL primitives.  By clearly separating expression handling, control‑flow lowering and function assembly, `mlir_generator.py` offers a straightforward yet extensible foundation for experimenting with quantum‑oriented IR transformations.