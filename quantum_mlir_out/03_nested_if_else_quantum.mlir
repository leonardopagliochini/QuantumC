builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 4 : i32
    %q1 = quantum.init 7 : i32
    %q2 = quantum.cmpi %q0, %q1[2 : i64] : i32
    %q3 = quantum.c_init(%q2) 1 : i32 : i32
    func.return %q3 : i32
    %q5 = quantum.not %q2
    %q6 = quantum.c_init(%q5) 0 : i32 : i32
    func.return %q6 : i32
  }
}