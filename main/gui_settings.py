import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import os
import sys
import subprocess
import importlib.util
import logging

from constants import BASE_DIR

logger = logging.getLogger(__name__)

class SettingsWindow(tb.Toplevel):
    def __init__(self, parent, settings, restart_callback, refresh_callback):
        # Apply the current theme to the new window
        theme = settings.get("theme", "darkly")
        
        # We need to get the root window to create the Toplevel with the same theme context
        super().__init__(title="Settings", themename=theme)
        self.geometry("600x650")

        self.parent = parent
        self.settings = settings
        self.restart_callback = restart_callback
        self.refresh_callback = refresh_callback
        
        # Load custom themes for this window as well
        self.load_custom_themes()

        self._build_ui()

    def load_custom_themes(self):
        """Loads .json themes from the 'themes' folder."""
        themes_dir = os.path.join(BASE_DIR, "themes")
        if os.path.exists(themes_dir):
            for f in os.listdir(themes_dir):
                if f.endswith(".json"):
                    try:
                        full_path = os.path.join(themes_dir, f)
                        self.style.load_user_themes(full_path)
                        logger.info("Loaded custom theme: %s", f)
                    except Exception:
                        logger.exception("Failed to load theme %s", f)

    def _build_ui(self):
        # --- VARIABLES ---
        v_root = tk.StringVar(value=self.settings.get("root_dir"))
        v_zip = tk.StringVar(value=self.settings.get("zip_dir"))
        v_exe = tk.StringVar(value=self.settings.get("dosbox_exe"))
        v_conf = tk.StringVar(value=self.settings.get("global_conf"))
        v_capture = tk.StringVar(value=self.settings.get("capture_dir"))
        v_theme = tk.StringVar(value=self.settings.get("theme"))

        # --- TABS ---
        tabs = tb.Notebook(self)
        tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tab_gen = tb.Frame(tabs)
        tab_app = tb.Frame(tabs)
        tabs.add(tab_gen, text="System & Paths")
        tabs.add(tab_app, text="Appearance & Themes")
        
        # --- TAB 1: SYSTEM ---
        def browse_path(var, is_file=False):
            if is_file: p = filedialog.askopenfilename(filetypes=[("Executable/Config", "*.*")], parent=self)
            else: p = filedialog.askdirectory(parent=self)
            if p: var.set(self.settings._make_relative(p))
            
        pad = 5
        def create_row(parent, label, var, cmd=None, placeholder=None):
            f = tb.Frame(parent); f.pack(fill=tk.X, padx=10, pady=pad)
            tb.Label(f, text=label, bootstyle="inverse-dark").pack(anchor="w")
            row_inner = tb.Frame(f); row_inner.pack(fill=tk.X, expand=True)
            ent = tb.Entry(row_inner, textvariable=var)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
            if cmd: tb.Button(row_inner, text="...").pack(side=tk.RIGHT, padx=(5,0))
            if placeholder: tb.Label(f, text=placeholder, font=("Segoe UI", 8), bootstyle="secondary").pack(anchor="w")

        create_row(tab_gen, "Installed Games (Root Dir):", v_root, lambda: browse_path(v_root, False))
        create_row(tab_gen, "Zipped Games (Source Dir):", v_zip, lambda: browse_path(v_zip, False))
        create_row(tab_gen, "DOSBox Executable (.exe):", v_exe, lambda: browse_path(v_exe, True))
        create_row(tab_gen, "Global Template Config (.conf):", v_conf, lambda: browse_path(v_conf, True))
        create_row(tab_gen, "DOSBox Capture Folder Name/Path:", v_capture, lambda: browse_path(v_capture, False), "Default: 'capture'")

        lbl_status = tb.Label(tab_gen, text="", font=("Segoe UI", 9, "bold"), wraplength=530, justify="center")
        lbl_status.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        def check_portability(*args):
            issues = []
            def is_path_portable(val):
                if not val: return True
                if not os.path.isabs(val): return True
                if val.startswith(BASE_DIR): return True
                return False
            if not is_path_portable(v_root.get()): issues.append("Root Dir")
            if not is_path_portable(v_zip.get()): issues.append("Zipped Games")
            if not is_path_portable(v_exe.get()): issues.append("DOSBox EXE")
            if issues: lbl_status.config(text=f"NOT PORTABLE: {', '.join(issues)}", bootstyle="danger")
            else: lbl_status.config(text="PORTABLE MODE ACTIVE", bootstyle="success")

        try:
            v_root.trace_add("write", lambda *a: check_portability())
            v_exe.trace_add("write", lambda *a: check_portability())
        except Exception:
            v_root.trace("w", lambda *a: check_portability())
            v_exe.trace("w", lambda *a: check_portability())
        check_portability()

        # --- TAB 2: APPEARANCE ---
        f_thm = tb.Frame(tab_app); f_thm.pack(fill=tk.X, padx=10, pady=15)
        tb.Label(f_thm, text="Select Visual Theme:", bootstyle="inverse-dark").pack(anchor="w")
        
        all_themes = sorted(self.style.theme_names())
        cb_thm = tb.Combobox(f_thm, values=all_themes, textvariable=v_theme, state="readonly")
        cb_thm.pack(fill=tk.X, pady=(5, 10))
        
        def open_themes_folder():
            themes_dir = os.path.join(BASE_DIR, "themes")
            if not os.path.exists(themes_dir): os.makedirs(themes_dir)
            try:
                if os.name == 'nt': os.startfile(themes_dir)
                else: subprocess.call(['xdg-open', themes_dir])
            except Exception:
                logger.exception("Failed to open themes folder %s", themes_dir)
            
        tb.Button(tab_app, text="📂 Open Themes Folder", command=open_themes_folder, bootstyle="info-outline").pack(fill=tk.X, padx=10)
        
        # --- THEME CREATOR LOGIC ---
        creator_installed = importlib.util.find_spec("ttkcreator") is not None
        
        f_creator = tb.Frame(tab_app)
        f_creator.pack(fill=tk.X, padx=10, pady=20)
        tb.Label(f_creator, text="Theme Creator Tool:", bootstyle="inverse-dark").pack(anchor="w")
        
        def run_installer():
            try:
                btn_install.configure(state="disabled", text="Installing... (Please wait)")
                self.update()
                subprocess.check_call([sys.executable, "-m", "pip", "install", "ttkcreator"])
                messagebox.showinfo("Success", "Theme Creator installed successfully!\\nYou may launch it now.", parent=self)
                btn_install.pack_forget()
                btn_launch.pack(fill=tk.X, pady=5)
            except Exception as e:
                logger.exception("Failed to install ttkcreator")
                messagebox.showerror("Error", f"Installation failed: {e}", parent=self)
                btn_install.configure(state="normal", text="📥 Install Theme Creator")

        def run_creator():
            try:
                subprocess.Popen([sys.executable, "-m", "ttkcreator"])
            except Exception:
                logger.exception("Failed to launch ttkcreator")
                messagebox.showerror("Error", "Failed to launch Theme Creator", parent=self)

        btn_install = tb.Button(f_creator, text="📥 Install Theme Creator (pip install ttkcreator)", command=run_installer, bootstyle="warning-outline")
        btn_launch = tb.Button(f_creator, text="🎨 Launch Theme Creator", command=run_creator, bootstyle="success-outline")

        if creator_installed:
            btn_launch.pack(fill=tk.X, pady=5)
        else:
            btn_install.pack(fill=tk.X, pady=5)
        
        info_txt = ("\\nCreate a theme using the tool above, save the .json file\\n"
                    "into the 'themes' folder (Open Themes Folder), and restart.")
        tb.Label(tab_app, text=info_txt, justify=tk.LEFT, bootstyle="secondary").pack(padx=10, anchor="w")

        # --- SAVE ---
        def save():
            old_theme = self.settings.get("theme")
            self.settings.set("root_dir", v_root.get())
            self.settings.set("zip_dir", v_zip.get())
            self.settings.set("dosbox_exe", v_exe.get())
            self.settings.set("global_conf", v_conf.get())
            self.settings.set("capture_dir", v_capture.get())
            self.settings.set("theme", v_theme.get())
            self.settings.save()
            
            if old_theme != v_theme.get():
                self.destroy()
                self.restart_callback()
            else:
                self.refresh_callback()
                self.destroy()

        tb.Button(self, text="Save Settings & Close", command=save, bootstyle="success").pack(pady=10, fill=tk.X, padx=10)