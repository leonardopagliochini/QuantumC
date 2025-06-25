builtin.module {
  func.func @main() -> i32 {
    %0 = arith.constant 2 : i32
    %1 = arith.constant 3 : i32
    %2 = iarith.addi_imm %1, 5 : i32
    %3 = arith.addi %0, %2 : i32
    %4 = iarith.addi_imm %0, 2 : i32
    %5 = arith.muli %3, %4 : i32
    %6 = iarith.addi_imm %5, 4 : i32
    %7 = iarith.subi_imm %6, 1 : i32
    %8 = iarith.muli_imm %7, 2 : i32
    func.return %8 : i32
  }
}