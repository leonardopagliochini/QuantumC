builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 1 : i32
    %q1 = quantum.init 2 : i32
    %q2 = quantum.init 3 : i32
    %q3 = quantum.addi %q0, %q1 : i32
    %q4 = quantum.muli %q3, %q2 : i32
    func.return %q4 : i32
  }
}