builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 3 : i32
    %q1 = quantum.init 4 : i32
    %q2 = quantum.addi %q0, %q1 : i32
    func.return %q2 : i32
  }
}