"""Stand-alone test for the ``add`` helper with 16 qubits."""

import test_arithmetics as ta


def main():
    """Run the addition test and print the result table."""
    ta.TOTAL_QUBITS = 12
    rows = ta._test_add()
    ta._print_table(rows, csv_path="test_log/test_add.csv")


if __name__ == "__main__":
    main()
