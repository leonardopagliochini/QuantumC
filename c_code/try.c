int main() {
    int base = (5 + 7);          // ADD
    int diff = (base - 3);        // SUB
    int prod = (diff * 4);        // MUL
    int quotient = (prod / 2);    // DIV
    int remainder = (quotient % 5); // REM
    int toggle = (remainder ^ 6);  // XOR (toggle some bits)
    int merged = (toggle | 1);    // OR (force last bit on)
    int masked = (merged & 7);    // AND (keep only 3 bits)
    int non_I = (diff - prod);
    int multip_op = (quotient + prod) * base;

    return 0;
}
