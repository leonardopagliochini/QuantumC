int main(){
  volatile int sink = 0;
  int a = 1, b = 2, c = 3, s = 0;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  a = a + b;
  if ((a + 3) < 4) { s = s + 1; } else { s = s - 1; }
  if ((b + 4) < 5) { s = s + 1; } else { s = s - 1; }
  if ((a + 5) < 6) { s = s + 1; } else { s = s - 1; }
  if ((b + 6) < 7) { s = s + 1; } else { s = s - 1; }
  if ((a + 7) < 8) { s = s + 1; } else { s = s - 1; }
sink = sink + a + b + c + s;
  return sink;
}
