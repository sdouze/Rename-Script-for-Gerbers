import os
import ctypes
import ctypes.wintypes
import zipfile
import customtkinter as ctk
from tkinter import filedialog
from tkinterdnd2 import TkinterDnD, DND_FILES

from rename import plan_renames, rename_files_with_condition, scan_folder

# --- Material-ish palette ----------------------------------------------------
ACCENT      = "#4f8cff"
ACCENT_HOVER = "#3b78ec"
SUCCESS     = "#2ecc71"
DANGER      = "#ff5d5d"
MUTED       = "#8a909c"

# Per-layer chip colors (Gerber layer code -> color)
LAYER_COLORS = {
    "gtl": "#ff6b6b",  # copper top
    "gbl": "#ff9f43",  # copper bottom
    "gko": "#a55eea",  # outline
    "gto": "#2dd4bf",  # silkscreen top
    "gts": "#4f8cff",  # soldermask top
    "gbs": "#5c7cfa",  # soldermask bottom
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

FONT_TITLE = ("Segoe UI Semibold", 22)
FONT_SUB   = ("Segoe UI", 12)
FONT       = ("Segoe UI", 13)
FONT_BOLD  = ("Segoe UI", 13, "bold")
FONT_SMALL = ("Segoe UI", 11)
FONT_MONO  = ("Cascadia Code", 12)


def _win32_pick_folder(hwnd=0):
    """
    Open the Windows Vista+ folder picker via IFileOpenDialog + FOS_PICKFOLDERS.
    Unlike tkinter's askdirectory, this dialog renders the files inside each
    folder (greyed out) so the user can orient themselves before confirming.
    Returns the selected path string, or None if the user cancelled.
    Falls back to tkinter's askdirectory on any COM/API error.
    """
    S_OK                = 0
    CLSCTX_INPROC       = 1
    FOS_PICKFOLDERS     = 0x00000020
    FOS_FORCEFILESYSTEM = 0x00000040
    SIGDN_FILESYSPATH   = ctypes.c_uint32(0x80058000)

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong),
                    ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort),
                    ("Data4", ctypes.c_ubyte * 8)]

    CLSID = GUID(0xDC1C5A9C, 0xE88A, 0x4DDE,
                 (ctypes.c_ubyte * 8)(0xA5,0xA1,0x60,0xF8,0x2A,0x20,0xAE,0xF7))
    IID   = GUID(0xD57C7288, 0xD4AD, 0x4768,
                 (ctypes.c_ubyte * 8)(0xBE,0x02,0x9D,0x96,0x95,0x32,0xD9,0x60))

    ole32 = ctypes.windll.ole32
    hr_init = ole32.CoInitialize(None)
    if hr_init not in (S_OK, 1):   # 1 = S_FALSE (already init on this thread)
        return filedialog.askdirectory() or None

    pfd = ctypes.c_void_p()
    try:
        hr = ole32.CoCreateInstance(
            ctypes.byref(CLSID), None, CLSCTX_INPROC,
            ctypes.byref(IID), ctypes.byref(pfd))
        if hr != S_OK or not pfd.value:
            return filedialog.askdirectory() or None

        # Cache vtable pointer before any calls so Release works in finally.
        vp  = ctypes.cast(pfd.value, ctypes.POINTER(ctypes.c_void_p))[0]
        vtb = ctypes.cast(vp, ctypes.POINTER(ctypes.c_void_p))

        # vtable layout (IUnknown + IModalWindow + IFileDialog + IFileOpenDialog):
        #   2=Release  3=Show  9=SetOptions  20=GetResult
        SetOptions = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, ctypes.c_uint32)(vtb[9])
        SetOptions(pfd.value, FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM)

        Show = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, ctypes.wintypes.HWND)(vtb[3])
        hr = Show(pfd.value, hwnd)

        path = None
        if hr == S_OK:
            psi = ctypes.c_void_p()
            GetResult = ctypes.WINFUNCTYPE(
                ctypes.HRESULT, ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p))(vtb[20])
            if GetResult(pfd.value, ctypes.byref(psi)) == S_OK and psi.value:
                # IShellItem vtable:  2=Release  5=GetDisplayName
                sv  = ctypes.cast(psi.value, ctypes.POINTER(ctypes.c_void_p))[0]
                svt = ctypes.cast(sv, ctypes.POINTER(ctypes.c_void_p))
                pszPath = ctypes.c_wchar_p()
                GetDisplayName = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p,
                    ctypes.c_uint32,
                    ctypes.POINTER(ctypes.c_wchar_p))(svt[5])
                if GetDisplayName(psi.value, SIGDN_FILESYSPATH,
                                  ctypes.byref(pszPath)) == S_OK and pszPath.value:
                    path = pszPath.value
                    ole32.CoTaskMemFree(pszPath)
                ctypes.WINFUNCTYPE(
                    ctypes.c_ulong, ctypes.c_void_p)(svt[2])(psi.value)
        return path
    except Exception:
        return filedialog.askdirectory() or None
    finally:
        if pfd.value:
            vp  = ctypes.cast(pfd.value, ctypes.POINTER(ctypes.c_void_p))[0]
            vtb = ctypes.cast(vp, ctypes.POINTER(ctypes.c_void_p))
            ctypes.WINFUNCTYPE(
                ctypes.c_ulong, ctypes.c_void_p)(vtb[2])(pfd.value)
        ole32.CoUninitialize()


