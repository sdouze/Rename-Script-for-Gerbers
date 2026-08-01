#Usage:In CMD python rename.py <path>

import os
import sys

def rename_files_with_condition(directory_path):
    # List all files in the directory
    files = os.listdir(directory_path)

    for file_name in files:

        if "outline" in file_name:
            new_name = file_name.replace("gbr", "gko")
            old_path = os.path.join(directory_path, file_name)
            new_path = os.path.join(directory_path, new_name)
            os.rename(old_path, new_path)

        elif "copper_bottom" in file_name:
            new_name = file_name.replace("gbr", "gbl")
            old_path = os.path.join(directory_path, file_name)
            new_path = os.path.join(directory_path, new_name)
            os.rename(old_path, new_path)

        elif "copper_top" in file_name:
            new_name = file_name.replace("gbr", "gtl")
            old_path = os.path.join(directory_path, file_name)
            new_path = os.path.join(directory_path, new_name)
            os.rename(old_path, new_path)

        elif "silkscreen_top" in file_name:
            new_name = file_name.replace("gbr", "gto")
            old_path = os.path.join(directory_path, file_name)
            new_path = os.path.join(directory_path, new_name)
            os.rename(old_path, new_path)

        elif "soldermask_bottom" in file_name:
            new_name = file_name.replace("gbr", "gbs")
            old_path = os.path.join(directory_path, file_name)
            new_path = os.path.join(directory_path, new_name)
            os.rename(old_path, new_path)            

        elif "soldermask_top" in file_name:
            new_name = file_name.replace("gbr", "gts")
            old_path = os.path.join(directory_path, file_name)
            new_path = os.path.join(directory_path, new_name)
            os.rename(old_path, new_path)  

    print("Done")          

# Call the function to perform the renaming

if __name__ == "__main__":
    # Check if the correct number of command-line arguments is provided
    if len(sys.argv) != 2:
        print("Usage: python rename.py <directory_path>")
        sys.exit(1)

    # Get the directory path from the command-line argument
    directory_path = sys.argv[1]

    # Call the function to perform the renaming
    rename_files_with_condition(directory_path)

