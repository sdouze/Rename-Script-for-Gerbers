# Gerber Renamer

A modern GUI tool that renames KiCad Gerber export files to the standard extensions expected by most PCB manufacturers.

| KiCad layer name | Standard extension |
|---|---|
| `*outline*` | `.gko` |
| `*copper_top*` | `.gtl` |
| `*copper_bottom*` | `.gbl` |
| `*silkscreen_top*` | `.gto` |
| `*soldermask_top*` | `.gts` |
| `*soldermask_bottom*` | `.gbs` |

Matching is case-insensitive. Files that don't match any rule are shown but left untouched.

---

## Download

Grab the latest **GerberRenamer.exe** from the [Releases](../../releases/latest) page — no installation needed, just run it.

---

## Run from source

**Requirements:** Python 3.10+

```bash
pip install -r requirements.txt
python gui_dragdrop.py
```

### Dependencies
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — modern Material-style UI
- [tkinterdnd2](https://github.com/pmgagne/tkinterdnd2) — drag & drop support

---

## Features

- **Drag & drop** a Gerber folder directly onto the drop zone
- **Browse** opens the native Windows folder picker (shows files inside each folder)
- **Preview** — see exactly which files will be renamed before committing
- **Rename files** — renames in one click; preview turns green on success
- **Create ZIP** — packages all files in the folder into a ready-to-send archive (appears after rename)
- **Open folder** — opens the folder in Explorer
- **Dark / Light** theme toggle

---

## Build executable

```bash
pip install pyinstaller
pyinstaller gui_dragdrop.spec
```

The standalone `.exe` will be in `dist/`.

---

## Usage as CLI

```bash
python rename.py <path/to/gerber/folder>
```