class Tk(ctk.CTk, TkinterDnD.DnDWrapper):
    """CTk window with tkinterdnd2 drag & drop support."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)


class RenamerApp:
    def __init__(self, root):
        self.root = root
        root.title("Gerber Renamer")
        root.geometry("780x720")
        root.minsize(680, 600)

        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(4, weight=1)  # preview row expands

        self._build_appbar()
        self._build_dropzone()
        self._build_controls()
        self._build_preview()
        self._build_statusbar()

        self._set_buttons_enabled(False)

    # -- app bar -------------------------------------------------------------
    def _build_appbar(self):
        bar = ctk.CTkFrame(self.root, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 4))
        bar.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(left, text="Gerber Renamer", font=FONT_TITLE,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(left,
                     text="Rename Gerber layers to standard extensions",
                     font=FONT_SUB, text_color=MUTED, anchor="w").pack(anchor="w")

        self.theme_switch = ctk.CTkSegmentedButton(
            bar, values=["Dark", "Light"], command=self._on_theme,
            font=FONT_SMALL)
        self.theme_switch.set("Dark")
        self.theme_switch.grid(row=0, column=1, sticky="e")

    # -- drop zone -----------------------------------------------------------
    def _build_dropzone(self):
        self.drop = ctk.CTkFrame(self.root, corner_radius=18, border_width=2,
                                 border_color=("#c9ccd4", "#3a3f4b"),
                                 fg_color=("#f0f2f6", "#23272f"), height=150)
        self.drop.grid(row=1, column=0, sticky="ew", padx=24, pady=(14, 10))
        self.drop.grid_propagate(False)
        self.drop.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(self.drop, fg_color="transparent")
        inner.grid(row=0, column=0, pady=26)

        self.drop_icon = ctk.CTkLabel(inner, text="⬇", font=("Segoe UI", 34),
                                      text_color=ACCENT)
        self.drop_icon.pack()
        self.drop_title = ctk.CTkLabel(inner, text="Drag & drop a Gerber folder",
                                       font=FONT_BOLD)
        self.drop_title.pack(pady=(2, 0))
        ctk.CTkLabel(inner, text="or browse below", font=FONT_SMALL,
                     text_color=MUTED).pack()

        for w in (self.drop, inner, self.drop_icon, self.drop_title):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self._on_drop)
            w.dnd_bind("<<DropEnter>>", self._on_drag_enter)
            w.dnd_bind("<<DropLeave>>", self._on_drag_leave)

    # -- controls ------------------------------------------------------------
    def _build_controls(self):
        row = ctk.CTkFrame(self.root, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 6))
        row.grid_columnconfigure(0, weight=1)

        self.path_var = ctk.StringVar()
        self.path_entry = ctk.CTkEntry(
            row, textvariable=self.path_var, height=42, corner_radius=10,
            font=FONT, placeholder_text="No folder selected…")
        self.path_entry.grid(row=0, column=0, sticky="ew")
        self.path_var.trace_add("write", lambda *_: self._set_buttons_enabled(
            bool(self.path_var.get().strip())))

        ctk.CTkButton(row, text="Browse", width=96, height=42, corner_radius=10,
                      font=FONT_BOLD, fg_color="transparent", border_width=1,
                      border_color=ACCENT, text_color=ACCENT,
                      hover_color=("#e6edff", "#2a3550"),
                      command=self._browse).grid(row=0, column=1, padx=(10, 0))

        actions = ctk.CTkFrame(self.root, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=24, pady=(8, 6))
        actions.grid_columnconfigure(2, weight=1)

        self.preview_btn = ctk.CTkButton(
            actions, text="Preview", width=120, height=42, corner_radius=10,
            font=FONT_BOLD, fg_color="transparent", border_width=1,
            border_color=("#c9ccd4", "#3a3f4b"), text_color=("#1c1f26", "#e6e7eb"),
            hover_color=("#e9ebf0", "#2a2f3a"), command=self._preview)
        self.preview_btn.grid(row=0, column=0)

        self.rename_btn = ctk.CTkButton(
            actions, text="Rename files", width=150, height=42, corner_radius=10,
            font=FONT_BOLD, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._run_rename)
        self.rename_btn.grid(row=0, column=1, padx=(10, 0))

        self.zip_btn = ctk.CTkButton(
            actions, text="📦  Create ZIP", width=140, height=42, corner_radius=10,
            font=FONT_BOLD, fg_color="#2ecc71", hover_color="#27ae60",
            text_color="#ffffff", command=self._create_zip)
        self.zip_btn.grid(row=0, column=2, padx=(10, 0))
        self.zip_btn.grid_remove()  # hidden until rename is done

        self.open_btn = ctk.CTkButton(
            actions, text="Open folder", width=120, height=42, corner_radius=10,
            font=FONT_BOLD, fg_color="transparent", border_width=1,
            border_color=("#c9ccd4", "#3a3f4b"), text_color=("#1c1f26", "#e6e7eb"),
            hover_color=("#e9ebf0", "#2a2f3a"), command=self._open_folder)
        self.open_btn.grid(row=0, column=3, sticky="e", padx=(10, 0))

    # -- preview -------------------------------------------------------------
    def _build_preview(self):
        card = ctk.CTkFrame(self.root, corner_radius=16)
        card.grid(row=4, column=0, sticky="nsew", padx=24, pady=(8, 6))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(card, fg_color="transparent", height=34)
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
        head.grid_columnconfigure(0, weight=1)
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text="ORIGINAL", font=FONT_SMALL, text_color=MUTED,
                     anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(head, text="NEW NAME", font=FONT_SMALL, text_color=MUTED,
                     anchor="w").grid(row=0, column=1, sticky="w", padx=(30, 0))
        ctk.CTkLabel(head, text="LAYER", font=FONT_SMALL, text_color=MUTED,
                     width=70).grid(row=0, column=2, sticky="e")

        self.rows = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.rows.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.rows.grid_columnconfigure(0, weight=1)

        self._empty = ctk.CTkLabel(
            self.rows, text="Preview will appear here.",
            font=FONT, text_color=MUTED)
        self._empty.pack(pady=30)

    # -- status bar ----------------------------------------------------------
    def _build_statusbar(self):
        bar = ctk.CTkFrame(self.root, fg_color="transparent")
        bar.grid(row=5, column=0, sticky="ew", padx=26, pady=(0, 14))
        self.status_dot = ctk.CTkLabel(bar, text="●", font=("Segoe UI", 12),
                                       text_color=MUTED, width=14)
        self.status_dot.pack(side="left")
        self.status_lbl = ctk.CTkLabel(bar, text="Select a folder to begin.",
                                       font=FONT_SMALL, text_color=MUTED)
        self.status_lbl.pack(side="left", padx=(6, 0))

    # -- drag & drop ---------------------------------------------------------
    def _on_drag_enter(self, _e):
        self.drop.configure(border_color=ACCENT)
        self.drop_title.configure(text="Release to load")

    def _on_drag_leave(self, _e):
        self.drop.configure(border_color=("#c9ccd4", "#3a3f4b"))
        self.drop_title.configure(text="Drag & drop a Gerber folder")

    def _on_drop(self, event):
        self._on_drag_leave(event)
        data = event.data
        if "{" in data and "}" in data:
            path = data.split("}")[0].strip("{ ")
        else:
            path = data.split()[0].strip() if data else ""
        if os.path.isfile(path):
            path = os.path.dirname(path)
        if os.path.isdir(path):
            self.path_var.set(path)
            self._preview()
        else:
            self._status("Could not read the dropped item.", DANGER)

    # -- actions -------------------------------------------------------------
    def _browse(self):
        folder = _win32_pick_folder()
        if folder:
            self.path_var.set(folder)
            self._preview()

    def _preview(self):
        self.zip_btn.grid_remove()  # reset ZIP button when folder changes
        folder = self._valid_folder()
        if not folder:
            return
        try:
            rows = scan_folder(folder)
        except OSError as e:
            self._status(f"Error reading folder: {e}", DANGER)
            return
        self._render_rows(rows)
        n = sum(1 for r in rows if r[3] == "rename")
        if n:
            self._status(f"{n} file(s) ready to rename.", ACCENT)
        elif rows:
            self._status("Nothing to rename — files already renamed or no rule.",
                         MUTED)
        else:
            self._status("No Gerber (.gbr) files found in this folder.", MUTED)

    def _run_rename(self):
        folder = self._valid_folder()
        if not folder:
            return
        try:
            plan = plan_renames(folder)
            if not plan:
                self._render_rows(scan_folder(folder))
                self._status("Nothing to rename — no matching files.", MUTED)
                return
            rename_files_with_condition(folder)
            rows = scan_folder(folder)
        except OSError as e:
            self._status(f"Rename failed: {e}", DANGER)
            return
        self._render_rows(rows)
        self._status(f"✓  Renamed {len(plan)} file(s) successfully.", SUCCESS)
        self.zip_btn.grid()  # show ZIP button after successful rename

    def _create_zip(self):
        folder = self._valid_folder()
        if not folder:
            return
        folder_name = os.path.basename(folder.rstrip("/\\"))
        default_name = f"{folder_name}_gerbers.zip"
        save_path = filedialog.asksaveasfilename(
            title="Save ZIP as",
            initialfile=default_name,
            defaultextension=".zip",
            filetypes=[("ZIP archive", "*.zip")],
        )
        if not save_path:
            return
        try:
            files = [
                f for f in os.listdir(folder)
                if os.path.isfile(os.path.join(folder, f))
            ]
            with zipfile.ZipFile(save_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    zf.write(os.path.join(folder, f), arcname=f)
        except OSError as e:
            self._status(f"ZIP failed: {e}", DANGER)
            return
        self._status(f"✓  ZIP created: {os.path.basename(save_path)}  ({len(files)} files)", SUCCESS)

    def _open_folder(self):
        folder = self._valid_folder()
        if folder:
            os.startfile(folder)

    # -- helpers -------------------------------------------------------------
    def _valid_folder(self):
        folder = self.path_var.get().strip()
        if not folder:
            self._status("Please select a folder first.", DANGER)
            return None
        if not os.path.isdir(folder):
            self._status("That folder does not exist.", DANGER)
            return None
        return folder

    def _render_rows(self, rows):
        for w in self.rows.winfo_children():
            w.destroy()
        if not rows:
            ctk.CTkLabel(self.rows, text="No Gerber (.gbr) files found.",
                         font=FONT, text_color=MUTED).pack(pady=30)
            return

        for old_name, new_name, _layer, status in rows:
            if status == "rename":
                code = new_name.rsplit(".", 1)[-1].lower()
                chip_color, chip_text = LAYER_COLORS.get(code, MUTED), code.upper()
                arrow, arrow_color = "→", ACCENT
                new_text, new_color = new_name, ("#1c1f26", "#e6e7eb")
                old_color = MUTED
            elif status == "done":
                code = old_name.rsplit(".", 1)[-1].lower()
                chip_color, chip_text = LAYER_COLORS.get(code, MUTED), code.upper()
                arrow, arrow_color = "✓", SUCCESS
                new_text, new_color = "already renamed", MUTED
                old_color = SUCCESS
            else:  # skip
                chip_color, chip_text = "#5a5f6a", "—"
                arrow, arrow_color = "—", MUTED
                new_text, new_color = "no matching rule", MUTED
                old_color = MUTED

            row = ctk.CTkFrame(self.rows, corner_radius=10,
                               fg_color=("#f3f4f8", "#272b34"))
            row.pack(fill="x", pady=3, padx=2)
            row.grid_columnconfigure(0, weight=1)
            row.grid_columnconfigure(2, weight=1)

            ctk.CTkLabel(row, text=old_name, font=FONT_MONO, anchor="w",
                         text_color=old_color).grid(row=0, column=0, sticky="w",
                                                     padx=(12, 6), pady=9)
            ctk.CTkLabel(row, text=arrow, font=FONT, text_color=arrow_color).grid(
                row=0, column=1, padx=4)
            ctk.CTkLabel(row, text=new_text, font=FONT_MONO, anchor="w",
                         text_color=new_color).grid(row=0, column=2, sticky="w",
                                                     padx=(6, 6), pady=9)
            ctk.CTkLabel(row, text=chip_text, font=("Segoe UI", 11, "bold"),
                         fg_color=chip_color, text_color="#ffffff",
                         corner_radius=8, width=52, height=24).grid(
                row=0, column=3, padx=(6, 12))

    def _status(self, text, color=MUTED):
        self.status_lbl.configure(text=text, text_color=color)
        self.status_dot.configure(text_color=color)

    def _set_buttons_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for btn in (getattr(self, "preview_btn", None),
                    getattr(self, "rename_btn", None),
                    getattr(self, "open_btn", None)):
            if btn is not None:
                btn.configure(state=state)

    def _on_theme(self, value):
        ctk.set_appearance_mode(value.lower())


def main():
    root = Tk()
    RenamerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
