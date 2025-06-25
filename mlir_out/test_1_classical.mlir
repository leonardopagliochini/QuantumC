builtin.module {
  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.constant 2 : i32
    %2 = iarith.muli_imm %1, 2 : i32
    %3 = iarith.addi_imm %2, 1 : i32
    %4 = arith.addi %0, %3 : i32
    %5 = iarith.subi_imm %4, 3 : i32
    %6 = iarith.addi_imm %5, 3 : i32
    %7 = iarith.muli_imm %6, 2 : i32
    %8 = iarith.subi_imm %7, 5 : i32
    func.return %8 : i32
  }
}