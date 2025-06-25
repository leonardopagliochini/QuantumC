builtin.module {
  func.func @main() -> i32 {
    %0 = arith.constant 1 : i32
    %1 = arith.addi %0, %0 : i32
    %2 = iarith.muli_imm %1, 2 : i32
    %3 = arith.addi %0, %0 : i32
    %4 = arith.muli %2, %3 : i32
    %5 = arith.muli %0, %2 : i32
    %6 = arith.muli %5, %4 : i32
    %7 = arith.addi %0, %2 : i32
    %8 = iarith.addi_imm %0, 7 : i32
    %9 = arith.addi %4, %0 : i32
    %10 = arith.addi %4, %2 : i32
    %11 = iarith.subi_imm %9, 7 : i32
    func.return %11 : i32
  }
}