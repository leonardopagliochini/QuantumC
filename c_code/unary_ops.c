int main() {
    int x = 5;
    int y = -x;     // unary minus
    int z = +y;     // unary plus (no-op)
    ++x;            // pre-increment
    --y;            // pre-decrement
    int a = x++;    // post-increment
    int b = y--;    // post-decrement
    int c = !0;     // logical NOT
    int d = ~a;     // bitwise NOT
    return x + y + a + b + c + d + z;
}
