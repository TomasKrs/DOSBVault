import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import os

from ..utils import restart_program
from ..logger import Logger

class DOSBoxEntryDialog(tb.Toplevel):
    def __init__(self, parent, entry=None):
        super().__init__(parent)
        self.transient(parent)
        self.title("DOSBox Installation")
        self.geometry("500x150")
        self.result = None

        self.name_var = tk.StringVar(value=entry['name'] if entry else "")
        self.path_var = tk.StringVar(value=entry['path'] if entry else "")

        frame = tb.Frame(self, padding=15); frame.pack(fill=tk.BOTH, expand=True); frame.columnconfigure(1, weight=1)
        tb.Label(frame, text="Name:").grid(row=0, column=0, padx=10, pady=5, sticky="w"); tb.Entry(frame, textvariable=self.name_var).grid(row=0, column=1, pady=5, sticky="ew")
        tb.Label(frame, text="Path:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        path_frame = tb.Frame(frame); path_frame.grid(row=1, column=1, sticky="ew"); path_frame.columnconfigure(0, weight=1)
        tb.Entry(path_frame, textvariable=self.path_var).grid(row=0, column=0, sticky="ew"); tb.Button(path_frame, text="...", command=self._browse_path, width=2).grid(row=0, column=1, padx=(5,0))

        btn_frame = tb.Frame(frame); btn_frame.grid(row=2, column=1, pady=10, sticky="e")
        tb.Button(btn_frame, text="OK", command=self._on_ok, bootstyle="success").pack(side=tk.LEFT)
        tb.Button(btn_frame, text="Cancel", command=self.destroy, bootstyle="secondary").pack(side=tk.LEFT, padx=5)

    def _browse_path(self):
        path = filedialog.askopenfilename(title="Select DOSBox Executable", filetypes=[("Executable files", "*.exe"), ("All files", "*.*")])
        if path:
            try: relative_path = os.path.relpath(path, os.getcwd())
            except ValueError: relative_path = path
            self.path_var.set(relative_path)
            
    def _on_ok(self):
        name = self.name_var.get().strip(); path = self.path_var.get().strip()
        if not name or not path: messagebox.showwarning("Missing Information", "Both Name and Path are required.", parent=self); return
        self.result = {"name": name, "path": path}; self.destroy()

class SettingsWindow(tb.Toplevel):
    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.settings = parent_app.settings
        self.title("Settings"); self.geometry("600x750")
        self.transient(parent_app)
        self.grab_set()

        # self.igdb_client_id_var = tk.StringVar(value=self.settings.get("igdb_client_id", ""))
        # self.igdb_client_secret_var = tk.StringVar(value=self.settings.get("igdb_client_secret", ""))

        self._init_ui()

    def _init_ui(self):
        # Save / Cancel Buttons - Packed first to ensure they stay at bottom
        btn_frame = tb.Frame(self, padding=15)
        btn_frame.pack(fill=X, side=BOTTOM)
        tb.Button(btn_frame, text="Save Settings", command=self.save_settings, bootstyle="success").pack(side=RIGHT, padx=5)
        tb.Button(btn_frame, text="Cancel", command=self.destroy, bootstyle="secondary").pack(side=RIGHT)

        notebook = tb.Notebook(self); notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        dosbox_frame = tb.Frame(notebook, padding=15); notebook.add(dosbox_frame, text="DOSBox")
        lf = tb.Labelframe(dosbox_frame, text="Manage DOSBox Installations", padding=10); lf.pack(fill=BOTH, expand=True); lf.columnconfigure(0, weight=1); lf.rowconfigure(1, weight=1)
        scan_frame = tb.Frame(lf); scan_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        tb.Button(scan_frame, text="Scan for New Installations", command=self._scan_dosbox_folder, bootstyle="primary").pack(side=LEFT)
        tree_frame = tb.Frame(lf); tree_frame.grid(row=1, column=0, sticky='nsew'); tree_frame.columnconfigure(0, weight=1); tree_frame.rowconfigure(0, weight=1)
        cols = ["Default", "Name", "Path"]; self.dosbox_tree = tb.Treeview(tree_frame, columns=cols, show="headings", height=8, selectmode="browse")
        self.dosbox_tree.grid(row=0, column=0, sticky="nsew")
        for col in cols: self.dosbox_tree.heading(col, text=col)
        self.dosbox_tree.column("Default", width=60, anchor="center", stretch=False); self.dosbox_tree.column("Name", width=150, stretch=False); self.dosbox_tree.column("Path", width=400, stretch=True)
        btn_frame_dos = tb.Frame(lf); btn_frame_dos.grid(row=2, column=0, sticky="ew", pady=(10,0))
        tb.Button(btn_frame_dos, text="Add Manually", command=self._add_dosbox, bootstyle="success-outline").pack(side=LEFT, padx=5)
        tb.Button(btn_frame_dos, text="Edit", command=self._edit_dosbox, bootstyle="info-outline").pack(side=LEFT)
        tb.Button(btn_frame_dos, text="Remove", command=self._remove_dosbox, bootstyle="danger-outline").pack(side=LEFT, padx=5)
        tb.Button(btn_frame_dos, text="Set as Default", command=self._set_default_dosbox, bootstyle="secondary").pack(side=RIGHT)
        
        self._build_columns_tab(notebook)
        
        theme_frame = tb.Frame(notebook, padding=15); notebook.add(theme_frame, text="Appearance")
        
        # Theme Selection
        tb.Label(theme_frame, text="Theme:").pack(anchor="w", padx=10, pady=(0,5))
        
        # Filter themes: only darkly, litera, and those in themes/ folder
        all_themes = self.parent_app.style.theme_names()
        allowed_themes = {"darkly", "litera"}
        
        themes_dir = os.path.join(os.getcwd(), "themes")
        if os.path.exists(themes_dir):
            for f in os.listdir(themes_dir):
                if f.endswith(".json"):
                    name = os.path.splitext(f)[0]
                    allowed_themes.add(name)
        
        # Also include current theme if it's somehow not in the list
        current_theme = self.settings.get("theme", "darkly")
        allowed_themes.add(current_theme)
        
        display_themes = sorted([t for t in all_themes if t in allowed_themes])
        
        self.theme_combo = tb.Combobox(theme_frame, values=display_themes, state="readonly"); self.theme_combo.pack(fill=X, padx=10, pady=(0,15))
        self.theme_combo.set(current_theme)
        
        # List Appearance
        lf_list = tb.Labelframe(theme_frame, text="Game List Appearance", padding=10)
        lf_list.pack(fill=X, padx=10, pady=10)
        
        tb.Label(lf_list, text="Row Height (px):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.row_height_var = tk.IntVar(value=self.settings.get("row_height", 45))
        tb.Spinbox(lf_list, from_=20, to=100, textvariable=self.row_height_var, width=10).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        tb.Label(lf_list, text="Font Size (pt):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.font_size_var = tk.IntVar(value=self.settings.get("font_size", 11))
        tb.Spinbox(lf_list, from_=8, to=24, textvariable=self.font_size_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # Preview Settings
        lf_preview = tb.Labelframe(theme_frame, text="Preview Settings", padding=10)
        lf_preview.pack(fill=X, padx=10, pady=10)
        
        tb.Label(lf_preview, text="Thumbnail Size:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.thumb_size_var = tk.StringVar(value=self.settings.get("thumbnail_size", "Medium"))
        tb.Combobox(lf_preview, textvariable=self.thumb_size_var, values=["Small", "Medium", "Large"], state="readonly", width=15).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        tb.Label(lf_preview, text="Slideshow Interval (s):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.slide_interval_var = tk.IntVar(value=self.settings.get("slideshow_interval", 3))
        tb.Spinbox(lf_preview, from_=3, to=60, textvariable=self.slide_interval_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        self.slideshow_enabled_var = tk.BooleanVar(value=self.settings.get("slideshow_enabled", True))
        tb.Checkbutton(lf_preview, text="Enable Slideshow (Cycle images)", variable=self.slideshow_enabled_var, bootstyle="round-toggle").grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        
        self.hover_preview_var = tk.BooleanVar(value=self.settings.get("hover_preview", True))
        tb.Checkbutton(lf_preview, text="Show Image Preview on Hover", variable=self.hover_preview_var, bootstyle="round-toggle").grid(row=3, column=0, columnspan=2, padx=5, pady=10, sticky="w")

        # Window Behavior
        lf_window = tb.Labelframe(theme_frame, text="Window Behavior", padding=10)
        lf_window.pack(fill=X, padx=10, pady=10)
        
        self.minimize_on_launch_var = tk.BooleanVar(value=self.settings.get("minimize_on_launch", False))
        tb.Checkbutton(lf_window, text="Minimize App on Game Launch", variable=self.minimize_on_launch_var, bootstyle="round-toggle").pack(anchor="w", padx=5, pady=5)

        # Logging Tab
        log_frame = tb.Frame(notebook, padding=15); notebook.add(log_frame, text="Logging")
        self.logging_var = tk.BooleanVar(value=self.settings.get("enable_logging", False))
        tb.Checkbutton(log_frame, text="Enable Logging to File", variable=self.logging_var, bootstyle="round-toggle").pack(anchor="w", pady=10)
        
        # Log Categories
        cat_frame = tb.Labelframe(log_frame, text="Log Categories", padding=10)
        cat_frame.pack(fill=X, pady=10)
        
        self.log_cats = {
            "rename": "Rename Game",
            "wizard": "Config Wizard Usage",
            "launch": "Game Launch",
            "import": "Import Game",
            "config": "Configuration Edit"
        }
        self.log_cat_vars = {}
        
        for key, label in self.log_cats.items():
            var = tk.BooleanVar(value=self.settings.get(f"log_{key}", True))
            tb.Checkbutton(cat_frame, text=label, variable=var).pack(anchor="w")
            self.log_cat_vars[key] = var

        tb.Label(log_frame, text="Logs are saved in the 'log' folder with date-based filenames.", bootstyle="secondary").pack(anchor="w", pady=(0, 20))
        tb.Button(log_frame, text="Clear All Logs", command=self._clear_logs, bootstyle="danger-outline").pack(anchor="w")
        
        self._load_dosbox_list()

    def _clear_logs(self):
        if messagebox.askyesno("Clear Logs", "Are you sure you want to delete all log files?", parent=self):
            Logger(self.settings).clear_logs()
            messagebox.showinfo("Success", "Logs cleared.", parent=self)

    def _build_columns_tab(self, notebook):
        columns_frame = tb.Frame(notebook, padding=15); notebook.add(columns_frame, text="Columns")
        lf = tb.Labelframe(columns_frame, text="Visible Columns in Game Library", padding=10); lf.pack(fill=BOTH, expand=True)
        
        all_columns = self.parent_app.library_panel.columns
        hidden_columns = self.settings.get('hidden_columns', [])
        self.column_vars = {}

        for i, col_id in enumerate(all_columns):
            if col_id == 'name': continue # Name column is always visible
            var = tk.BooleanVar(value=(col_id not in hidden_columns))
            col_text = col_id.replace("_", " ").title()
            cb = tb.Checkbutton(lf, text=col_text, variable=var, bootstyle="primary")
            cb.grid(row=i // 3, column=i % 3, sticky='w', padx=10, pady=5)
            self.column_vars[col_id] = var

    def _create_dir_entry(self, parent, label_text, var):
        frame = tb.Labelframe(parent, text=label_text, padding=10)
        frame.pack(fill=X, expand=True, pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        entry = tb.Entry(frame, textvariable=var); entry.grid(row=0, column=0, sticky="ew")
        button = tb.Button(frame, text="Browse...", command=lambda v=var: self._browse_directory(v), bootstyle="secondary-outline"); button.grid(row=0, column=1, padx=(10,0))

    def _browse_directory(self, var):
        path = filedialog.askdirectory(title="Select Directory", parent=self)
        if path:
            try: relative_path = os.path.relpath(path, os.getcwd())
            except ValueError: relative_path = path
            var.set(relative_path)

    def _load_dosbox_list(self):
        for item in self.dosbox_tree.get_children(): self.dosbox_tree.delete(item)
        installations = self.settings.get("dosbox_installations", [])
        for i, item in enumerate(installations): self.dosbox_tree.insert("", "end", iid=i, values=("✓" if item.get('default') else "", item['name'], item['path']))

    def _add_dosbox(self):
        dialog = DOSBoxEntryDialog(self); self.wait_window(dialog)
        if dialog.result:
            installations = self.settings.get("dosbox_installations", [])
            if not installations: dialog.result['default'] = True
            installations.append(dialog.result); self.settings.set("dosbox_installations", installations); self._load_dosbox_list()

    def _edit_dosbox(self):
        if not (selected := self.dosbox_tree.selection()): return
        index = int(selected[0]); installations = self.settings.get("dosbox_installations", []); entry_to_edit = installations[index].copy()
        dialog = DOSBoxEntryDialog(self, entry_to_edit); self.wait_window(dialog)
        if dialog.result:
            installations[index]['name'] = dialog.result['name']; installations[index]['path'] = dialog.result['path']
            self.settings.set("dosbox_installations", installations); self._load_dosbox_list()

    def _remove_dosbox(self):
        if not (selected := self.dosbox_tree.selection()): return
        index = int(selected[0]); installations = self.settings.get("dosbox_installations", [])
        if installations[index].get('default') and len(installations) > 1:
            messagebox.showwarning("Cannot Remove", "Cannot remove the default DOSBox installation. Please set another as default first.", parent=self); return
        if messagebox.askyesno("Confirm", f"Are you sure you want to remove '{installations[index]['name']}'?", parent=self):
            installations.pop(index); self.settings.set("dosbox_installations", installations); self._load_dosbox_list()

    def _set_default_dosbox(self):
        if not (selected := self.dosbox_tree.selection()): return
        index = int(selected[0]); installations = self.settings.get("dosbox_installations", [])
        for i, item in enumerate(installations): item['default'] = (i == index)
        self.settings.set("dosbox_installations", installations); self._load_dosbox_list()
    
    def _perform_scan(self, search_path):
        found = []; self.parent_app.config(cursor="wait"); self.update()
        abs_search_path = os.path.abspath(search_path)
        if os.path.isdir(abs_search_path):
            for root, dirs, files in os.walk(abs_search_path):
                found_in_dir = False
                for file in files:
                    lower_file = file.lower()
                    if "dosbox" in lower_file and lower_file.endswith(".exe"):
                        dir_name = os.path.basename(root); full_path = os.path.join(root, file)
                        try: relative_path = os.path.relpath(full_path, os.getcwd())
                        except ValueError: relative_path = full_path
                        found.append({"name": dir_name, "path": relative_path}); found_in_dir = True
                if found_in_dir: dirs[:] = []
        self.parent_app.config(cursor=""); return found
    
    def _process_scan_results(self, found_installs):
        if not found_installs:
            messagebox.showinfo("Scan Complete", "No new DOSBox installations found in the specified directory.", parent=self); return
        current_paths = [inst['path'] for inst in self.settings.get("dosbox_installations", [])]
        new_installs = [f for f in found_installs if f['path'] not in current_paths]
        if not new_installs:
            messagebox.showinfo("Scan Complete", "All found instances are already in your list.", parent=self); return
        add_dialog = tb.Toplevel(self); add_dialog.title("Found DOSBox Installations"); add_dialog.geometry("600x400"); add_dialog.transient(self)
        add_dialog.grab_set() # Ensure this dialog gets focus and blocks interaction with settings window
        tb.Label(add_dialog, text="Select which DOSBox installations to add:", padding=10).pack()
        vars = [ (tk.BooleanVar(value=True), item) for item in new_installs ]
        for var, item in vars: tb.Checkbutton(add_dialog, text=f"{item['name']} ({item['path']})", variable=var).pack(anchor='w', padx=10)
        def on_add_selected():
            installations = self.settings.get("dosbox_installations", []); is_first_batch = not installations
            for var, item in vars:
                if var.get():
                    if is_first_batch: item['default'] = True; is_first_batch = False
                    installations.append(item)
            self.settings.set("dosbox_installations", installations); self._load_dosbox_list(); add_dialog.destroy()
        btn_container = tb.Frame(add_dialog, padding=10); btn_container.pack(fill=X, side=BOTTOM)
        tb.Button(btn_container, text="Add Selected", command=on_add_selected, bootstyle='success').pack(side=RIGHT)
        tb.Button(btn_container, text="Cancel", command=add_dialog.destroy, bootstyle='secondary').pack(side=RIGHT, padx=5)

    def _scan_dosbox_folder(self):
        dosbox_dir = self.settings.get("dosbox_root_dir", "DOSBox")
        if not dosbox_dir: messagebox.showwarning("Directory Not Set", "DOSBox directory is not configured.", parent=self); return
        if not os.path.isdir(dosbox_dir): messagebox.showerror("Invalid Path", f"The specified DOSBox directory does not exist:\n{os.path.abspath(dosbox_dir)}", parent=self); return
        found = self._perform_scan(dosbox_dir); self._process_scan_results(found)

    def save_settings(self):
        self.settings.set("enable_logging", self.logging_var.get())
        
        for key, var in self.log_cat_vars.items():
            self.settings.set(f"log_{key}", var.get())
            
        Logger(self.settings).refresh_settings()
        
        # Save Appearance
        self.settings.set("row_height", self.row_height_var.get())
        self.settings.set("font_size", self.font_size_var.get())
        
        # Save Preview Settings
        self.settings.set("thumbnail_size", self.thumb_size_var.get())
        self.settings.set("slideshow_interval", max(3, self.slide_interval_var.get()))
        self.settings.set("slideshow_enabled", self.slideshow_enabled_var.get())
        self.settings.set("hover_preview", self.hover_preview_var.get())
        self.settings.set("minimize_on_launch", self.minimize_on_launch_var.get())
        
        hidden_columns = [col_id for col_id, var in self.column_vars.items() if not var.get()]
        self.settings.set('hidden_columns', hidden_columns)
        
        # Re-apply settings to library panel
        self.parent_app.library_panel.apply_appearance_settings()
        self.parent_app.library_panel.apply_user_column_settings()
        
        # Explicitly update slideshow state
        if self.slideshow_enabled_var.get():
            self.parent_app.library_panel._start_image_cycling()
        else:
            self.parent_app.library_panel._stop_image_cycling()
            # Force update to static image if in grid mode
            if self.parent_app.library_panel.view_mode == "grid":
                self.parent_app.library_panel.populate_grid()

        self.parent_app.refresh_library()

        if self.theme_combo.get() != self.settings.get("theme"):
            self.settings.set("theme", self.theme_combo.get())
            if messagebox.askyesno("Restart Required", "A theme change requires a restart. Restart now?"):
                self.destroy(); restart_program()
                return
        self.destroy()