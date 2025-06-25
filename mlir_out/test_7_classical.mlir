builtin.module {
  func.func @main() -> i32 {
    %0 = arith.constant 2 : i32
    %1 = iarith.addi_imm %0, 2 : i32
    %2 = arith.addi %0, %1 : i32
    %3 = iarith.muli_imm %2, 3 : i32
    %4 = iarith.subi_imm %3, 1 : i32
    %5 = arith.muli %4, %1 : i32
    %6 = arith.divsi %4, %0 : i32
    %7 = arith.addi %5, %6 : i32
    %8 = iarith.addi_imm %7, 2 : i32
    %9 = iarith.addi_imm %1, 1 : i32
    %10 = arith.divsi %8, %9 : i32
    %11 = arith.addi %10, %5 : i32
    %12 = arith.muli %11, %1 : i32
    %13 = arith.addi %0, %4 : i32
    %14 = arith.muli %12, %13 : i32
    %15 = iarith.addi_imm %14, 3 : i32
    %16 = arith.divsi %11, %0 : i32
    %17 = arith.addi %15, %16 : i32
    %18 = iarith.subi_imm %17, 4 : i32
    %19 = iarith.muli_imm %18, 5 : i32
    %20 = iarith.divsi_imm %19, 2 : i32
    func.return %20 : i32
  }
}