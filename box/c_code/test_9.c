int main() {
    int a = 2 + 3, b = a + 4, c = b + 5;
    c = c - 2;
    int d = a * b * c;
    int e = (a + b + c) * d;
    e = e + 7;
    int f = e / (b + 1), g = (f + e) * d;
    int h = (g + c) / (f + 1);
    h = h + (g * e);
    h = h - 6;
    int i = h * 2;
    i = i + 5;
    return i;
}