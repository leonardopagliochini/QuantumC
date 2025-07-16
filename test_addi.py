"""Stand-alone test for the ``addi`` helper with 16 qubits."""

import test_arithmetics as ta


def main():
    """Run the addi test and print the result table."""
    ta.TOTAL_QUBITS = 8
    rows = ta._test_addi()
    ta._print_table(rows, csv_path="test_log/test_addi.csv")


if __name__ == "__main__":
    main()
