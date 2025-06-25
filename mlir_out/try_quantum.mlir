builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 1 : i32
    %q0_1 = quantum.addi %q0, %q0 : i32
    %q0_2 = quantum.muli_imm %q0_1, 2 : i32
    %q2 = quantum.init 1 : i32
    %q2_1 = quantum.addi %q2, %q2 : i32
    %q2_2 = quantum.muli %q2_1, %q0_2 : i32
    %q4 = quantum.init 1 : i32
    %q4_1 = quantum.muli %q4, %q0_2 : i32
    %q4_2 = quantum.muli %q4_1, %q2_2 : i32
    %q5 = quantum.init 1 : i32
    %q5_1 = quantum.addi %q5, %q0_2 : i32
    %q6 = quantum.init 1 : i32
    %q6_1 = quantum.addi_imm %q6, 7 : i32
    %q7 = quantum.init 1 : i32
    %q7_1 = quantum.addi %q7, %q2_2 : i32
    %q0_3 = quantum.addi %q0_2, %q2_2 : i32
    %q7_2 = quantum.subi_imm %q7_1, 7 : i32
    func.return %q7_2 : i32
  }
}