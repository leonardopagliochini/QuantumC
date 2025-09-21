int main(){
  volatile int sink = 0;
  int a = 1, b = 2, c = 3, s = 0;
sink = sink + a + b + c + s;
  return sink;
}
