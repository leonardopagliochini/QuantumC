from xdsl.ir import Block, Region, SSAValue
from xdsl.dialects.builtin import i32
from xdsl.dialects.func import FuncOp, ReturnOp
from xdsl.dialects.arith import ConstantOp, AddiOp, SubiOp, MuliOp, DivSIOp, CmpiOp
from dialect_ops import CondBranchOp, BranchOp, AddiImmOp, SubiImmOp, MuliImmOp, DivSImmOp
from c_ast import Expression, IntegerLiteral, DeclRef, BinaryOperator, BinaryOperatorWithImmediate
from c_ast import VarDecl, AssignStmt, ReturnStmt, FunctionDecl, CompoundStmt, IfStmt

class MLIRGenerator:
    def __init__(self) -> None:
        self.symbol_table: dict[str, SSAValue | None] = {}
        self.current_block: Block | None = None
        self.function_region: Region | None = None

    # def process_expression(self, expr: Expression) -> SSAValue:
    #     if isinstance(expr, IntegerLiteral):
    #         op = ConstantOp.from_int_and_width(expr.value, 32)
    #         self.current_block.add_op(op)
    #         return op.results[0]
    #     if isinstance(expr, DeclRef):
    #         if expr.name not in self.symbol_table or self.symbol_table[expr.name] is None:
    #             raise ValueError(f"Use of undeclared or uninitialized variable '{expr.name}'")
    #         return self.symbol_table[expr.name]
    #     if isinstance(expr, (BinaryOperator, BinaryOperatorWithImmediate)):
    #         lhs_val = self.process_expression(expr.lhs)
    #         rhs_val = self.process_expression(expr.rhs)
    #         arith_map = {'+': AddiOp, '-': SubiOp, '*': MuliOp, '/': DivSIOp}
    #         cmp_map = {'==': "eq", '!=': "ne", '<': "slt", '<=': "sle", '>': "sgt", '>=': "sge"}
    #         if expr.opcode in arith_map:
    #             op = arith_map[expr.opcode](lhs_val, rhs_val)
    #             self.current_block.add_op(op)
    #             return op.results[0]
    #         elif expr.opcode in cmp_map:
    #             op = CmpiOp(lhs_val, rhs_val, cmp_map[expr.opcode])
    #             self.current_block.add_op(op)
    #             return op.results[0]
    #         raise ValueError(f"Unsupported operator: {expr.opcode}")
    #     raise TypeError(f"Unsupported expression type: {type(expr)}")
    
    def process_expression(self, expr: Expression) -> SSAValue:
        if isinstance(expr, IntegerLiteral):
            op = ConstantOp.from_int_and_width(expr.value, 32)
            self.current_block.add_op(op)
            return op.results[0]
        
        if isinstance(expr, DeclRef):
            if expr.name not in self.symbol_table or self.symbol_table[expr.name] is None:
                raise ValueError(f"Use of undeclared or uninitialized variable '{expr.name}'")
            return self.symbol_table[expr.name]

        if isinstance(expr, BinaryOperator):
            lhs_val = self.process_expression(expr.lhs)
            rhs_val = self.process_expression(expr.rhs)
            arith_map = {'+': AddiOp, '-': SubiOp, '*': MuliOp, '/': DivSIOp}
            cmp_map = {'==': "eq", '!=': "ne", '<': "slt", '<=': "sle", '>': "sgt", '>=': "sge"}

            if expr.opcode in arith_map:
                op = arith_map[expr.opcode](lhs_val, rhs_val)
                self.current_block.add_op(op)
                return op.results[0]
            elif expr.opcode in cmp_map:
                op = CmpiOp(lhs_val, rhs_val, cmp_map[expr.opcode])
                self.current_block.add_op(op)
                return op.results[0]
            raise ValueError(f"Unsupported binary operator: {expr.opcode}")

        if isinstance(expr, BinaryOperatorWithImmediate):
            lhs_val = self.process_expression(expr.lhs)
            imm_val = expr.rhs.value if isinstance(expr.rhs, IntegerLiteral) else None
            if imm_val is None:
                raise ValueError("Immediate value must be an integer literal")

            arith_map = {
                '+': AddiImmOp,
                '-': SubiImmOp,
                '*': MuliImmOp,
                '/': DivSImmOp,
            }

            cmp_map = {
                '==': "eq",
                '!=': "ne",
                '<': "slt",
                '<=': "sle",
                '>': "sgt",
                '>=': "sge",
            }

            if expr.opcode in arith_map:
                op = arith_map[expr.opcode](lhs_val, imm_val)
                self.current_block.add_op(op)
                return op.results[0]
            
            elif expr.opcode in cmp_map:
                # Simula il confronto con una costante creando prima una costante
                const_op = ConstantOp.from_int_and_width(imm_val, 32)
                self.current_block.add_op(const_op)
                rhs_val = const_op.results[0]
                cmp_op = CmpiOp(lhs_val, rhs_val, cmp_map[expr.opcode])
                self.current_block.add_op(cmp_op)
                return cmp_op.results[0]

        raise ValueError(f"Unsupported immediate binary operator: {expr.opcode}")



    def lower_if(self, stmt: IfStmt, tail: list) -> None:
        cond_val = self.process_expression(stmt.condition)
        then_block = Block()
        else_block = Block()
        self.function_region.add_block(then_block)
        self.function_region.add_block(else_block)

        self.current_block.add_op(CondBranchOp(cond_val, then_block, [], else_block, []))

        original_symtable = dict(self.symbol_table)

        self.symbol_table = dict(original_symtable)
        self.current_block = then_block
        self._lower_block(stmt.then_body.stmts + tail)

        self.symbol_table = dict(original_symtable)
        self.current_block = else_block
        if stmt.else_body:
            self._lower_block(stmt.else_body.stmts + tail)
        else:
            self._lower_block(tail)

    def _lower_block(self, stmts: list) -> None:
        i = 0
        while i < len(stmts):
            stmt = stmts[i]
            if isinstance(stmt, IfStmt):
                self.lower_if(stmt, stmts[i+1:])
                return
            elif isinstance(stmt, VarDecl):
                self.symbol_table[stmt.name] = self.process_expression(stmt.init) if stmt.init else None
            elif isinstance(stmt, AssignStmt):
                self.symbol_table[stmt.name] = self.process_expression(stmt.value)
            elif isinstance(stmt, ReturnStmt):
                ret_val = self.process_expression(stmt.value) if stmt.value else []
                self.current_block.add_op(ReturnOp(ret_val))
                return
            i += 1

    def generate_function(self, func: FunctionDecl) -> FuncOp:
        self.symbol_table.clear()
        entry_block = Block()
        self.function_region = Region()
        self.function_region.add_block(entry_block)
        self.current_block = entry_block
        self._lower_block(func.body.stmts)
        func_type = ([i32] * len(func.params), [i32])
        return FuncOp(func.name, func_type, self.function_region)
