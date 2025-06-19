int main() {
    int a = 4, b = a + 3, c = b + 7;
    int x = a * b;  int y = (c + x) * b;
    int z = y / (a + 1);
    z = z + (x * c);
    int w = (z / a) * (b + 1);
    return 0;
}