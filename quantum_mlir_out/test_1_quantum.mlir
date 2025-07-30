builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 1 : i32
    %q1 = quantum.init 2 : i32
    %q2 = quantum.muli_imm %q1, 2 : i32
    %q3 = quantum.addi_imm %q2, 1 : i32
    %q4 = quantum.addi %q0, %q3 : i32
    %q5 = quantum.subi_imm %q4, 3 : i32
    %q6 = quantum.addi_imm %q5, 3 : i32
    %q7 = quantum.muli_imm %q6, 2 : i32
    %q8 = quantum.subi_imm %q7, 5 : i32
    func.return %q8 : i32
  }
}