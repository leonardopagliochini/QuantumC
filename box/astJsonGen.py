"""Generate Clang JSON AST files from C sources.

This small helper module invokes ``clang`` for every ``.c`` file found in the
``c_code`` directory (or a custom ``input_dir``) and stores the produced JSON
AST under ``json_out``.  The intent is to make it easy to regenerate the test
inputs used by the rest of the project without having to remember the exact
``clang`` command line.
"""

import os
import subprocess

def astJsonGen(input_dir: str = "c_code") -> None:
    """Generate JSON ASTs for every ``.c`` file in ``input_dir``.

    Parameters
    ----------
    input_dir:
        Directory containing the C sources.  Each file in this directory is
        compiled with ``clang`` using the ``-ast-dump=json`` option and the
        resulting JSON is placed in a sibling ``json_out`` folder.
    """
    # Save the current working directory so we can build paths relative to it.
    current_dir = os.getcwd()

    # Build paths to the ``c_code`` directory and ``json_out`` output folder.
    c_code_folder = os.path.join(current_dir, input_dir)
    json_out_folder = os.path.join(current_dir, 'json_out')

    # Ensure the source directory exists before proceeding.
    if not os.path.isdir(c_code_folder):
        raise FileNotFoundError("Error: 'c_code' folder does not exist.")

    # Collect every C source file in ``c_code`` so we can process them below.
    c_files = [f for f in os.listdir(c_code_folder) if f.endswith('.c')]

    if not c_files:
        raise FileNotFoundError("Error: No .c files found in 'c_code' folder.")

    # Create the output directory where the JSON files will be written.
    os.makedirs(json_out_folder, exist_ok=True)

    # Iterate over all discovered C files and run Clang on each one.
    for c_file in c_files:
        c_file_path = os.path.join(c_code_folder, c_file)
        # Drop the ``.c`` extension to produce the JSON file name.
        base_name = os.path.splitext(c_file)[0]
        json_output_path = os.path.join(json_out_folder, f'{base_name}.json')

        # Invoke Clang to emit the JSON AST into the designated file.
        clang_ast_cmd_json = f'clang -Xclang -ast-dump=json -g -fsyntax-only {c_file_path} > {json_output_path}'
        subprocess.run(clang_ast_cmd_json, shell=True, check=True)

        # Verify that the output file was actually created.
        if not os.path.isfile(json_output_path):
            raise RuntimeError(f"Error: JSON output file {json_output_path} was not created.")

        print(f"JSON output saved to: {json_output_path}")
