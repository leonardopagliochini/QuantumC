builtin.module {
  func.func @main() -> i32 {
    %0 = arith.constant 2 : i32
    %1 = arith.constant 3 : i32
    %2 = arith.addi %0, %1 : i32
    %3 = iarith.addi_imm %2, 4 : i32
    %4 = iarith.addi_imm %3, 5 : i32
    %5 = iarith.subi_imm %4, 2 : i32
    %6 = arith.muli %2, %3 : i32
    %7 = arith.muli %6, %5 : i32
    %8 = arith.addi %2, %3 : i32
    %9 = arith.addi %8, %5 : i32
    %10 = arith.muli %9, %7 : i32
    %11 = iarith.addi_imm %10, 7 : i32
    %12 = iarith.addi_imm %3, 1 : i32
    %13 = arith.divsi %11, %12 : i32
    %14 = arith.addi %13, %11 : i32
    %15 = arith.muli %14, %7 : i32
    %16 = arith.addi %15, %5 : i32
    %17 = iarith.addi_imm %13, 1 : i32
    %18 = arith.divsi %16, %17 : i32
    %19 = arith.muli %15, %11 : i32
    %20 = arith.addi %18, %19 : i32
    %21 = iarith.subi_imm %20, 6 : i32
    %22 = iarith.muli_imm %21, 2 : i32
    %23 = iarith.addi_imm %22, 5 : i32
    func.return %23 : i32
  }
}