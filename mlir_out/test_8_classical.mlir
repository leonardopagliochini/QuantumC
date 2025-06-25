builtin.module {
  func.func @main() -> i32 {
    %0 = arith.constant 5 : i32
    %1 = arith.constant 3 : i32
    %2 = arith.addi %0, %1 : i32
    %3 = iarith.addi_imm %2, 2 : i32
    %4 = arith.addi %2, %3 : i32
    %5 = iarith.muli_imm %4, 2 : i32
    %6 = iarith.subi_imm %5, 3 : i32
    %7 = arith.divsi %6, %2 : i32
    %8 = arith.addi %3, %6 : i32
    %9 = arith.addi %7, %8 : i32
    %10 = arith.muli %7, %9 : i32
    %11 = iarith.addi_imm %10, 2 : i32
    %12 = arith.addi %11, %9 : i32
    %13 = iarith.addi_imm %3, 1 : i32
    %14 = arith.divsi %12, %13 : i32
    %15 = arith.muli %11, %6 : i32
    %16 = arith.addi %14, %15 : i32
    %17 = arith.divsi %9, %2 : i32
    %18 = arith.addi %16, %17 : i32
    %19 = iarith.addi_imm %18, 9 : i32
    %20 = iarith.subi_imm %19, 4 : i32
    %21 = iarith.muli_imm %20, 3 : i32
    func.return %21 : i32
  }
}