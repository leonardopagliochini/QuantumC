"""Stand-alone test for the ``subi`` helper with 16 qubits."""

import test_arithmetics as ta


def main():
    """Run the subi test and print the result table."""
    ta.TOTAL_QUBITS = 16
    rows = ta._test_subi()
    ta._print_table(rows)


if __name__ == "__main__":
    main()
