import os
import subprocess

def generate_llvm_ir(input_dir: str = "c_code") -> None:
    """Generate LLVM IR (.ll) files from every ``.c`` file with loop unrolling only.

    Uses clang -O0 and applies the loop-unroll pass via opt.
    """
    current_dir = os.getcwd()
    c_code_folder = os.path.join(current_dir, input_dir)
    ll_out_folder = os.path.join(current_dir, 'json_out')

    if not os.path.isdir(c_code_folder):
        raise FileNotFoundError("Error: 'c_code' folder does not exist.")

    c_files = [f for f in os.listdir(c_code_folder) if f.endswith('.c')]
    if not c_files:
        raise FileNotFoundError("Error: No .c files found in 'c_code' folder.")

    os.makedirs(ll_out_folder, exist_ok=True)

    for c_file in c_files:
        c_file_path = os.path.join(c_code_folder, c_file)
        base_name = os.path.splitext(c_file)[0]
        ll_raw_path = os.path.join(ll_out_folder, f'{base_name}_raw.ll')
        ll_output_path = os.path.join(ll_out_folder, f'{base_name}.ll')

        # Step 1: Generate raw LLVM IR at -O0
        clang_cmd = f"clang -O0 -emit-llvm -S {c_file_path} -o {ll_raw_path}"
        subprocess.run(clang_cmd, shell=True, check=True)

        # Step 2: Apply loop-unroll pass using opt
        opt_cmd = f"opt -S -passes=loop-unroll {ll_raw_path} -o {ll_output_path}"
        subprocess.run(opt_cmd, shell=True, check=True)

        print(f"Unrolled LLVM IR saved to: {ll_output_path}")
