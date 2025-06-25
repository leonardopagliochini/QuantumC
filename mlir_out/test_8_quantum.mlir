builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 5 : i32
    %q1 = quantum.init 3 : i32
    %q0_1 = quantum.addi %q0, %q1 : i32
    %q0_2 = quantum.addi_imm %q0_1, 2 : i32
    %q4 = quantum.init 5 : i32
    %q2 = quantum.addi %q4, %q1 : i32
    %q2_1 = quantum.addi %q2, %q0_2 : i32
    %q2_2 = quantum.muli_imm %q2_1, 2 : i32
    %q2_3 = quantum.subi_imm %q2_2, 3 : i32
    %q5 = quantum.addi %q4, %q1 : i32
    %q2_4 = quantum.divsi %q2_3, %q5 : i32
    %q8 = quantum.addi %q5, %q0_2 : i32
    %q7 = quantum.muli_imm %q8, 2 : i32
    %q6 = quantum.subi_imm %q7, 3 : i32
    %q0_3 = quantum.addi %q0_2, %q6 : i32
    %q0_4 = quantum.addi %q0_3, %q2_4 : i32
    %q2_5 = quantum.muli %q2_4, %q0_4 : i32
    %q2_6 = quantum.addi_imm %q2_5, 2 : i32
    %q0_5 = quantum.addi %q0_4, %q2_6 : i32
    %q9 = quantum.addi_imm %q5, 2 : i32
    %q9_1 = quantum.addi_imm %q9, 1 : i32
    %q0_6 = quantum.divsi %q0_5, %q9_1 : i32
    %q6_1 = quantum.muli %q6, %q2_6 : i32
    %q6_2 = quantum.addi %q6_1, %q0_6 : i32
    %q10 = quantum.subi_imm %q7, 3 : i32
    %q2_7 = quantum.divsi %q10, %q5 : i32
    %q9_2 = quantum.addi_imm %q5, 2 : i32
    %q0_7 = quantum.addi %q9_2, %q10 : i32
    %q0_8 = quantum.addi %q0_7, %q2_7 : i32
    %q0_9 = quantum.divsi %q0_8, %q5 : i32
    %q0_10 = quantum.addi %q0_9, %q6_2 : i32
    %q0_11 = quantum.addi_imm %q0_10, 9 : i32
    %q0_12 = quantum.subi_imm %q0_11, 4 : i32
    %q0_13 = quantum.muli_imm %q0_12, 3 : i32
    func.return %q0_13 : i32
  }
}