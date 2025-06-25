builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 2 : i32
    %q1 = quantum.init 3 : i32
    %q0_1 = quantum.addi %q0, %q1 : i32
    %q0_2 = quantum.addi_imm %q0_1, 4 : i32
    %q0_3 = quantum.addi_imm %q0_2, 5 : i32
    %q0_4 = quantum.subi_imm %q0_3, 2 : i32
    %q4 = quantum.init 2 : i32
    %q2 = quantum.addi %q4, %q1 : i32
    %q5 = quantum.addi_imm %q2, 4 : i32
    %q2_1 = quantum.muli %q2, %q5 : i32
    %q2_2 = quantum.muli %q2_1, %q0_4 : i32
    %q6 = quantum.addi %q4, %q1 : i32
    %q6_1 = quantum.addi %q6, %q5 : i32
    %q6_2 = quantum.addi %q6_1, %q0_4 : i32
    %q6_3 = quantum.muli %q6_2, %q2_2 : i32
    %q6_4 = quantum.addi_imm %q6_3, 7 : i32
    %q5_1 = quantum.addi_imm %q5, 1 : i32
    %q6_5 = quantum.divsi %q6_4, %q5_1 : i32
    %q11 = quantum.addi %q4, %q1 : i32
    %q5_2 = quantum.addi_imm %q11, 4 : i32
    %q10 = quantum.addi %q11, %q5_2 : i32
    %q9 = quantum.addi %q10, %q0_4 : i32
    %q8 = quantum.muli %q9, %q2_2 : i32
    %q7 = quantum.addi_imm %q8, 7 : i32
    %q7_1 = quantum.addi %q7, %q6_5 : i32
    %q2_3 = quantum.muli %q2_2, %q7_1 : i32
    %q0_5 = quantum.addi %q0_4, %q2_3 : i32
    %q6_6 = quantum.addi_imm %q6_5, 1 : i32
    %q0_6 = quantum.divsi %q0_5, %q6_6 : i32
    %q7_2 = quantum.addi_imm %q8, 7 : i32
    %q7_3 = quantum.muli %q7_2, %q2_3 : i32
    %q7_4 = quantum.addi %q7_3, %q0_6 : i32
    %q7_5 = quantum.subi_imm %q7_4, 6 : i32
    %q7_6 = quantum.muli_imm %q7_5, 2 : i32
    %q7_7 = quantum.addi_imm %q7_6, 5 : i32
    func.return %q7_7 : i32
  }
}