int main() {
    int a = 2 + 3, b = a + 4, c = b + 5;
    int d = a * b * c;
    int e = (a + b + c) * d;
    int f = e / (b + 1), g = (f + e) * d;
    int h = (g + c) / (f + 1);
    h = h + (g * e);
    return 0;
}