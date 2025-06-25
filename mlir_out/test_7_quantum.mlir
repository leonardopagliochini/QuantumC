builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 2 : i32
    %q0_1 = quantum.addi_imm %q0, 2 : i32
    %q2 = quantum.init 2 : i32
    %q2_1 = quantum.addi %q2, %q0_1 : i32
    %q2_2 = quantum.muli_imm %q2_1, 3 : i32
    %q2_3 = quantum.subi_imm %q2_2, 1 : i32
    %q0_2 = quantum.muli %q0_1, %q2_3 : i32
    %q4 = quantum.init 2 : i32
    %q2_4 = quantum.divsi %q2_3, %q4 : i32
    %q2_5 = quantum.addi %q2_4, %q0_2 : i32
    %q2_6 = quantum.addi_imm %q2_5, 2 : i32
    %q5 = quantum.addi_imm %q4, 2 : i32
    %q5_1 = quantum.addi_imm %q5, 1 : i32
    %q2_7 = quantum.divsi %q2_6, %q5_1 : i32
    %q0_3 = quantum.addi %q0_2, %q2_7 : i32
    %q5_2 = quantum.addi_imm %q4, 2 : i32
    %q5_3 = quantum.muli %q5_2, %q0_3 : i32
    %q6 = quantum.addi_imm %q4, 2 : i32
    %q2_8 = quantum.addi %q4, %q6 : i32
    %q2_9 = quantum.muli_imm %q2_8, 3 : i32
    %q2_10 = quantum.subi_imm %q2_9, 1 : i32
    %q2_11 = quantum.addi %q2_10, %q4 : i32
    %q2_12 = quantum.muli %q2_11, %q5_3 : i32
    %q2_13 = quantum.addi_imm %q2_12, 3 : i32
    %q0_4 = quantum.divsi %q0_3, %q4 : i32
    %q0_5 = quantum.addi %q0_4, %q2_13 : i32
    %q0_6 = quantum.subi_imm %q0_5, 4 : i32
    %q0_7 = quantum.muli_imm %q0_6, 5 : i32
    %q0_8 = quantum.divsi_imm %q0_7, 2 : i32
    func.return %q0_8 : i32
  }
}