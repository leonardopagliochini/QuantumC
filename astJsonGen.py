import os
import subprocess

def astJsonGen(input_dir="c_code"):
    # Save the current working directory (location of the script)
    current_dir = os.getcwd()

    # Define paths relative to the current directory
    c_code_folder = os.path.join(current_dir, input_dir)
    json_out_folder = os.path.join(current_dir, 'json_out')

    # Check if the c_code folder exists
    if not os.path.isdir(c_code_folder):
        raise FileNotFoundError("Error: 'c_code' folder does not exist.")

    # List all .c files in the c_code folder
    c_files = [f for f in os.listdir(c_code_folder) if f.endswith('.c')]

    if not c_files:
        raise FileNotFoundError("Error: No .c files found in 'c_code' folder.")

    # Ensure the output folder exists
    os.makedirs(json_out_folder, exist_ok=True)

    # Process each .c file
    for c_file in c_files:
        c_file_path = os.path.join(c_code_folder, c_file)
        base_name = os.path.splitext(c_file)[0]  # Get base name without extension
        json_output_path = os.path.join(json_out_folder, f'{base_name}.json')

        # Run clang to generate AST in JSON format
        clang_ast_cmd_json = f'clang -Xclang -ast-dump=json -g -fsyntax-only {c_file_path} > {json_output_path}'
        subprocess.run(clang_ast_cmd_json, shell=True, check=True)

        # Verify if the JSON output file was successfully created
        if not os.path.isfile(json_output_path):
            raise RuntimeError(f"Error: JSON output file {json_output_path} was not created.")

        print(f"JSON output saved to: {json_output_path}")