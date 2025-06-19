int main() {
    int a = 3 + 2, b = 4 + a, c = (a + b) * (b + 1);
    int d = c + (a + b);
    int e = d * c * (a + 1);
    int f = e / (d + 2), g = (f + e) * a;
    int h = g + (b + c), i = h * (h + g);
    int j = i / (a + b), k = j + (i + 1);
    k = k * (e + f) + (g + h + i + j);
    return 0;
}