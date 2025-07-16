"""Stand-alone test for the ``sub`` helper with 16 qubits."""

import test_arithmetics as ta


def main():
    """Run the subtraction test and print the result table."""
    ta.TOTAL_QUBITS = 16
    rows = ta._test_sub()
    ta._print_table(rows, csv_path="test_log/test_sub.csv")


if __name__ == "__main__":
    main()
