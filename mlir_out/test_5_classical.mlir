builtin.module {
  func.func @main() -> i32 {
    %0 = arith.constant 3 : i32
    %1 = arith.constant 2 : i32
    %2 = arith.addi %0, %1 : i32
    %3 = iarith.addi_imm %2, 5 : i32
    %4 = iarith.subi_imm %3, 1 : i32
    %5 = arith.divsi %4, %2 : i32
    %6 = arith.addi %2, %4 : i32
    %7 = arith.addi %6, %5 : i32
    %8 = iarith.muli_imm %7, 2 : i32
    %9 = iarith.addi_imm %8, 3 : i32
    %10 = arith.muli %9, %4 : i32
    %11 = arith.addi %5, %2 : i32
    %12 = arith.muli %10, %11 : i32
    %13 = arith.divsi %12, %9 : i32
    %14 = arith.addi %13, %2 : i32
    %15 = iarith.subi_imm %14, 2 : i32
    %16 = iarith.muli_imm %15, 4 : i32
    %17 = iarith.addi_imm %16, 8 : i32
    func.return %17 : i32
  }
}