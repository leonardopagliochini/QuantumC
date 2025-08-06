builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 5 : i32
    %q1 = quantum.init 1 : i32
    %q2 = quantum.cmpi %q0, %q1[0 : i64] : i32
    %q3 = quantum.c_init(%q2) 10 : i32 : i32
    func.return %q3 : i32
    %q5 = quantum.not %q2
    %q6 = quantum.c_init(%q5) 5 : i32 : i32
    %q7 = quantum.cmpi %q0, %q6[0 : i64] : i32
    %q8 = quantum.and %q5, %q7
    %q9 = quantum.c_init(%q8) 20 : i32 : i32
    func.return %q9 : i32
    %q10 = quantum.not %q7
    %q11 = quantum.and %q5, %q10
    %q12 = quantum.c_init(%q11) 0 : i32 : i32
    func.return %q12 : i32
  }
}