int main() {
    int x = 5 + 3, y = x + 2, z = (x + y) * 2;
    int p = z / x, q = p + (y + z);
    p = p * q;
    int r = (p + q) / (y + 1);
    int s = r + (p * z) + (q / x);
    return 0;
}