static int ga=1, gb=2, gs=0;
void __attribute__((noinline)) roi_block(void) {
  ga = ga + 1;
  gs = gs + ga;
  gb = gb + 1;
  gs = gs + gb;
  ga = ga + 2;
  gs = gs + ga;
  gb = gb + 1;
  gs = gs + gb;
}

int main(){
  volatile int sink = 0;
  int a = 1, b = 2, c = 3, s = 0;
  if ((a + 3) < 4) { s = s + 1; } else { s = s - 1; }
  if ((b + 4) < 5) { s = s + 1; } else { s = s - 1; }
  if ((a + 5) < 6) { s = s + 1; } else { s = s - 1; }
  if ((b + 6) < 7) { s = s + 1; } else { s = s - 1; }
  if ((a + 7) < 8) { s = s + 1; } else { s = s - 1; }
  if ((b + 8) < 9) { s = s + 1; } else { s = s - 1; }
  roi_block();
  a = a + 1;
  s = s + a;
  b = b + 1;
  s = s + b;
  a = a + 2;
  s = s + a;
  b = b + 1;
  s = s + b;
sink = sink + a + b + c + s;
  return sink;
}
