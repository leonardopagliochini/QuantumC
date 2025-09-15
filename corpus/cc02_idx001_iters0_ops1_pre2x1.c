int main(){
  volatile int sink = 0;
  int a = 1, b = 2, c = 3, s = 0;
  a = a + b;
  a = a + b;
  if ((a + 3) < 4) { s = s + 1; } else { s = s - 1; }
sink = sink + a + b + c + s;
  return sink;
}
