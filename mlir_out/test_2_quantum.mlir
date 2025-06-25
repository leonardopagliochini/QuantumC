builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 2 : i32
    %q1 = quantum.init 3 : i32
    %q1_1 = quantum.addi_imm %q1, 5 : i32
    %q1_2 = quantum.addi %q1_1, %q0 : i32
    %q0_1 = quantum.addi_imm %q0, 2 : i32
    %q0_2 = quantum.muli %q0_1, %q1_2 : i32
    %q0_3 = quantum.addi_imm %q0_2, 4 : i32
    %q0_4 = quantum.subi_imm %q0_3, 1 : i32
    %q0_5 = quantum.muli_imm %q0_4, 2 : i32
    func.return %q0_5 : i32
  }
}