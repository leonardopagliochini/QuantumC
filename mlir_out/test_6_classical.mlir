builtin.module {
  func.func @main() -> i32 {
    %0 = arith.constant 4 : i32
    %1 = iarith.addi_imm %0, 3 : i32
    %2 = iarith.addi_imm %1, 7 : i32
    %3 = arith.muli %0, %1 : i32
    %4 = iarith.addi_imm %3, 2 : i32
    %5 = arith.addi %2, %4 : i32
    %6 = arith.muli %5, %1 : i32
    %7 = iarith.addi_imm %0, 1 : i32
    %8 = arith.divsi %6, %7 : i32
    %9 = arith.muli %4, %2 : i32
    %10 = arith.addi %8, %9 : i32
    %11 = iarith.subi_imm %10, 1 : i32
    %12 = arith.divsi %11, %0 : i32
    %13 = iarith.addi_imm %1, 1 : i32
    %14 = arith.muli %12, %13 : i32
    %15 = iarith.subi_imm %14, 3 : i32
    %16 = iarith.addi_imm %15, 7 : i32
    %17 = iarith.muli_imm %16, 2 : i32
    func.return %17 : i32
  }
}