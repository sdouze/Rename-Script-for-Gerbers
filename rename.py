import os
import sys

# Maps a substring found in the original Gerber filename to the
# target extension/code it should be renamed to.
LAYER_RULES = [
    ("outline",          "gko"),  # Board outline / keep-out
    ("copper_bottom",    "gbl"),  # Bottom copper
    ("copper_top",       "gtl"),  # Top copper
    ("silkscreen_top",   "gto"),  # Top silkscreen / overlay
    ("soldermask_bottom","gbs"),  # Bottom solder mask
    ("soldermask_top",   "gts"),  # Top solder mask
]

GERBER_EXT = ".gbr"


def _matched_code(file_name):
    """Return (keyword, code) if the filename matches a rule, else (None, None).

    Matching is case-insensitive so 'Copper_Top.gbr' matches 'copper_top'.
    """
    name = file_name.lower()
    for keyword, code in LAYER_RULES:
        if keyword in name:
            return keyword, code
    return None, None


def _target_name(file_name, code):
    """Replace the file's extension with the layer code (e.g. .gbr -> .gtl)."""
    base, _ext = os.path.splitext(file_name)
    return f"{base}.{code}"


def scan_folder(directory_path):
    """Inspect a folder without changing anything.

    Returns a list of (old_name, new_name, layer, status) for every relevant
    file, where status is one of:
        'rename' -> will be renamed (new_name is the target)
        'done'   -> already has the correct extension (new_name is None)
        'skip'   -> a .gbr file with no matching rule (new_name is None)
    """
    rows = []
    for file_name in sorted(os.listdir(directory_path)):
        if not os.path.isfile(os.path.join(directory_path, file_name)):
            continue

        keyword, code = _matched_code(file_name)
        ext = os.path.splitext(file_name)[1].lower()

        if code:
            new_name = _target_name(file_name, code)
            if new_name == file_name:
                rows.append((file_name, None, keyword, "done"))
            else:
                rows.append((file_name, new_name, keyword, "rename"))
        elif ext == GERBER_EXT:
            rows.append((file_name, None, None, "skip"))
    return rows


def plan_renames(directory_path):
    """Return [(old_name, new_name, layer)] for files that will be renamed."""
    return [(old, new, layer)
            for (old, new, layer, status) in scan_folder(directory_path)
            if status == "rename"]


def rename_files_with_condition(directory_path, dry_run=False):
    """Rename Gerber files according to LAYER_RULES.

    Returns the list of (old_name, new_name, layer) that were (or would be)
    renamed. When ``dry_run`` is True, nothing is written to disk.
    """
    plan = plan_renames(directory_path)
    if not dry_run:
        for old_name, new_name, _ in plan:
            os.rename(
                os.path.join(directory_path, old_name),
                os.path.join(directory_path, new_name),
            )
    return plan


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python rename.py <directory_path>")
        sys.exit(1)

    results = rename_files_with_condition(sys.argv[1])
    for old_name, new_name, layer in results:
        print(f"{old_name} -> {new_name}  ({layer})")
    print(f"Done. {len(results)} file(s) renamed.")
