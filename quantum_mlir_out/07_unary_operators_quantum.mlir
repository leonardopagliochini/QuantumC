builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 5 : i32
    %q1 = quantum.init 0 : i32
    %q2 = quantum.subi %q1, %q0 : i32
    %q3 = quantum.addi_imm %q2, 1 : i32
    func.return %q3 : i32
  }
}