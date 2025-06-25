builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 1 : i32
    %q0_1 = quantum.addi_imm %q0, 4 : i32
    %q2 = quantum.init 1 : i32
    %q2_1 = quantum.addi %q2, %q0_1 : i32
    %q2_2 = quantum.addi_imm %q2_1, 2 : i32
    %q0_2 = quantum.muli %q0_1, %q2_2 : i32
    %q4 = quantum.init 1 : i32
    %q4_1 = quantum.addi_imm %q4, 1 : i32
    %q4_2 = quantum.muli %q4_1, %q0_2 : i32
    %q4_3 = quantum.addi_imm %q4_2, 3 : i32
    %q2_3 = quantum.addi_imm %q2_2, 1 : i32
    %q4_4 = quantum.divsi %q4_3, %q2_3 : i32
    %q4_5 = quantum.addi_imm %q4_4, 10 : i32
    %q4_6 = quantum.subi_imm %q4_5, 5 : i32
    %q4_7 = quantum.muli_imm %q4_6, 2 : i32
    func.return %q4_7 : i32
  }
}