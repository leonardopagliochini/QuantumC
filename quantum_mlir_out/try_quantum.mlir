builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 5 : i32
    %q1 = quantum.init 0 : i32
    %q2 = quantum.subi %q1, %q0 : i32
    %q3 = quantum.addi_imm %q0, 1 : i32
    %q4 = quantum.subi_imm %q2, 1 : i32
    %q5 = quantum.init 0 : i32
    %q6 = quantum.init 0 : i32
    %q7 = quantum.cmpi %q5, %q6[0 : i64] : i32
    %q8 = quantum.init 12 : i32
    %q9 = quantum.init 0 : i32
    %q10 = quantum.init 1 : i32
    %q11 = quantum.subi %q9, %q8 : i32
    %q12 = quantum.subi %q11, %q10 : i32
    %q13 = quantum.addi %q3, %q4 : i32
    %q14 = quantum.addi %q13, %q0 : i32
    %q15 = quantum.addi %q14, %q2 : i32
    %q16 = quantum.addi %q15, %q12 : i32
    %q17 = quantum.addi %q16, %q2 : i32
    func.return %q17 : i32
  }
}