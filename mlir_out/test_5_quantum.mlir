builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 3 : i32
    %q1 = quantum.init 2 : i32
    %q0_1 = quantum.addi %q0, %q1 : i32
    %q0_2 = quantum.addi_imm %q0_1, 5 : i32
    %q0_3 = quantum.subi_imm %q0_2, 1 : i32
    %q4 = quantum.init 3 : i32
    %q2 = quantum.addi %q4, %q1 : i32
    %q0_4 = quantum.divsi %q0_3, %q2 : i32
    %q6 = quantum.addi_imm %q2, 5 : i32
    %q5 = quantum.subi_imm %q6, 1 : i32
    %q2_1 = quantum.addi %q2, %q5 : i32
    %q2_2 = quantum.addi %q2_1, %q0_4 : i32
    %q2_3 = quantum.muli_imm %q2_2, 2 : i32
    %q2_4 = quantum.addi_imm %q2_3, 3 : i32
    %q5_1 = quantum.muli %q5, %q2_4 : i32
    %q7 = quantum.addi %q4, %q1 : i32
    %q0_5 = quantum.addi %q0_4, %q7 : i32
    %q0_6 = quantum.muli %q0_5, %q5_1 : i32
    %q0_7 = quantum.divsi %q0_6, %q2_4 : i32
    %q7_1 = quantum.addi %q7, %q0_7 : i32
    %q7_2 = quantum.subi_imm %q7_1, 2 : i32
    %q7_3 = quantum.muli_imm %q7_2, 4 : i32
    %q7_4 = quantum.addi_imm %q7_3, 8 : i32
    func.return %q7_4 : i32
  }
}