int main() {
    int a = 4, b = a + 3, c = b + 7;
    int x = a * b + 2;  int y = (c + x) * b;
    int z = y / (a + 1);
    z = z + (x * c) - 1;
    int w = (z / a) * (b + 1);
    w = w - 3;
    int v = w + 7;
    v = v * 2;
    return 0;
}