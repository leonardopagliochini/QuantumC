int main() {
    int result = 0;
    for (int i = 0; i < 3; i = i + 1) {
        if (i == 1) {
            result = result + 10;
        }
    }
    return result;
}
