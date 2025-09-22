int main(){
  volatile int sink = 0;
  int a = 1, b = 2, c = 3, s = 0;
  if ((a + 3) < 4) { s = s + 1; } else { s = s - 1; }
  if ((b + 4) < 5) { s = s + 1; } else { s = s - 1; }
  if ((a + 5) < 6) { s = s + 1; } else { s = s - 1; }
  if ((b + 6) < 7) { s = s + 1; } else { s = s - 1; }
  if ((a + 7) < 8) { s = s + 1; } else { s = s - 1; }
  if ((b + 8) < 9) { s = s + 1; } else { s = s - 1; }
  if ((a + 9) < 10) { s = s + 1; } else { s = s - 1; }
  if ((b + 10) < 11) { s = s + 1; } else { s = s - 1; }
  if ((a + 11) < 12) { s = s + 1; } else { s = s - 1; }
  if ((b + 12) < 13) { s = s + 1; } else { s = s - 1; }
  if ((a + 13) < 14) { s = s + 1; } else { s = s - 1; }
  if ((b + 14) < 15) { s = s + 1; } else { s = s - 1; }
  if ((a + 15) < 16) { s = s + 1; } else { s = s - 1; }
  if ((b + 16) < 17) { s = s + 1; } else { s = s - 1; }
  if ((a + 17) < 18) { s = s + 1; } else { s = s - 1; }
  if ((b + 18) < 19) { s = s + 1; } else { s = s - 1; }
  if ((a + 19) < 20) { s = s + 1; } else { s = s - 1; }
  if ((b + 20) < 21) { s = s + 1; } else { s = s - 1; }
  if ((a + 21) < 22) { s = s + 1; } else { s = s - 1; }
  if ((b + 22) < 23) { s = s + 1; } else { s = s - 1; }
  if ((a + 23) < 24) { s = s + 1; } else { s = s - 1; }
  if ((b + 24) < 25) { s = s + 1; } else { s = s - 1; }
sink = sink + a + b + c + s;
  return sink;
}
