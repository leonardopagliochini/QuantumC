int main() {
    int a = 3 + 2, b = 4 + a, c = (a + b) * (b + 1);
    c = c + 2;
    int d = c + (a + b);
    int e = d * c * (a + 1);
    e = e - 3;
    int f = e / (d + 2), g = (f + e) * a;
    int h = g + (b + c), i = h * (h + g);
    int j = i / (a + b), k = j + (i + 1);
    k = k * (e + f) + (g + h + i + j);
    k = k - 8;
    int m = k + 12;
    m = m * 2;
    return 0;
}