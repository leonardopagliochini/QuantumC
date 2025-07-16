"""Stand-alone test for the ``div`` helper with 16 qubits."""

import test_arithmetics as ta


def main():
    """Run the division test and print the result table."""
    ta.TOTAL_QUBITS = 16
    rows = ta._test_division()
    ta._print_table(rows)


if __name__ == "__main__":
    main()
