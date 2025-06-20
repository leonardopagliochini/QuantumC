int main() {
    int a = 2, b = 2 + a, c = (a + b) * 3;
    c = c - 1;
    int d = c * b;
    int e = d + (c / a);
    e = e + 2;
    int f = e / (b + 1) + d;
    int g = (f * b) * (a + c) + 3;
    g = g + f / a - 4;
    int h = g * 5;
    h = h / 2;
    return 0;
}