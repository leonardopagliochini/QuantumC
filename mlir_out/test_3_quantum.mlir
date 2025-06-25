builtin.module {
  func.func @main() -> i32 {
    %q0 = quantum.init 2 : i32
    %q1 = quantum.init 3 : i32
    %q0_1 = quantum.addi %q0, %q1 : i32
    %q1_1 = quantum.muli %q1, %q0_1 : i32
    %q1_2 = quantum.addi_imm %q1_1, 1 : i32
    %q2 = quantum.init 2 : i32
    %q1_3 = quantum.divsi %q1_2, %q2 : i32
    %q1_4 = quantum.muli_imm %q1_3, 2 : i32
    %q2_1 = quantum.addi %q2, %q1_4 : i32
    %q2_2 = quantum.subi_imm %q2_1, 2 : i32
    %q2_3 = quantum.muli_imm %q2_2, 3 : i32
    %q2_4 = quantum.addi_imm %q2_3, 4 : i32
    func.return %q2_4 : i32
  }
}