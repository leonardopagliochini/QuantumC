#include <stdio.h>

int main() {
    int a = 1;
    int b = 2 * (a + a);
    int c = b * (a + a);

    int genova = a * b * c;

    int d, e, f, g;

    d = a + b;
    e = a + 7;
    f = c + a;
    g = c + b;

    int qst = 7 - f;

    // Print all variables for comparison
    printf("a = %d\n", a);
    printf("b = %d\n", b);
    printf("c = %d\n", c);
    printf("genova = %d\n", genova);
    printf("d = %d\n", d);
    printf("e = %d\n", e);
    printf("f = %d\n", f);
    printf("g = %d\n", g);
    printf("qst = %d\n", qst);

    return 0;
}
