static int ga=1, gb=2, gs=0;
void __attribute__((noinline)) roi_block(void) {
  ga = ga + 1;
  gs = gs + ga;
  gb = gb + 1;
  gs = gs + gb;
}

int main(){
  volatile int sink = 0;
  int a = 1, b = 2, c = 3, s = 0;
  roi_block();
  a = a + 1;
  s = s + a;
  b = b + 1;
  s = s + b;
sink = sink + a + b + c + s;
  return sink;
}
