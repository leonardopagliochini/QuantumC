int main() {
    int x = 5 + 3, y = x + 2, z = (x + y) * 2;
    z = z - 3;
    int p = z / x, q = p + (y + z);
    p = p * q;
    p = p + 2;
    int r = (p + q) / (y + 1);
    int s = r + (p * z) + (q / x);
    s = s + 9;
    int t = s - 4;
    t = t * 3;
    return t;
}