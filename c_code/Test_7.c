int main() {
    int a = 2, b = 2 + a, c = (a + b) * 3;
    int d = c * b;
    int e = d + (c / a);
    int f = e / (b + 1) + d;
    int g = (f * b) * (a + c);
    g = g + f / a;
    return 0;
}