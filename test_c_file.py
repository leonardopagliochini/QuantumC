#!/usr/bin/env python3

import subprocess
import argparse
import os
import sys

def compile_and_run_c(c_path: str) -> str:
    exe_path = "main"
    try:
        subprocess.run(["gcc", c_path, "-o", exe_path], check=True)
        result = subprocess.run([f"./{exe_path}"], capture_output=True, text=True)
        returncode = str(result.returncode)
        print(f"[C OUTPUT] Return code: {returncode}")
        return returncode
    except subprocess.CalledProcessError as e:
        print("[ERROR] Compilation failed:", e)
        sys.exit(1)
    finally:
        if os.path.exists(exe_path):
            os.remove(exe_path)


def run_quantum_pipeline(c_path: str) -> str:
    try:
        result = subprocess.run(
            [sys.executable, "pipeline.py", c_path, "--run"],
            capture_output=True,
            text=True
        )
        quantum_output = result.stdout + result.stderr
        print("[Quantum OUTPUT]")
        print(quantum_output)
        return quantum_output
    except subprocess.CalledProcessError as e:
        print("[ERROR] Quantum execution failed:", e)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Compare classical and quantum output.")
    parser.add_argument("c_file", help="Path to the input C file")
    args = parser.parse_args()

    print(f"\n[INFO] Running classical execution for {args.c_file}")
    classical_output = compile_and_run_c(args.c_file)

    print(f"\n[INFO] Running quantum pipeline for {args.c_file}")
    quantum_output = run_quantum_pipeline(args.c_file)

    print("\n[SUMMARY]")
    if classical_output in quantum_output:
        print(f"[✅] Classical result '{classical_output}' found in quantum output!")
    else:
        print(f"[❌] Classical result '{classical_output}' NOT found in quantum output!")

if __name__ == "__main__":
    main()


