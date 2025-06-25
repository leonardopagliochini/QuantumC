builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 1 : i32
    %q1 = quantum.init 2 : i32
    %q1_1 = quantum.muli_imm %q1, 2 : i32
    %q1_2 = quantum.addi_imm %q1_1, 1 : i32
    %q0_1 = quantum.addi %q0, %q1_2 : i32
    %q0_2 = quantum.subi_imm %q0_1, 3 : i32
    %q0_3 = quantum.addi_imm %q0_2, 3 : i32
    %q0_4 = quantum.muli_imm %q0_3, 2 : i32
    %q0_5 = quantum.subi_imm %q0_4, 5 : i32
    func.return %q0_5 : i32
  }
}