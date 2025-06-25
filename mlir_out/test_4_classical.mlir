builtin.module {
  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = iarith.addi_imm %0, 4 : i32
    %2 = arith.addi %0, %1 : i32
    %3 = iarith.addi_imm %2, 2 : i32
    %4 = arith.muli %3, %1 : i32
    %5 = iarith.addi_imm %0, 1 : i32
    %6 = arith.muli %4, %5 : i32
    %7 = iarith.addi_imm %6, 3 : i32
    %8 = iarith.addi_imm %3, 1 : i32
    %9 = arith.divsi %7, %8 : i32
    %10 = iarith.addi_imm %9, 10 : i32
    %11 = iarith.subi_imm %10, 5 : i32
    %12 = iarith.muli_imm %11, 2 : i32
    func.return %12 : i32
  }
}