builtin.module {
  func.func @main() -> i32 {
    %0 = arith.constant 2 : i32
    %1 = arith.constant 3 : i32
    %2 = arith.addi %0, %1 : i32
    %3 = arith.muli %2, %1 : i32
    %4 = iarith.addi_imm %3, 1 : i32
    %5 = arith.divsi %4, %0 : i32
    %6 = iarith.muli_imm %5, 2 : i32
    %7 = arith.addi %6, %0 : i32
    %8 = iarith.subi_imm %7, 2 : i32
    %9 = iarith.muli_imm %8, 3 : i32
    %10 = iarith.addi_imm %9, 4 : i32
    func.return %10 : i32
  }
}