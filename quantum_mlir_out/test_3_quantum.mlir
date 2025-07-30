builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 2 : i32
    %q1 = quantum.init 3 : i32
    %q2 = quantum.addi %q0, %q1 : i32
    %q3 = quantum.muli %q2, %q1 : i32
    %q4 = quantum.addi_imm %q3, 1 : i32
    %q5 = quantum.divsi %q4, %q0 : i32
    %q6 = quantum.muli_imm %q5, 2 : i32
    %q7 = quantum.addi %q6, %q0 : i32
    %q8 = quantum.subi_imm %q7, 2 : i32
    %q9 = quantum.muli_imm %q8, 3 : i32
    %q10 = quantum.addi_imm %q9, 4 : i32
    func.return %q10 : i32
  }
}