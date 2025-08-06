builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 5 : i32
    func.return %q0 : i32
  }
}