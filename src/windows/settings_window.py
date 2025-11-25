import tkinter as tk
from tkinter import filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import os
import sys
import subprocess
import importlib.util

# Imports from our modules
from constants import BASE_DIR

class SettingsWindow(tb.Toplevel):
    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.settings = parent_app.settings
        
        self.title("Settings")
        self.geometry("600x650")

        # --- VARIABLES ---
        self.v_root = tk.StringVar(value=self.settings.get("root_dir"))
        self.v_zip = tk.StringVar(value=self.settings.get("zip_dir"))
        self.v_exe = tk.StringVar(value=self.settings.get("dosbox_exe"))
        self.v_conf = tk.StringVar(value=self.settings.get("global_conf"))
        self.v_capture = tk.StringVar(value=self.settings.get("capture_dir"))
        self.v_theme = tk.StringVar(value=self.settings.get("theme"))

        self._init_ui()
        self._check_portability()

    def _init_ui(self):
        # --- TABS ---
        tabs = tb.Notebook(self)
        tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tab_gen = tb.Frame(tabs)
        tab_app = tb.Frame(tabs)
        tabs.add(tab_gen, text="System & Paths")
        tabs.add(tab_app, text="Appearance & Themes")
        
        # --- TAB 1: SYSTEM ---
        self._build_system_tab(tab_gen)
        
        # --- TAB 2: APPEARANCE ---
        self._build_appearance_tab(tab_app)
        
        # --- SAVE ---
        tb.Button(self, text="Save Settings & Restart if needed", command=self._save, bootstyle="success").pack(pady=10, fill=tk.X, padx=10)

    def _build_system_tab(self, parent):
        self._create_path_row(parent, "Installed Games (Root Dir):", self.v_root, is_file=False)
        self._create_path_row(parent, "Zipped Games (Source Dir):", self.v_zip, is_file=False)
        self._create_path_row(parent, "DOSBox Executable (.exe):", self.v_exe, is_file=True)
        self._create_path_row(parent, "Global Template Config (.conf):", self.v_conf, is_file=True)
        self._create_path_row(parent, "DOSBox Capture Folder Name/Path:", self.v_capture, is_file=False, placeholder="Default: 'capture'")

        self.lbl_status = tb.Label(parent, text="", font=("Segoe UI", 9, "bold"), wraplength=530, justify="center")
        self.lbl_status.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        self.v_root.trace("w", self._check_portability)
        self.v_exe.trace("w", self._check_portability)

    def _build_appearance_tab(self, parent):
        # --- THEME SELECTOR ---
        f_thm = tb.Frame(parent)
        f_thm.pack(fill=tk.X, padx=10, pady=15)
        tb.Label(f_thm, text="Select Visual Theme:", bootstyle="inverse-dark").pack(anchor="w")
        
        all_themes = sorted(self.parent_app.style.theme_names())
        cb_thm = tb.Combobox(f_thm, values=all_themes, textvariable=self.v_theme, state="readonly")
        cb_thm.pack(fill=tk.X, pady=(5, 10))
        
        tb.Button(parent, text="📂 Open Themes Folder", command=self._open_themes_folder, bootstyle="info-outline").pack(fill=tk.X, padx=10)
        
        # --- THEME CREATOR ---
        self._build_theme_creator_section(parent)
        
        info_txt = ("\nCreate a theme using the tool above, save the .json file\n"
                    "into the 'themes' folder (Open Themes Folder), and restart.")
        tb.Label(parent, text=info_txt, justify=tk.LEFT, bootstyle="secondary").pack(padx=10, anchor="w")

    def _build_theme_creator_section(self, parent):
        creator_installed = importlib.util.find_spec("ttkcreator") is not None
        
        f_creator = tb.Frame(parent)
        f_creator.pack(fill=tk.X, padx=10, pady=20)
        tb.Label(f_creator, text="Theme Creator Tool:", bootstyle="inverse-dark").pack(anchor="w")
        
        btn_install = tb.Button(f_creator, text="📥 Install Theme Creator (pip install ttkcreator)", command=lambda: self._run_installer(btn_install, btn_launch), bootstyle="warning-outline")
        btn_launch = tb.Button(f_creator, text="🎨 Launch Theme Creator", command=self._run_creator, bootstyle="success-outline")

        if creator_installed:
            btn_launch.pack(fill=tk.X, pady=5)
        else:
            btn_install.pack(fill=tk.X, pady=5)

    def _browse_path(self, var, is_file=False):
        if is_file:
            p = filedialog.askopenfilename(filetypes=[("Executable/Config", "*.*")], parent=self)
        else:
            p = filedialog.askdirectory(parent=self)
        if p:
            var.set(self.settings._make_relative(p))
            
    def _create_path_row(self, parent, label, var, is_file, placeholder=None):
        f = tb.Frame(parent)
        f.pack(fill=tk.X, padx=10, pady=5)
        tb.Label(f, text=label, bootstyle="inverse-dark").pack(anchor="w")
        row_inner = tb.Frame(f)
        row_inner.pack(fill=tk.X, expand=True)
        ent = tb.Entry(row_inner, textvariable=var)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tb.Button(row_inner, text="...", command=lambda: self._browse_path(var, is_file), bootstyle="outline").pack(side=tk.RIGHT, padx=(5,0))
        if placeholder:
            tb.Label(f, text=placeholder, font=("Segoe UI", 8), bootstyle="secondary").pack(anchor="w")

    def _check_portability(self, *args):
        issues = []
        def is_path_portable(val):
            if not val: return True
            if not os.path.isabs(val): return True
            if val.startswith(BASE_DIR): return True
            return False
        
        if not is_path_portable(self.v_root.get()): issues.append("Root Dir")
        if not is_path_portable(self.v_zip.get()): issues.append("Zipped Games")
        if not is_path_portable(self.v_exe.get()): issues.append("DOSBox EXE")
        
        if issues:
            self.lbl_status.config(text=f"NOT PORTABLE: {', '.join(issues)}", bootstyle="danger")
        else:
            self.lbl_status.config(text="PORTABLE MODE ACTIVE", bootstyle="success")

    def _open_themes_folder(self):
        themes_dir = os.path.join(BASE_DIR, "themes")
        if not os.path.exists(themes_dir):
            os.makedirs(themes_dir)
        if os.name == 'nt':
            os.startfile(themes_dir)
        else:
            subprocess.call(['xdg-open', themes_dir])

    def _run_installer(self, btn_install, btn_launch):
        try:
            btn_install.configure(state="disabled", text="Installing... (Please wait)")
            self.update()
            subprocess.check_call([sys.executable, "-m", "pip", "install", "ttkcreator"])
            tk.messagebox.showinfo("Success", "Theme Creator installed successfully!\nYou may launch it now.", parent=self)
            btn_install.pack_forget()
            btn_launch.pack(fill=tk.X, pady=5)
        except Exception as e:
            tk.messagebox.showerror("Error", f"Installation failed: {e}", parent=self)
            btn_install.configure(state="normal", text="📥 Install Theme Creator")

    def _run_creator(self):
        try:
            subprocess.Popen([sys.executable, "-m", "ttkcreator"])
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to launch: {e}", parent=self)

    def _save(self):
        old_theme = self.settings.get("theme")
        self.settings.set("root_dir", self.v_root.get())
        self.settings.set("zip_dir", self.v_zip.get())
        self.settings.set("dosbox_exe", self.v_exe.get())
        self.settings.set("global_conf", self.v_conf.get())
        self.settings.set("capture_dir", self.v_capture.get())
        self.settings.set("theme", self.v_theme.get())
        self.settings.save()
        
        if old_theme != self.v_theme.get():
            self.destroy()
            self.parent_app.restart_program()
        else:
            self.parent_app.refresh_library()
            self.destroy()