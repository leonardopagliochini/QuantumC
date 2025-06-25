builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 4 : i32
    %q0_1 = quantum.addi_imm %q0, 3 : i32
    %q0_2 = quantum.addi_imm %q0_1, 7 : i32
    %q2 = quantum.init 4 : i32
    %q3 = quantum.addi_imm %q2, 3 : i32
    %q2_1 = quantum.muli %q2, %q3 : i32
    %q2_2 = quantum.addi_imm %q2_1, 2 : i32
    %q0_3 = quantum.addi %q0_2, %q2_2 : i32
    %q0_4 = quantum.muli %q0_3, %q3 : i32
    %q5 = quantum.init 4 : i32
    %q5_1 = quantum.addi_imm %q5, 1 : i32
    %q0_5 = quantum.divsi %q0_4, %q5_1 : i32
    %q6 = quantum.addi_imm %q3, 7 : i32
    %q6_1 = quantum.muli %q6, %q2_2 : i32
    %q6_2 = quantum.addi %q6_1, %q0_5 : i32
    %q6_3 = quantum.subi_imm %q6_2, 1 : i32
    %q7 = quantum.init 4 : i32
    %q6_4 = quantum.divsi %q6_3, %q7 : i32
    %q3_1 = quantum.addi_imm %q3, 1 : i32
    %q3_2 = quantum.muli %q3_1, %q6_4 : i32
    %q3_3 = quantum.subi_imm %q3_2, 3 : i32
    %q3_4 = quantum.addi_imm %q3_3, 7 : i32
    %q3_5 = quantum.muli_imm %q3_4, 2 : i32
    func.return %q3_5 : i32
  }
}