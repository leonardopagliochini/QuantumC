"""Stand-alone test for the ``muli`` helper with 16 qubits."""

import test_arithmetics as ta


def main():
    """Run the muli test and print the result table."""
    ta.TOTAL_QUBITS = 8
    rows = ta._test_muli()
    ta._print_table(rows, csv_path="test_log/test_muli.csv")


if __name__ == "__main__":
    main()
