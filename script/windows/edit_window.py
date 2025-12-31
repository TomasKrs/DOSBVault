import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
from ttkbootstrap.tooltip import ToolTip
import os
import webbrowser
import json
from urllib.parse import quote_plus, urlparse, parse_qs
import urllib.request
import re

from .. import constants
from ..utils import truncate_text
from ..components.igdb_client import IGDBClient
from datetime import datetime

class GameSelectionDialog(tb.Toplevel):
    def __init__(self, parent, games, game_name=""):
        super().__init__(parent)
        self.transient(parent)
        self.title("Select Game")
        self.geometry("600x450")
        self.result = None
        
        if game_name:
            tb.Label(self, text=f"Select match for: {game_name}", bootstyle="warning", font="-weight bold").pack(pady=(10, 0))
        
        tb.Label(self, text="Multiple games found. Please select one:", bootstyle="info").pack(pady=10)
        
        columns = ("name", "year", "platforms")
        self.tree = tb.Treeview(self, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("name", text="Name")
        self.tree.heading("year", text="Year")
        self.tree.heading("platforms", text="Platforms")
        self.tree.column("name", width=250)
        self.tree.column("year", width=80)
        self.tree.column("platforms", width=200)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        for i, game in enumerate(games):
            year = ""
            if 'first_release_date' in game:
                year = datetime.fromtimestamp(game['first_release_date']).year
            platforms = ", ".join([p['name'] for p in game.get('platforms', [])])
            self.tree.insert("", "end", values=(game['name'], year, platforms), iid=str(i))
            
        self.games = games
        
        btn_frame = tb.Frame(self)
        btn_frame.pack(pady=10)
        tb.Button(btn_frame, text="Select", command=self.on_select, bootstyle="success").pack(side=tk.LEFT, padx=5)
        tb.Button(btn_frame, text="Cancel", command=self.destroy, bootstyle="secondary").pack(side=tk.LEFT, padx=5)
        
        self.tree.bind("<Double-1>", lambda e: self.on_select())
        
        # Center window
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"+{x}+{y}")
        self.lift()
        self.focus_force()
        self.grab_set()

    def on_select(self):
        selected = self.tree.selection()
        if not selected: return
        idx = int(selected[0])
        self.result = self.games[idx]
        self.destroy()


class VideoLinkDialog(tb.Toplevel):
    def __init__(self, parent, video_info=None, initial_url="", **kwargs):
        super().__init__(**kwargs)
        self.transient(parent); self.geometry("500x150"); self.result = None; self.title_var = tk.StringVar(); self.url_var = tk.StringVar()
        if video_info: self.title_var.set(video_info.get("title", "")); self.url_var.set(video_info.get("url", ""))
        elif initial_url: self.url_var.set(initial_url)
        frame = tb.Frame(self, padding=15); frame.pack(fill=tk.BOTH, expand=True); frame.columnconfigure(1, weight=1)
        tb.Label(frame, text="Video Title:").grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w"); title_entry = tb.Entry(frame, textvariable=self.title_var); title_entry.grid(row=0, column=1, pady=5, sticky="ew")
        tb.Label(frame, text="YouTube URL:").grid(row=1, column=0, padx=(0, 10), pady=5, sticky="w"); url_entry = tb.Entry(frame, textvariable=self.url_var); url_entry.grid(row=1, column=1, pady=5, sticky="ew")
        if initial_url: title_entry.focus_set()
        else: url_entry.focus_set()
        btn_frame = tb.Frame(frame); btn_frame.grid(row=2, column=0, columnspan=2, pady=10, sticky="e"); tb.Button(btn_frame, text="OK", command=self.on_ok, bootstyle="success").pack(side=tk.LEFT); tb.Button(btn_frame, text="Cancel", command=self.destroy, bootstyle="secondary").pack(side=tk.LEFT, padx=5)
        self.bind("<Return>", lambda event: self.on_ok()); self.bind("<Escape>", lambda event: self.destroy())
    def on_ok(self):
        if not self.url_var.get().strip(): messagebox.showwarning("Missing URL", "The URL field cannot be empty.", parent=self); return
        self.result = {"title": self.title_var.get().strip(), "url": self.url_var.get().strip()}; self.destroy()

class AddMountDialog(tb.Toplevel):
    def __init__(self, parent, initial_drive="D", initial_data=None):
        super().__init__(parent)
        self.title("Add/Edit Mount Point")
        self.geometry("500x300")
        self.result = None
        
        if initial_data:
            self.drive_var = tk.StringVar(value=initial_data.get("drive", "D"))
            self.type_var = tk.StringVar(value=initial_data.get("type", "dir"))
            self.path_var = tk.StringVar(value=initial_data.get("path", ""))
            self.label_var = tk.StringVar(value=initial_data.get("label", ""))
            self.as_var = tk.StringVar(value=initial_data.get("as", "iso"))
        else:
            self.drive_var = tk.StringVar(value=initial_drive)
            self.type_var = tk.StringVar(value="dir") # dir or image
            self.path_var = tk.StringVar()
            self.label_var = tk.StringVar()
            self.as_var = tk.StringVar(value="iso") # iso or fat for images
        
        self._init_ui()

    def _init_ui(self):
        main = tb.Frame(self, padding=10)
        main.pack(fill=BOTH, expand=True)
        
        # Drive Letter
        f_drive = tb.Frame(main)
        f_drive.pack(fill=X, pady=5)
        tb.Label(f_drive, text="Drive Letter:").pack(side=LEFT)
        tb.Combobox(f_drive, textvariable=self.drive_var, values=["A", "B", "C", "D", "E", "F", "G"], width=5, state="readonly").pack(side=LEFT, padx=10)
        
        # Mount Directory Section
        f_dir = tb.Labelframe(main, text="Mount Directory", padding=10)
        f_dir.pack(fill=X, pady=10)
        
        tb.Radiobutton(f_dir, text="Mount Directory", variable=self.type_var, value="dir").grid(row=0, column=0, sticky="w")
        
        self.ent_dir = tb.Entry(f_dir, textvariable=self.path_var)
        self.ent_dir.grid(row=0, column=1, sticky="ew", padx=5)
        tb.Button(f_dir, text="Browse..", command=self._browse_dir).grid(row=0, column=2)
        
        tb.Label(f_dir, text="Label:").grid(row=1, column=0, sticky="w", pady=5)
        tb.Entry(f_dir, textvariable=self.label_var).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        
        f_dir.columnconfigure(1, weight=1)
        
        # Mount Image Section
        f_img = tb.Labelframe(main, text="Mount Image(s)", padding=10)
        f_img.pack(fill=X, pady=10)
        
        tb.Radiobutton(f_img, text="Mount Image(s)", variable=self.type_var, value="image").grid(row=0, column=0, sticky="w")
        
        self.ent_img = tb.Entry(f_img, textvariable=self.path_var)
        self.ent_img.grid(row=0, column=1, sticky="ew", padx=5)
        tb.Button(f_img, text="Browse..", command=self._browse_img).grid(row=0, column=2)
        
        tb.Label(f_img, text="As:").grid(row=1, column=0, sticky="w", pady=5)
        tb.Combobox(f_img, textvariable=self.as_var, values=["iso", "fat"], width=5, state="readonly").grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        f_img.columnconfigure(1, weight=1)
        
        # Buttons
        btn_frame = tb.Frame(main)
        btn_frame.pack(fill=X, pady=10)
        tb.Button(btn_frame, text="OK", command=self._on_ok, bootstyle="success").pack(side=RIGHT)
        tb.Button(btn_frame, text="Cancel", command=self.destroy, bootstyle="secondary").pack(side=RIGHT, padx=10)

    def _browse_dir(self):
        self.type_var.set("dir")
        # Ensure dialog is on top
        self.attributes("-topmost", False)
        path = filedialog.askdirectory(parent=self)
        if path: self.path_var.set(path)
        self.lift()

    def _browse_img(self):
        self.type_var.set("image")
        # Ensure dialog is on top
        self.attributes("-topmost", False)
        paths = filedialog.askopenfilenames(parent=self, filetypes=[("Disk Images", "*.iso *.cue *.img *.bin"), ("All Files", "*.*")])
        if paths: self.path_var.set(";".join(paths))
        self.lift()

    def _on_ok(self):
        if not self.path_var.get():
            messagebox.showerror("Error", "Path is required.", parent=self)
            return
        self.result = {
            "drive": self.drive_var.get(),
            "type": self.type_var.get(),
            "path": self.path_var.get(),
            "label": self.label_var.get(),
            "as": self.as_var.get()
        }
        self.destroy()

class EditWindow(tb.Toplevel):
    def __init__(self, parent_app, zip_name):
        super().__init__(parent_app)
        self.transient(parent_app)
        self.parent_app = parent_app; self.logic = parent_app.logic
        self.main_frame = tb.Frame(self); self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.initial_data = {}; self.loading_data = True; self.has_unsaved_changes = False; self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.open_param_windows = {} # Track open parameter edit windows
        self._load_game_data(zip_name)

    def _mark_as_changed(self, *args):
        if self.loading_data: return
        self.has_unsaved_changes = True
        if hasattr(self, 'save_button'): 
            self.save_button.config(state="normal", bootstyle="danger")
            
    def _are_settings_equal(self, d1, d2):
        try:
            return json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)
        except:
            return False

    def _on_play_test(self):
        if self.has_unsaved_changes:
            if self._are_settings_equal(self._get_current_ui_values(), self.initial_data):
                 self.has_unsaved_changes = False
                 if hasattr(self, 'save_button'): self.save_button.config(state="disabled", bootstyle="success")
            elif messagebox.askyesno("Unsaved Changes", "Save changes before playing?", parent=self):
                self._save(close=False)
            else:
                return 
        
        # Check for main executable
        details = self._get_current_ui_values()
        main_exe = next((exe for exe, info in details.get("executables", {}).items() if info.get("role") == constants.ROLE_MAIN), None)
        if not main_exe:
            messagebox.showwarning("Missing Executable", "Please assign a Main Executable in the Executables tab.", parent=self)
            return
            
        try:
            # Check minimize setting
            should_minimize = self.parent_app.settings.get("minimize_on_launch", False)
            if should_minimize:
                try: self.iconify()
                except: pass
                
            # Ensure window is not topmost
            self.attributes("-topmost", False)
            thread = self.logic.launch_game(self.zip_name, force_fullscreen=self.parent_app.force_fullscreen_var.get(), auto_exit=self.parent_app.auto_exit_var.get())
            
            def check_thread():
                if thread.is_alive():
                    self.after(1000, check_thread)
                else:
                    if should_minimize:
                        self.deiconify()
                    self.lift()
            
            self.after(1000, check_thread)
            
        except Exception as e:
            if should_minimize: self.deiconify()
            self.lift()
            messagebox.showerror("Error", str(e), parent=self)

    def _on_test_play_temp(self):
        # Check for main executable
        details = self._get_current_ui_values()
        main_exe = next((exe for exe, info in details.get("executables", {}).items() if info.get("role") == constants.ROLE_MAIN), None)
        if not main_exe:
            messagebox.showwarning("Missing Executable", "Please assign a Main Executable in the Executables tab.", parent=self)
            return
            
        try:
            # Check minimize setting
            should_minimize = self.parent_app.settings.get("minimize_on_launch", False)
            if should_minimize:
                try: self.iconify()
                except: pass
                
            self.attributes("-topmost", False)
            
            # Generate temp config
            generated_lines = self.logic.generate_config_content(self.name, main_exe, details)
            content = "\n".join(generated_lines)
            
            temp_dir = os.path.join(self.logic.base_dir, "database", "games_datainfo", self.name, "confs")
            os.makedirs(temp_dir, exist_ok=True)
            temp_conf_path = os.path.join(temp_dir, "temp_test.conf")
            
            with open(temp_conf_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            # Launch with override
            thread = self.logic.launch_game(self.zip_name, force_fullscreen=self.parent_app.force_fullscreen_var.get(), auto_exit=self.parent_app.auto_exit_var.get(), config_override_path=temp_conf_path, dosbox_path_override=details.get("custom_dosbox_path"), details_override=details)
            
            # Monitor thread to restore window
            def check_thread():
                if thread.is_alive():
                    self.after(1000, check_thread)
                else:
                    if should_minimize:
                        self.deiconify()
                    self.lift()
            
            self.after(1000, check_thread)
            
        except Exception as e:
            if should_minimize: self.deiconify()
            self.lift()
            messagebox.showerror("Error", str(e), parent=self)

    def _on_close(self):
        if self.has_unsaved_changes:
            if self._are_settings_equal(self._get_current_ui_values(), self.initial_data):
                 self.destroy()
                 return
            if (answer := messagebox.askyesnocancel("Unsaved Changes", "You have unsaved changes. Do you want to save them before closing?", parent=self)) is True: self._save(close=True)
            elif answer is None: return
        self.destroy()

    def _load_game_data(self, zip_name, existing_data=None):
        self.loading_data = True; [widget.destroy() for widget in self.main_frame.winfo_children()]
        self.zip_name = zip_name; self.name = os.path.splitext(zip_name)[0]; self.original_name = self.name
        self.title(f"Configuration: {self.name}"); self.resizable(False, False)
        
        if existing_data: 
            # Deep copy to ensure we don't have reference issues
            self.game_data = json.loads(json.dumps(existing_data))
        else: 
            self.game_data = self.logic.import_from_dosbox_conf(self.name)
        
        # Sync with reference config
        self.game_data = self.logic.sync_dosbox_settings_with_reference(self.game_data)
            
        self._auto_assign_roles_if_needed()
        self.initial_data = json.loads(json.dumps(self.game_data))
        self.has_unsaved_changes = False
        
        self.is_installed = 'installed' in self.parent_app.tree.item(self.zip_name, 'tags'); self.dosbox_installations = self.parent_app.settings.get("dosbox_installations", [])
        button_frame = tb.Frame(self.main_frame); button_frame.pack(fill=tk.X, padx=10, pady=(5,10)); button_frame.columnconfigure(1, weight=1)
        tb.Button(button_frame, text="<< Previous", command=lambda: self._navigate(-1)).grid(row=0, column=0, sticky='w')
        
        center_btn_frame = tb.Frame(button_frame); center_btn_frame.grid(row=0, column=1)
        self.save_button = tb.Button(center_btn_frame, text="Save Configuration", command=lambda: self._save(close=False), bootstyle="success", state="disabled"); self.save_button.pack(side=LEFT, padx=5)
        tb.Button(center_btn_frame, text="▶ Play", command=self._on_play_test, bootstyle="success-outline").pack(side=LEFT, padx=5)
        tb.Button(center_btn_frame, text="Test (No Save)", command=self._on_test_play_temp, bootstyle="warning-outline").pack(side=LEFT, padx=5)
        
        tb.Button(button_frame, text="Next >>", command=lambda: self._navigate(1)).grid(row=0, column=2, sticky='e')
        
        self.tabs = tb.Notebook(self.main_frame); self.tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=0)
        tab_map = {
            "Info": self._build_general_tab, 
            "Quick Settings": self._build_simple_tab,
            "Mounts": self._build_drives_tab,
            "Autoexec": self._build_autoexec_tab,
            "User.conf": self._build_expert_tab,
            "Executables": self._build_executables_tab
        }
        for name, builder in tab_map.items():
            tab = tb.Frame(self.tabs); self.tabs.add(tab, text=name); setattr(self, f"tab_{name.lower().replace(' ', '_').replace('&','and').replace('.','_')}", tab)
            # Always build User.conf (Expert) tab to ensure it's populated
            if name == "User.conf":
                builder(tab)
            
            if self.is_installed or name == "Info": 
                if name != "User.conf": # Already built above
                    builder(tab)
            else: 
                self.tabs.tab(tab, state="disabled")
            
        self.tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        
        self.loading_data = False
        
        # Initialize hidden variables that were previously in removed tabs
        # This prevents crashes when accessing them in _get_current_ui_values
        self.v_dosbox_path_name = tk.StringVar(value="(Use Default)")
        if self.game_data.get("custom_dosbox_path"):
             # Try to match name
             path = self.game_data.get("custom_dosbox_path")
             matched = next((inst['name'] for inst in self.dosbox_installations if inst['path'] == path), None)
             if matched: self.v_dosbox_path_name.set(matched)
             else: self.v_dosbox_path_name.set(path) # Set as custom path string if no name match

    def _on_tab_changed(self, event):
        try:
            selected_tab = self.tabs.select()
            tab_text = self.tabs.tab(selected_tab, "text")
            if tab_text == "User.conf":
                self._refresh_expert_tree_view()
                self._check_and_convert_params(auto_fix=True)
            elif tab_text == "Quick Settings":
                self._sync_quick_settings_ui()
        except Exception: pass

    def _auto_assign_roles_if_needed(self):
        executables = self.game_data.get("executables", {})
        if executables and any(info.get("role") != constants.ROLE_UNASSIGNED for info in executables.values()): return
        all_exes = self.logic.get_all_executables(self.name); new_exe_map = {}
        if len(all_exes) == 1: new_exe_map[all_exes[0]] = {"role": constants.ROLE_MAIN, "title": "", "params": ""}
        else:
            for exe in all_exes:
                exe_lower = os.path.basename(exe).lower(); role = constants.ROLE_UNASSIGNED
                if "setup" in exe_lower or "setsound" in exe_lower: role = constants.ROLE_SETUP
                elif "install" in exe_lower: role = constants.ROLE_INSTALL
                new_exe_map[exe] = {"role": role, "title": "", "params": ""}
        self.game_data["executables"] = new_exe_map; self.logic.save_game_details(self.name, self.game_data)

    def _navigate(self, direction):
        if self.has_unsaved_changes:
            answer = messagebox.askyesnocancel("Unsaved Changes", "You have unsaved changes. Do you want to save them before navigating?", parent=self)
            if answer is True: self._save(close=False)
            elif answer is None: return
        installed_ids = [item for item in self.parent_app.tree.get_children() if 'installed' in self.parent_app.tree.item(item, 'tags')]
        if not installed_ids: return
        try:
            current_index = installed_ids.index(self.zip_name); new_index = (current_index + direction) % len(installed_ids); new_zip_name = installed_ids[new_index]
            current_tab_index = self.tabs.index(self.tabs.select())
            
            # Optimization: Instead of destroying everything, just reload data if possible
            # But since tabs are dynamic (Executables tab depends on files), we might need to rebuild some parts.
            # However, rebuilding everything is slow.
            # Let's try to just call _load_game_data which rebuilds everything.
            # The user complained about speed. The slowness comes from destroying and recreating widgets.
            # A full refactor to update widgets in place is complex.
            # But we can at least optimize the "window closing/opening" feel by NOT destroying the window itself (which we already don't do).
            # The user said: "it looks like the window closes and opens again".
            # This might be because we are destroying all children of main_frame.
            
            # Let's try to minimize the visual glitch by using `update_idletasks` or similar?
            # Or maybe we can just update the title and content without the flicker.
            
            self._load_game_data(new_zip_name)
            
            # Restore tab selection
            if current_tab_index < len(self.tabs.tabs()):
                self.tabs.select(current_tab_index)
                
            self.parent_app.tree.selection_set(new_zip_name); self.parent_app.tree.see(new_zip_name)
        except ValueError:
            if installed_ids: self._load_game_data(installed_ids[0]); self.parent_app.tree.selection_set(installed_ids[0]); self.parent_app.tree.see(installed_ids[0])

    def _build_custom_conf_tab(self, parent):
        parent.columnconfigure(0, weight=1); parent.rowconfigure(1, weight=1); header_frame = tb.Frame(parent); header_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=(10,5))
        
        tb.Label(header_frame, text="DOSBox Configuration (dosbox.conf)", bootstyle="info").pack(side=LEFT)
        
        tb.Button(header_frame, text="Reset (Default)", command=self._reset_to_default_dosbox, bootstyle="danger-outline").pack(side=tk.RIGHT, padx=(5,0))
        tb.Button(header_frame, text="Regenerate from Settings", command=self._force_regenerate, bootstyle="info-outline").pack(side=tk.RIGHT)
        
        self.custom_conf_text = ScrolledText(parent, wrap=tk.WORD, autohide=True); self.custom_conf_text.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0,10))
        
        # If custom content exists, show it. Otherwise generate it.
        content = self.game_data.get("custom_config_content", "")
        if not content.strip():
             content = self._generate_conf_content()
             
        self.custom_conf_text.text.insert(tk.END, content)
        self.custom_conf_text.text.bind("<KeyRelease>", self._on_custom_conf_key)
        
        # Bind tab change to update this if needed?
        # The user wants "akakolvek zmena v kartach ... sa okamzite prejavi".
        # Since this is a text field, we can't easily update it while preserving manual edits.
        # But if the user hasn't manually edited (or if we treat UI as master), we can update.
        # For now, let's rely on "Regenerate" button or initial load.
        # Implementing live update of text field from UI changes is complex because it would overwrite manual edits.
        # However, we can update it when the tab is selected IF no manual edits were made?
        # Let's stick to manual regeneration for now to avoid data loss, as per "Force Regenerate".

    def _on_custom_conf_key(self, event):
        self._mark_as_changed()

    def _update_custom_conf_preview(self):
        content = self._generate_conf_content()
        self.custom_conf_text.text.delete("1.0", tk.END)
        self.custom_conf_text.text.insert("1.0", content)

    def _generate_conf_content(self):
        # We need to get values from UI widgets, not just self.game_data
        temp_details = self._get_current_ui_values()
        main_exe = next((exe for exe, info in temp_details.get("executables", {}).items() if info.get("role") == constants.ROLE_MAIN), None)
        lines = self.logic.generate_config_content(self.name, main_exe, temp_details)
        return "\n".join(lines)
        
    def _reset_to_default_dosbox(self):
        if messagebox.askyesno("Reset to Default?", "Load default configuration from DOSBox folder (without comments)?\nThis will overwrite current text.", parent=self):
            content = self.logic.get_dosbox_conf_content()
            if content:
                # Strip comments
                lines = [line for line in content.splitlines() if not line.strip().startswith(('#', ';'))]
                clean_content = "\n".join(lines)
                self.custom_conf_text.text.delete("1.0", tk.END)
                self.custom_conf_text.text.insert("1.0", clean_content)
                self._mark_as_changed()
            else:
                messagebox.showinfo("Info", "No default configuration found.", parent=self)

    def _build_autoexec_tab(self, parent):
        parent.columnconfigure(0, weight=1); parent.rowconfigure(1, weight=1)
        
        header = tb.Frame(parent, padding=10)
        header.grid(row=0, column=0, sticky="ew")
        
        tb.Label(header, text="Autoexec Configuration (Main Game Only)", bootstyle="info", font="-weight bold").pack(side=LEFT)
        
        # Split view: Pre-Launch and Post-Launch
        paned = tb.Panedwindow(parent, orient=VERTICAL)
        paned.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # Pre-Launch Frame
        f_pre = tb.Frame(paned)
        paned.add(f_pre, weight=1)
        
        tb.Label(f_pre, text="Pre-Launch Commands (Before Game Executable):", bootstyle="secondary").pack(anchor="w", pady=(0, 5))
        self.t_autoexec_pre = ScrolledText(f_pre, wrap=tk.WORD, height=10)
        self.t_autoexec_pre.pack(fill=BOTH, expand=True)
        
        # Post-Launch Frame
        f_post = tb.Frame(paned)
        paned.add(f_post, weight=1)
        
        tb.Label(f_post, text="Post-Launch Commands (After Game Exit):", bootstyle="secondary").pack(anchor="w", pady=(10, 5))
        self.t_autoexec_post = ScrolledText(f_post, wrap=tk.WORD, height=5)
        self.t_autoexec_post.pack(fill=BOTH, expand=True)
        
        # Load content
        # We now store autoexec_pre and autoexec_post in game_details
        # If legacy custom_autoexec exists, we might want to show it or migrate it?
        # For now, let's just load the new fields.
        
        pre_content = self.game_data.get("autoexec_pre", "")
        if isinstance(pre_content, list): pre_content = "\n".join(pre_content)
        self.t_autoexec_pre.text.insert("1.0", pre_content)
        
        post_content = self.game_data.get("autoexec_post", "")
        if isinstance(post_content, list): post_content = "\n".join(post_content)
        self.t_autoexec_post.text.insert("1.0", post_content)
        
        # Bind changes
        self.t_autoexec_pre.text.bind("<<Modified>>", self._mark_as_changed)
        self.t_autoexec_post.text.bind("<<Modified>>", self._mark_as_changed)

    def _build_dosbox_tab(self, parent):
        self.t_autoexec.text.bind("<KeyRelease>", self._on_autoexec_change)

    def _on_autoexec_change(self, event):
        # Save custom autoexec back to game_data
        text = self.t_autoexec.text.get("1.0", tk.END).strip()
        if text:
            self.game_data["custom_autoexec"] = text.split("\n")
        else:
            self.game_data["custom_autoexec"] = []
        self._mark_as_changed()

    def _build_expert_tab(self, parent):
        parent.columnconfigure(0, weight=1); parent.rowconfigure(2, weight=1)
        # Increase row weight for bottom panel to ensure visibility
        parent.rowconfigure(4, weight=0) 
        
        # Header with Config Selector
        header = tb.Frame(parent, padding=10); header.grid(row=0, column=0, sticky="ew")
        
        # Top Row: Config Selector + Buttons
        top_row = tb.Frame(header)
        top_row.pack(fill=X, expand=True)
        
        tb.Label(top_row, text="Reference Config:", bootstyle="info").pack(side=LEFT)
        
        self.available_confs = self.logic.get_available_dosbox_confs()
        self.selected_conf_var = tk.StringVar()
        if self.available_confs:
            # Check if we have a saved preference for this game
            saved_conf = self.game_data.get("reference_conf")
            
            default_selection = None
            
            # Normalize available confs for comparison
            avail_norm = [os.path.normpath(os.path.join(self.logic.base_dir, c) if not os.path.isabs(c) else c).lower() for c in self.available_confs]
            
            if saved_conf:
                saved_norm = os.path.normpath(os.path.join(self.logic.base_dir, saved_conf) if not os.path.isabs(saved_conf) else saved_conf).lower()
                if saved_norm in avail_norm:
                    # Find the original string
                    idx = avail_norm.index(saved_norm)
                    default_selection = self.available_confs[idx]
            
            if not default_selection:
                # Default to first
                default_selection = self.available_confs[0]
                
                # Try to match with default DOSBox setting
                dosbox_installations = self.parent_app.settings.get("dosbox_installations", [])
                default_path = next((inst.get("path") for inst in dosbox_installations if inst.get("default")), None)
                
                if default_path:
                    default_dir = os.path.dirname(default_path)
                    # Normalize paths for comparison
                    default_dir_norm = os.path.normpath(default_dir).lower()
                    
                    for conf in self.available_confs:
                        # conf is relative path or absolute path
                        # We need to resolve it to absolute to compare directory
                        if os.path.isabs(conf):
                            conf_abs = conf
                        else:
                            conf_abs = os.path.join(self.logic.base_dir, conf)
                            
                        conf_dir = os.path.dirname(conf_abs)
                        if os.path.normpath(conf_dir).lower() == default_dir_norm:
                            # Found a match in the same directory.
                            # But wait, there might be multiple configs in the same directory (e.g. dosbox.conf and dosbox-staging.conf)
                            # We should prefer the one that matches the executable name if possible, or the "staging" one if it's staging.
                            
                            # If we already found a match, check if this one is "better"
                            # e.g. if we found "dosbox.conf" but now we see "dosbox-staging.conf" and path has "staging"
                            
                            if "staging" in default_path.lower() and "staging" in conf.lower():
                                default_selection = conf
                                break # Strong match
                            elif "dosbox-x" in default_path.lower() and "dosbox-x" in conf.lower():
                                # Prefer "full-reference" if available
                                if "full-reference" in conf.lower():
                                    default_selection = conf
                                    break # Strongest match
                                
                                # If we already have a dosbox-x match, don't overwrite unless this one is better (which we handled above)
                                # But if we only have a weak match (or no match), take this one.
                                # Since we are iterating, let's just take it if we haven't found a full-reference one yet.
                                if not default_selection or "full-reference" not in default_selection.lower():
                                    default_selection = conf
                                # Don't break, keep looking for full-reference
                            else:
                                # Weak match (same dir), keep it but continue looking for strong match
                                if not default_selection:
                                    default_selection = conf
            
            self.selected_conf_var.set(default_selection)
            # Ensure it's saved if it wasn't set
            if not saved_conf:
                self.game_data["reference_conf"] = default_selection
            
        cb_conf = tb.Combobox(top_row, textvariable=self.selected_conf_var, values=self.available_confs, width=60, state="readonly")
        cb_conf.pack(side=LEFT, padx=10, fill=X, expand=True)
        
        # Bind selection change to auto-refresh and save preference
        def on_conf_change(event):
            self.game_data["reference_conf"] = self.selected_conf_var.get()
            self._mark_as_changed()
            # Automatically reset settings to match the new reference config (as requested)
            self._reset_expert_settings(silent=True)
            # Force refresh of metadata and tree view to show new defaults
            self._refresh_expert_metadata()
            
        cb_conf.bind("<<ComboboxSelected>>", on_conf_change)
        
        # Refresh Button (Removed as requested)
        # tb.Button(top_row, text="Refresh", command=self._refresh_expert_metadata, bootstyle="info-outline").pack(side=LEFT, padx=5)
        tb.Button(top_row, text="Reset", command=self._reset_expert_settings, bootstyle="danger-outline").pack(side=LEFT, padx=5)
        tb.Button(top_row, text="Check/Convert", command=self._check_and_convert_params, bootstyle="warning-outline").pack(side=LEFT, padx=5)
        
        # Bottom Row: Info Labels
        bot_row = tb.Frame(header, padding=(0, 5, 0, 0))
        bot_row.pack(fill=X, expand=True)
        
        # Version Info Label
        self.lbl_dosbox_version = tb.Label(bot_row, text="Version: Unknown", bootstyle="secondary")
        self.lbl_dosbox_version.pack(side=LEFT, padx=(0, 10))
        
        # Info Label for Resolved Path (Moved from DOSBox tab)
        resolved_path = self.game_data.get("custom_dosbox_path", "")
        if not resolved_path:
             # If not set, it uses default.
             resolved_path = self.logic.default_dosbox_exe
             
        resolved_engine = "Unknown"
        # Better detection logic
        path_lower = resolved_path.lower()
        if "staging" in path_lower: resolved_engine = "DOSBox Staging"
        elif "dosbox-x" in path_lower or "dosbox_x" in path_lower: resolved_engine = "DOSBox-X"
        elif "dosbox" in path_lower: resolved_engine = "DOSBox (Standard)"
        
        # Also check the selected config file name if path is ambiguous
        if resolved_engine == "DOSBox (Standard)" and self.selected_conf_var.get():
            conf_lower = self.selected_conf_var.get().lower()
            if "staging" in conf_lower: resolved_engine = "DOSBox Staging"
            elif "dosbox-x" in conf_lower: resolved_engine = "DOSBox-X"
        
        rel_path = resolved_path
        try:
            # Ensure both paths are absolute before calculating relative path
            abs_resolved = os.path.abspath(resolved_path)
            abs_base = os.path.abspath(self.logic.base_dir)
            rel_path = os.path.relpath(abs_resolved, abs_base)
        except ValueError: pass
        
        # Path label removed as requested
        # info_text = f"Path: {truncate_text(rel_path, 60)}"
        # self.lbl_expert_engine_info = tb.Label(bot_row, text=info_text, bootstyle="warning", justify="left")
        # self.lbl_expert_engine_info.pack(side=LEFT)
        
        tb.Label(parent, text="Expert Configuration (User Overrides)", bootstyle="warning").grid(row=1, column=0, sticky="w", padx=10)
        
        # Search Bar
        search_frame = tb.Frame(parent)
        search_frame.grid(row=1, column=0, sticky="e", padx=(0, 25)) # Moved to col 0, added padding for scrollbar space
        tb.Label(search_frame, text="Search:").pack(side=LEFT, padx=(0, 5))
        self.expert_search_var = tk.StringVar()
        self.expert_search_var.trace("w", lambda *args: self._refresh_expert_tree_view())
        tb.Entry(search_frame, textvariable=self.expert_search_var, width=25).pack(side=LEFT)
        
        self.expert_tree = tb.Treeview(parent, columns=("section", "key", "value", "default"), show="headings")
        self.expert_tree.heading("section", text="Section", anchor="w")
        self.expert_tree.heading("key", text="Key", anchor="w")
        self.expert_tree.heading("value", text="Value", anchor="w")
        self.expert_tree.heading("default", text="Default", anchor="w")
        self.expert_tree.column("section", width=100, anchor="w")
        self.expert_tree.column("key", width=150, anchor="w")
        self.expert_tree.column("value", width=150, anchor="w")
        self.expert_tree.column("default", width=150, anchor="w")
        
        # Add Scrollbar
        vsb = tb.Scrollbar(parent, orient="vertical", command=self.expert_tree.yview)
        self.expert_tree.configure(yscrollcommand=vsb.set)
        
        self.expert_tree.grid(row=2, column=0, sticky="nsew", padx=(10, 0))
        vsb.grid(row=2, column=1, sticky="ns", padx=(0, 10))
        
        # Populate from dosbox_settings
        settings = self.game_data.get("dosbox_settings", {})
        for section, keys in settings.items():
            for key, value in keys.items():
                self.expert_tree.insert("", "end", values=(section, key, value))
                
        btn_frame = tb.Frame(parent, padding=10); btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        # Buttons enabled as requested by user
        self.btn_add_param = tb.Button(btn_frame, text="Add Parameter (+)", command=self._add_expert_param_dialog, bootstyle="success", state="normal")
        # self.btn_add_param.pack(side=LEFT) # Hidden as requested
        # tb.Button(btn_frame, text="Remove Selected", command=self._remove_expert_param, bootstyle="danger", state="normal").pack(side=LEFT, padx=5) # Hidden as requested
        
        # Toggle Changed Only
        self.btn_toggle_changed = tb.Button(btn_frame, text="Show Changed Only", command=self._toggle_changed_only, bootstyle="secondary-outline")
        self.btn_toggle_changed.pack(side=RIGHT)
        
        # Description Panel -> Split Panel
        self.expert_bottom_frame = tb.Frame(parent)
        self.expert_bottom_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)
        parent.rowconfigure(4, weight=0) # Don't let it expand infinitely, but give it space
        parent.rowconfigure(2, weight=1) # Treeview takes most space
        
        # Left: Edit Controls
        self.expert_edit_frame = tb.Labelframe(self.expert_bottom_frame, text="Edit Parameter", bootstyle="warning", padding=10)
        self.expert_edit_frame.pack(side=LEFT, fill=Y, expand=False, padx=(0, 5))
        self.expert_edit_frame.configure(width=300) 
        # self.expert_edit_frame.pack_propagate(False) # Removed to prevent button cutoff
        
        # Placeholder for edit frame
        tb.Label(self.expert_edit_frame, text="Select a parameter to edit.", bootstyle="secondary", wraplength=280).pack(pady=20)

        # Right: Info
        self.desc_frame = tb.Labelframe(self.expert_bottom_frame, text="Parameter Info", bootstyle="info", padding=10)
        self.desc_frame.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Use Text widget with Scrollbar instead of Label
        # Removed bg=parent.cget("bg") to avoid TclError with ttk frames
        self.txt_expert_desc = tk.Text(self.desc_frame, height=7, wrap=tk.WORD, state="disabled", relief="flat", font=("Consolas", 9))
        desc_vsb = tb.Scrollbar(self.desc_frame, orient="vertical", command=self.txt_expert_desc.yview)
        self.txt_expert_desc.configure(yscrollcommand=desc_vsb.set)
        
        self.txt_expert_desc.pack(side=LEFT, fill=BOTH, expand=True)
        desc_vsb.pack(side=RIGHT, fill=Y)
        
        # Initial text
        self.txt_expert_desc.config(state="normal")
        self.txt_expert_desc.insert("1.0", "Select a parameter to see details and edit.")
        self.txt_expert_desc.config(state="disabled")

        self.expert_tree.bind("<<TreeviewSelect>>", self._on_expert_select)
        self.expert_tree.bind("<Button-3>", self._show_expert_context_menu)
        # Removed double click and motion bindings as requested
        
        # Initial metadata load
        self._refresh_expert_metadata()

    def _toggle_changed_only(self):
        self.show_changed_only = not getattr(self, 'show_changed_only', False)
        self.btn_toggle_changed.config(bootstyle="warning" if self.show_changed_only else "secondary-outline")
        if hasattr(self, 'expert_search_var'):
            self.expert_search_var.set("")
        self._refresh_expert_tree_view()

    def _update_add_param_button_state(self):
        """Disables Add Parameter button if all possible parameters are already added."""
        if not hasattr(self, 'btn_add_param'): return
        
        # Get reference settings (all possible keys)
        ref_settings = getattr(self, 'reference_settings', {})
        if not ref_settings: return # Can't determine
        
        # Count total possible keys
        total_possible = sum(len(keys) for keys in ref_settings.values())
        
        # Count current keys in tree
        current_count = len(self.expert_tree.get_children())
        
        if current_count >= total_possible:
            self.btn_add_param.config(state="disabled")
        else:
            self.btn_add_param.config(state="normal")

    def _refresh_expert_tree_view(self):
        # Similar to update_expert_tree but as a class method
        if not hasattr(self, 'expert_tree'): return
        
        ref_settings = getattr(self, 'reference_settings', {})
        curr_settings = self.game_data.get("dosbox_settings", {})
        search_query = self.expert_search_var.get().lower().strip() if hasattr(self, 'expert_search_var') else ""
        csv_meta = getattr(self, 'current_metadata', {})
        
        self.expert_tree.delete(*self.expert_tree.get_children())
        
        all_sections = set(curr_settings.keys()) | set(ref_settings.keys())
        for section in sorted(all_sections):
            if section.lower() == "autoexec": continue
            curr_keys = curr_settings.get(section, {})
            ref_keys = ref_settings.get(section, {})
            all_keys = set(curr_keys.keys()) | set(ref_keys.keys())
            
            for key in sorted(all_keys):
                val = curr_keys.get(key, ref_keys.get(key))
                ref_val = ref_keys.get(key)
                
                is_changed = str(val) != str(ref_val)
                if getattr(self, 'show_changed_only', False) and not is_changed:
                    continue
                
                # Search Filter
                if search_query:
                    # Check key, section, value
                    match = (search_query in key.lower()) or (search_query in section.lower()) or (search_query in str(val).lower())
                    # Check description
                    if not match:
                        meta = csv_meta.get(section.lower(), {}).get(key.lower(), {})
                        desc = meta.get("info", "").lower()
                        if search_query in desc:
                            match = True
                    
                    if not match: continue

                item_id = self.expert_tree.insert("", "end", values=(section, key, val, ref_val))
                if is_changed:
                    self.expert_tree.item(item_id, tags=("changed",))
                    
        self.expert_tree.tag_configure("changed", foreground="#ff5555")
        self._update_add_param_button_state()

    def _on_expert_select(self, event):
        if not (sel := self.expert_tree.selection()): return
        item = sel[0]
        vals = self.expert_tree.item(item, "values")
        if not vals: return
        sec, key, current_val = vals[0], vals[1], vals[2]
        
        # Lookup metadata
        csv_meta = getattr(self, 'current_metadata', {})
        meta = csv_meta.get(sec.lower(), {}).get(key.lower(), {})
        desc = meta.get("info", "No description available.")
        possible = meta.get("possible", [])
        
        # Update Info Text
        self.txt_expert_desc.config(state="normal")
        self.txt_expert_desc.delete("1.0", tk.END)
        self.txt_expert_desc.insert("1.0", f"[{sec}] {key}\n\n{desc}")
        if possible:
             self.txt_expert_desc.insert(tk.END, f"\n\nPossible Values: {', '.join(possible)}")
        self.txt_expert_desc.config(state="disabled")
        
        # Update Edit Frame
        for widget in self.expert_edit_frame.winfo_children(): widget.destroy()
        
        tb.Label(self.expert_edit_frame, text=f"Section: {sec}", font=("Segoe UI", 8)).pack(anchor="w")
        tb.Label(self.expert_edit_frame, text=f"Key: {key}", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 5))
        
        self.expert_edit_var = tk.StringVar(value=current_val)
        
        widget = None
        if possible:
            cb = tb.Combobox(self.expert_edit_frame, textvariable=self.expert_edit_var, values=possible)
            cb.pack(fill=X, pady=5)
            widget = cb
        else:
            entry = tb.Entry(self.expert_edit_frame, textvariable=self.expert_edit_var)
            entry.pack(fill=X, pady=5)
            widget = entry
            
        if widget:
            # Refresh tree on focus out to handle "Show Changed Only" filtering
            refresh_cmd = lambda e: self._refresh_expert_tree_view() if getattr(self, 'show_changed_only', False) else None
            widget.bind("<FocusOut>", refresh_cmd)
            widget.bind("<Return>", refresh_cmd)
            
        def save_change(*args):
            new_val = self.expert_edit_var.get()
            
            # Update game_data to persist changes when filtering
            if "dosbox_settings" not in self.game_data: self.game_data["dosbox_settings"] = {}
            if sec not in self.game_data["dosbox_settings"]: self.game_data["dosbox_settings"][sec] = {}
            self.game_data["dosbox_settings"][sec][key] = new_val
            
            # Sync Quick Settings UI
            self._sync_quick_settings_ui()
            
            # Get default value for display
            ref_val = getattr(self, 'reference_settings', {}).get(sec, {}).get(key)
            
            try:
                self.expert_tree.item(item, values=(sec, key, new_val, ref_val))
                self._mark_as_changed()
                
                # Re-check highlighting
                if str(new_val) != str(ref_val):
                    self.expert_tree.item(item, tags=("changed",))
                else:
                    self.expert_tree.item(item, tags=())
            except:
                # Item might be gone if tree was refreshed
                pass
            
        self.expert_edit_var.trace("w", save_change)
        # tb.Button(self.expert_edit_frame, text="Apply Change", command=save_change, bootstyle="success-outline").pack(fill=X, pady=10, padx=5)

    def _show_expert_context_menu(self, event):
        item_id = self.expert_tree.identify_row(event.y)
        if not item_id:
            return
            
        self.expert_tree.selection_set(item_id)
        item = self.expert_tree.item(item_id)
        values = item['values']
        if not values: return
        
        section, key, current_val, default_val = values[0], values[1], values[2], values[3]
        
        menu = tk.Menu(self.expert_tree, tearoff=0)
        
        # Possible Values Submenu
        possible_menu = tk.Menu(menu, tearoff=0)
        
        # Get metadata for this key
        metadata = getattr(self, 'current_metadata', {}).get(section.lower(), {}).get(key.lower(), {})
        possible_values = metadata.get("possible", [])
        
        if possible_values:
            for val in possible_values:
                # Use lambda with default arg to capture value
                possible_menu.add_command(label=str(val), command=lambda v=val: self._update_expert_value(section, key, v))
            menu.add_cascade(label="Possible Values", menu=possible_menu)
        else:
            menu.add_command(label="Possible Values (None)", state="disabled")
            
        # Reset to Default
        if str(default_val) != "N/A":
             menu.add_command(label=f"Reset to Default ({default_val})", command=lambda: self._update_expert_value(section, key, default_val))
        else:
             menu.add_command(label="Reset to Default", state="disabled")

        menu.post(event.x_root, event.y_root)

    def _update_expert_value(self, section, key, value):
        if "dosbox_settings" not in self.game_data:
            self.game_data["dosbox_settings"] = {}
        if section not in self.game_data["dosbox_settings"]:
            self.game_data["dosbox_settings"][section] = {}
            
        self.game_data["dosbox_settings"][section][key] = value
        self._mark_as_changed()
        self._sync_quick_settings_ui()
        self._refresh_expert_tree_view()
        # Also update the edit frame if it's showing this item
        self._on_expert_select(None)

    def _on_expert_motion(self, event):
        # Deprecated
        pass

    def _on_expert_double_click(self, event):
        # Deprecated
        pass

    def _check_and_convert_params(self, silent_if_empty=False, auto_fix=False):
        """Checks for invalid parameters and offers to convert them based on mapping."""
        if not hasattr(self, 'expert_tree'): return
        
        # 1. Identify Invalid Parameters
        invalid_params = [] # List of (item_id, section, key, value)
        
        # Get reference settings (valid keys)
        ref_settings = getattr(self, 'reference_settings', {})
        if not ref_settings:
            # Try to load if missing
            selected_conf = self.selected_conf_var.get()
            if selected_conf:
                if not os.path.isabs(selected_conf): selected_conf = os.path.join(self.logic.base_dir, selected_conf)
                try:
                    with open(selected_conf, 'r', encoding='utf-8', errors='ignore') as f:
                        ref_settings = self.logic.parse_dosbox_conf_to_json(f.read())
                except: pass
        
        if not ref_settings:
            if not silent_if_empty and not auto_fix:
                messagebox.showerror("Error", "Could not load reference configuration for validation.", parent=self)
            return

        # Load Mapping
        mapping_path = os.path.join(self.logic.base_dir, "database", "mapping_functions.json")
        mapping = {}
        if os.path.exists(mapping_path):
            try:
                with open(mapping_path, 'r', encoding='utf-8') as f: mapping = json.load(f)
            except: pass
            
        # Determine Target Variant
        target_variant = "standard"
        if hasattr(self, 'detected_variant'):
            if "staging" in self.detected_variant.lower(): target_variant = "staging"
            elif "x" in self.detected_variant.lower() and "dosbox" not in self.detected_variant.lower(): target_variant = "x"
            elif "dosbox-x" in self.detected_variant.lower(): target_variant = "x"
            
        # Check each item in tree
        for item in self.expert_tree.get_children():
            vals = self.expert_tree.item(item, "values")
            if not vals or len(vals) < 3: continue
            
            sec, key, val = vals[0], vals[1], vals[2]
            
            # Check if exists in reference
            if sec in ref_settings and key in ref_settings[sec]:
                continue # Valid
                
            # If not valid, check for mapping
            proposed_change = None
            
            # Check mapping for (sec, key) -> target_variant
            if sec in mapping and key in mapping[sec]:
                map_data = mapping[sec][key].get(target_variant)
                if map_data and map_data.get("key"):
                    new_sec = map_data.get("section", sec)
                    new_key = map_data.get("key")
                    
                    # Verify if the mapped key is actually valid in reference
                    if new_sec in ref_settings and new_key in ref_settings[new_sec]:
                        proposed_change = (new_sec, new_key)
            
            if proposed_change:
                invalid_params.append({
                    "item": item,
                    "old": (sec, key),
                    "new": proposed_change,
                    "val": val
                })
            else:
                # Invalid but no mapping found - maybe just report it?
                # User asked to "offer possibility where to assign based on mapping_function"
                # If no mapping, we ignore for now or could list as "Unknown"
                pass

        if not invalid_params:
            if not silent_if_empty and not auto_fix:
                messagebox.showinfo("Check Complete", "No convertible invalid parameters found.", parent=self)
            return
            
        # 2. Auto Fix or Show Dialog
        if auto_fix:
            count = 0
            for p in invalid_params:
                # Update game_data
                old_sec, old_key = p['old']
                new_sec, new_key = p['new']
                val = p['val']
                
                # Remove old
                if old_sec in self.game_data.get("dosbox_settings", {}) and old_key in self.game_data["dosbox_settings"][old_sec]:
                    del self.game_data["dosbox_settings"][old_sec][old_key]
                    # Clean up section if empty?
                    if not self.game_data["dosbox_settings"][old_sec]:
                        del self.game_data["dosbox_settings"][old_sec]
                
                # Add new
                if "dosbox_settings" not in self.game_data: self.game_data["dosbox_settings"] = {}
                if new_sec not in self.game_data["dosbox_settings"]: self.game_data["dosbox_settings"][new_sec] = {}
                self.game_data["dosbox_settings"][new_sec][new_key] = val
                
                count += 1
                
            self._mark_as_changed()
            self._refresh_expert_tree_view()
            # Silent update, no message box as requested "proste to len zmen"
            return

        d = tb.Toplevel(self); d.title("Convert Parameters"); d.geometry("600x400")
        
        tb.Label(d, text=f"Found {len(invalid_params)} parameters that can be converted:", font="-weight bold").pack(pady=10)
        
        list_frame = tb.Frame(d)
        list_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        tree = tb.Treeview(list_frame, columns=("old", "arrow", "new", "value"), show="headings", height=10)
        tree.heading("old", text="Current Parameter")
        tree.heading("arrow", text="->")
        tree.heading("new", text="New Parameter")
        tree.heading("value", text="Value")
        
        tree.column("old", width=200)
        tree.column("arrow", width=30, anchor="center")
        tree.column("new", width=200)
        tree.column("value", width=100)
        
        tree.pack(side=LEFT, fill=BOTH, expand=True)
        tb.Scrollbar(list_frame, orient="vertical", command=tree.yview).pack(side=RIGHT, fill=Y)
        
        for p in invalid_params:
            old_str = f"[{p['old'][0]}] {p['old'][1]}"
            new_str = f"[{p['new'][0]}] {p['new'][1]}"
            tree.insert("", "end", values=(old_str, "->", new_str, p['val']))
            
        def convert():
            count = 0
            for p in invalid_params:
                # Update game_data
                old_sec, old_key = p['old']
                new_sec, new_key = p['new']
                val = p['val']
                
                # Remove old
                if old_sec in self.game_data.get("dosbox_settings", {}) and old_key in self.game_data["dosbox_settings"][old_sec]:
                    del self.game_data["dosbox_settings"][old_sec][old_key]
                    # Clean up section if empty?
                    if not self.game_data["dosbox_settings"][old_sec]:
                        del self.game_data["dosbox_settings"][old_sec]
                
                # Add new
                if "dosbox_settings" not in self.game_data: self.game_data["dosbox_settings"] = {}
                if new_sec not in self.game_data["dosbox_settings"]: self.game_data["dosbox_settings"][new_sec] = {}
                self.game_data["dosbox_settings"][new_sec][new_key] = val
                
                count += 1
                
            self._mark_as_changed()
            self._refresh_expert_tree_view()
            d.destroy()
            messagebox.showinfo("Success", f"Converted {count} parameters.", parent=self)
            
        btn_frame = tb.Frame(d, padding=10)
        btn_frame.pack(fill=X)
        tb.Button(btn_frame, text="Convert All", command=convert, bootstyle="success").pack(side=RIGHT, padx=5)
        tb.Button(btn_frame, text="Cancel", command=d.destroy, bootstyle="secondary").pack(side=RIGHT)

    def _reset_expert_settings(self, silent=False):
        selected_conf = self.selected_conf_var.get()
        if not selected_conf: return
        
        if not silent and not messagebox.askyesno("Reset Settings", f"This will replace all Expert settings with values from:\n{selected_conf}\n\nAre you sure?", parent=self):
            return

        # Resolve relative path if needed
        if not os.path.isabs(selected_conf):
            selected_conf = os.path.join(self.logic.base_dir, selected_conf)
            
        try:
            with open(selected_conf, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Parse settings
            new_settings = self.logic.parse_dosbox_conf_to_json(content)
            
            # Update game data
            self.game_data["dosbox_settings"] = new_settings
            
            # Refresh Treeview
            self.expert_tree.delete(*self.expert_tree.get_children())
            for section, keys in new_settings.items():
                for key, value in keys.items():
                    self.expert_tree.insert("", "end", values=(section, key, value))
            
            self._mark_as_changed()
            
            # Also refresh metadata to update version info etc.
            self._refresh_expert_metadata()
            
            if not silent:
                messagebox.showinfo("Reset Complete", "Expert settings have been reset to match the selected configuration.", parent=self)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to reset settings: {e}", parent=self)

    def _refresh_expert_metadata(self):
        selected_conf = self.selected_conf_var.get()
        if not selected_conf: return
        
        # Resolve relative path if needed
        if not os.path.isabs(selected_conf):
            abs_conf_path = os.path.join(self.logic.base_dir, selected_conf)
        else:
            abs_conf_path = selected_conf
        
        try:
            with open(abs_conf_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # 1. Load Values into Treeview (Auto-Reset)
            # We do NOT want to overwrite self.game_data["dosbox_settings"] if it already exists and has data!
            # But we need the reference settings to compare against.
            reference_settings = self.logic.parse_dosbox_conf_to_json(content)
            self.reference_settings = reference_settings # Store for later use
            
            # If dosbox_settings is empty (first load?), populate it.
            # But usually it's populated in _load_game_data.
            # If we are "refreshing" metadata, we probably just want to update the tree view tags.
            # However, the "Refresh" button implies reloading from the selected config.
            # If the user clicked Refresh, they might WANT to reset to that config?
            # But the function is also called on init.
            # Let's assume on init we keep existing settings, but on manual refresh we might ask?
            # For now, let's prioritize preserving user edits.
            
            current_settings = self.game_data.get("dosbox_settings", {})
            if not current_settings:
                self.game_data["dosbox_settings"] = reference_settings
                current_settings = reference_settings
            
            self.expert_tree.delete(*self.expert_tree.get_children())
            
            # We need to merge keys from reference and current to show everything
            all_sections = set(current_settings.keys()) | set(reference_settings.keys())
            
            for section in sorted(all_sections):
                curr_keys = current_settings.get(section, {})
                ref_keys = reference_settings.get(section, {})
                all_keys = set(curr_keys.keys()) | set(ref_keys.keys())
                
                for key in sorted(all_keys):
                    val = curr_keys.get(key, ref_keys.get(key)) # Default to ref if missing in curr
                    ref_val = ref_keys.get(key)
                    
                    # Insert
                    item_id = self.expert_tree.insert("", "end", values=(section, key, val))
                    
                    # Highlight if different
                    # Normalize for comparison (strings, lower case for bools if needed)
                    # DOSBox values are strings usually.
                    if str(val) != str(ref_val):
                        self.expert_tree.item(item_id, tags=("changed",))
                        
            self.expert_tree.tag_configure("changed", foreground="#ff5555") # Red color for changed
            
            # self._mark_as_changed() # Don't mark as changed just for refreshing view

            # 2. Detect Version & JSON
            # Determine effective variant based on configuration, not just file content
            variant, version = self.logic.detect_dosbox_version(content)
            
            # Override variant if custom path or default exe points to a specific engine
            custom_path = self.game_data.get("custom_dosbox_path", "")
            if custom_path:
                if "staging" in custom_path.lower(): variant = "dosbox-staging"
                elif "dosbox-x" in custom_path.lower(): variant = "dosbox-x"
            elif self.logic.default_dosbox_exe:
                if "staging" in self.logic.default_dosbox_exe.lower(): variant = "dosbox-staging"
                elif "dosbox-x" in self.logic.default_dosbox_exe.lower(): variant = "dosbox-x"
            
            self.detected_variant = variant # Store for Quick Settings
            self.current_metadata, json_name = self.logic.load_dosbox_metadata_json(variant)
            self.lbl_dosbox_version.config(text=f"Detected: {variant} ({version}) | Loaded: {json_name}")
            
            # Sanitize current settings against the detected variant
            # This ensures that if we switched engines, we map/remove incompatible keys
            if "dosbox_settings" in self.game_data:
                sanitized, remapped_keys = self.logic.sanitize_dosbox_settings(self.game_data["dosbox_settings"], variant)
                # Only update if changed to avoid unnecessary writes/refreshes if already clean
                if sanitized != self.game_data["dosbox_settings"] or remapped_keys:
                    self.game_data["dosbox_settings"] = sanitized
                    # We need to refresh the tree view again because data changed
                    self.expert_tree.delete(*self.expert_tree.get_children())
                    
                    # Re-populate tree with sanitized data
                    # We need to merge keys from reference and current to show everything
                    all_sections = set(sanitized.keys()) | set(reference_settings.keys())
                    
                    # Normalize remapped keys for checking
                    remapped_check = {(s.lower(), k.lower()) for s, k in remapped_keys}
                    
                    for section in sorted(all_sections):
                        curr_keys = sanitized.get(section, {})
                        ref_keys = reference_settings.get(section, {})
                        all_keys = set(curr_keys.keys()) | set(ref_keys.keys())
                        
                        for key in sorted(all_keys):
                            # Skip if key was remapped/removed
                            if (section.lower(), key.lower()) in remapped_check:
                                continue
                                
                            val = curr_keys.get(key, ref_keys.get(key))
                            ref_val = ref_keys.get(key)
                            
                            item_id = self.expert_tree.insert("", "end", values=(section, key, val))
                            if str(val) != str(ref_val):
                                self.expert_tree.item(item_id, tags=("changed",))
                    
                    self._mark_as_changed()

            # 3. Switch DOSBox Engine
            conf_dir = os.path.dirname(abs_conf_path)
            matched_inst_name = None
            local_dosbox_exe = None
            
            # Check if dosbox executable exists in the same folder as the config
            potential_exes = ["dosbox.exe", "dosbox-x.exe", "dosbox-staging.exe"]
            for exe in potential_exes:
                p = os.path.join(conf_dir, exe)
                if os.path.exists(p):
                    local_dosbox_exe = p
                    break

            if local_dosbox_exe:
                # If found, check if it matches a known installation
                for inst in self.dosbox_installations:
                    if os.path.normpath(inst.get('path', '')) == os.path.normpath(local_dosbox_exe):
                        matched_inst_name = inst.get('name')
                        break
            else:
                # Only if no local exe found, try other matching methods
                
                # Try to match by directory
                for inst in self.dosbox_installations:
                    inst_path = inst.get('path', '')
                    if not inst_path: continue
                    inst_dir = os.path.dirname(inst_path)
                    if os.path.normpath(conf_dir) == os.path.normpath(inst_dir):
                        matched_inst_name = inst.get('name')
                        break
                
                # Fallback: Try to match by variant name
                if not matched_inst_name:
                    for inst in self.dosbox_installations:
                        inst_name = inst.get('name', '').lower()
                        if variant.lower() in inst_name:
                            matched_inst_name = inst.get('name')
                            break

            if matched_inst_name:
                if hasattr(self, 'v_dosbox_path_name'): self.v_dosbox_path_name.set(matched_inst_name)
                # Also update custom_dosbox_path to match the selection
                self.game_data['custom_dosbox_path'] = next((inst['path'] for inst in self.dosbox_installations if inst['name'] == matched_inst_name), "")
            elif local_dosbox_exe:
                 # If we found a local exe but no matching installation name, we keep the custom path
                 if hasattr(self, 'v_dosbox_path_name'): self.v_dosbox_path_name.set(local_dosbox_exe)
                 self.game_data['custom_dosbox_path'] = local_dosbox_exe

            # Update the Info Label
            resolved_path = self.game_data.get("custom_dosbox_path", "")
            if not resolved_path: resolved_path = self.logic.default_dosbox_exe
            
            resolved_engine = "Unknown"
            if "staging" in resolved_path.lower(): resolved_engine = "DOSBox Staging"
            elif "dosbox-x" in resolved_path.lower(): resolved_engine = "DOSBox-X"
            elif "dosbox" in resolved_path.lower(): resolved_engine = "DOSBox (Standard)"
            
            info_text = f"Path: {truncate_text(resolved_path, 40)}"
            # Find the label widget in header (it's the last child of header frame usually, or we can store ref)
            # We didn't store a ref to the info label in _build_expert_tab easily accessible here?
            # Wait, we did: self.lbl_dosbox_version is the version label.
            # The info label was added as a plain label.
            # Let's find it. It's in 'header' frame.
            # Actually, we can just rebuild the label text if we had a ref.
            # I'll add a ref in _build_expert_tab first.
            if hasattr(self, 'lbl_expert_engine_info'):
                self.lbl_expert_engine_info.config(text=info_text)

        except Exception as e:
            print(f"Error refreshing metadata: {e}")
            self.lbl_dosbox_version.config(text="Error reading config")
            self.current_metadata = {}

    def _add_expert_param_dialog(self):
        # Load default config to get available options (structure)
        selected_conf = self.selected_conf_var.get()
        # Resolve relative path if needed
        if selected_conf and not os.path.isabs(selected_conf):
            selected_conf = os.path.join(self.logic.base_dir, selected_conf)
            
        default_conf = self.logic.get_default_dosbox_conf(self.game_data.get("custom_dosbox_path"), specific_conf_path=selected_conf)
        defaults = self.logic.parse_dosbox_conf_with_metadata(default_conf)
        
        # Use pre-loaded metadata from CSV
        csv_meta = getattr(self, 'current_metadata', {})
        
        # Get existing parameters to filter them out
        existing_params = set()
        for item in self.expert_tree.get_children():
            vals = self.expert_tree.item(item, "values")
            if vals and len(vals) >= 2:
                existing_params.add((vals[0], vals[1]))

        d = tb.Toplevel(self); d.title("Add Parameter"); d.geometry("600x600")
        
        tb.Label(d, text="Section:").pack(pady=5)
        
        # Filter sections to only those that have missing keys
        available_sections = []
        for sec in sorted(defaults.keys()):
            all_keys = defaults[sec].keys()
            # Check if there is at least one key in this section NOT in existing_params
            if any((sec, k) not in existing_params for k in all_keys):
                available_sections.append(sec)
                
        v_sec = tk.StringVar()
        cb_sec = tb.Combobox(d, textvariable=v_sec, values=available_sections, state="readonly")
        cb_sec.pack(pady=5)
        
        tb.Label(d, text="Key:").pack(pady=5)
        v_key = tk.StringVar()
        cb_key = tb.Combobox(d, textvariable=v_key, state="readonly")
        cb_key.pack(pady=5)
        
        tb.Label(d, text="Value:").pack(pady=5)
        v_val = tk.StringVar()
        cb_val = tb.Combobox(d, textvariable=v_val)
        cb_val.pack(pady=5)
        
        # Info Box
        info_frame = tb.Labelframe(d, text="Description & Options", bootstyle="info", padding=10)
        info_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        t_info = tk.Text(info_frame, wrap=tk.WORD, height=12, state="disabled", bg=d.cget("bg"))
        t_info.pack(fill=BOTH, expand=True)
        
        def update_info(sec, key):
            t_info.config(state="normal")
            t_info.delete("1.0", tk.END)
            
            # Look up in CSV metadata first (using lowercase for matching)
            meta = csv_meta.get(sec.lower(), {}).get(key.lower(), {})
            
            # Fallback to parsed data if not in CSV (though CSV is preferred)
            parsed_data = defaults.get(sec, {}).get(key, {})
            
            desc = meta.get("info", parsed_data.get("description", "No description available."))
            poss_list = meta.get("possible", parsed_data.get("possible_values_list", []))
            def_val = meta.get("default", parsed_data.get("value", "N/A"))
            
            poss_str = ", ".join(poss_list) if poss_list else "N/A"
            
            t_info.insert(tk.END, f"Default Value: {def_val}\n\n{desc}\n\nPossible Values: {poss_str}")
            
            # Update value combobox values
            if poss_list:
                cb_val.config(values=poss_list)
            else:
                cb_val.config(values=[])
                
            t_info.config(state="disabled")

        def on_sec_change(e):
            sec = v_sec.get()
            if sec in defaults:
                # Filter out keys that are already in the expert tree
                all_keys = defaults[sec].keys()
                keys = sorted([k for k in all_keys if (sec, k) not in existing_params])
                
                cb_key.config(values=keys)
                if keys: 
                    cb_key.current(0)
                    on_key_change(None)
                else:
                    v_key.set("")
                    v_val.set("")
                    cb_val.config(values=[])
                    t_info.config(state="normal")
                    t_info.delete("1.0", tk.END)
                    t_info.insert("1.0", "All parameters in this section are already added.")
                    t_info.config(state="disabled")
                
        def on_key_change(e):
            sec = v_sec.get(); key = v_key.get()
            # Set default value if available
            meta = csv_meta.get(sec.lower(), {}).get(key.lower(), {})
            if meta:
                 v_val.set(meta.get("default", ""))
            elif sec in defaults and key in defaults[sec]:
                v_val.set(defaults[sec][key]['value'])
            update_info(sec, key)
                
        cb_sec.bind("<<ComboboxSelected>>", on_sec_change)
        cb_key.bind("<<ComboboxSelected>>", on_key_change)
        
        if available_sections: cb_sec.current(0); on_sec_change(None)
        
        def add():
            s, k, v = v_sec.get(), v_key.get(), v_val.get()
            if s and k:
                # Check if exists
                exists = False
                for item in self.expert_tree.get_children():
                    vals = self.expert_tree.item(item, "values")
                    if vals[0] == s and vals[1] == k:
                        self.expert_tree.item(item, values=(s, k, v))
                        exists = True; break
                if not exists:
                    self.expert_tree.insert("", "end", values=(s, k, v))
                self._mark_as_changed()
                d.destroy()
                
        tb.Button(d, text="Add/Update", command=add, bootstyle="success").pack(pady=10)

    def _remove_expert_param(self):
        if sel := self.expert_tree.selection():
            self.expert_tree.delete(sel[0])
            self._mark_as_changed()

    def _edit_expert_param(self, event):
        if not (sel := self.expert_tree.selection()): return
        item = sel[0]
        vals = self.expert_tree.item(item, "values")
        sec, key, current_val = vals[0], vals[1], vals[2]
        
        # Check if window already open
        win_key = f"{sec}.{key}"
        if win_key in self.open_param_windows:
            try:
                self.open_param_windows[win_key].lift()
                self.open_param_windows[win_key].focus_force()
                return
            except tk.TclError:
                # Window might have been destroyed but not removed from dict
                del self.open_param_windows[win_key]
        
        # Load metadata
        selected_conf = self.selected_conf_var.get()
        # Resolve relative path if needed
        if selected_conf and not os.path.isabs(selected_conf):
            selected_conf = os.path.join(self.logic.base_dir, selected_conf)
            
        default_conf = self.logic.get_default_dosbox_conf(self.game_data.get("custom_dosbox_path"), specific_conf_path=selected_conf)
        defaults = self.logic.parse_dosbox_conf_with_metadata(default_conf)
        
        # Use pre-loaded metadata from CSV
        csv_meta = getattr(self, 'current_metadata', {})
        meta = csv_meta.get(sec.lower(), {}).get(key.lower(), {})
        
        # Fallback to parsed data
        parsed_data = defaults.get(sec, {}).get(key, {})
        
        desc = meta.get("info", parsed_data.get("description", "No description available."))
        poss_list = meta.get("possible", parsed_data.get("possible_values_list", []))
        def_val = meta.get("default", parsed_data.get("value", "N/A"))
        
        poss_str = ", ".join(poss_list) if poss_list else "N/A"
        
        d = tb.Toplevel(self); d.title(f"Edit {key}"); d.geometry("600x500")
        self.open_param_windows[win_key] = d
        
        def on_destroy(e):
            if e.widget == d and win_key in self.open_param_windows:
                del self.open_param_windows[win_key]
        d.bind("<Destroy>", on_destroy)
        
        tb.Label(d, text=f"Section: [{sec}]  Key: {key}", font="-weight bold").pack(pady=10)
        
        tb.Label(d, text="Value:").pack(anchor="w", padx=10)
        v_val = tk.StringVar(value=current_val)
        
        # Check if boolean
        is_bool = False
        if poss_list and len(poss_list) == 2:
            lower_poss = [str(p).lower() for p in poss_list]
            if "true" in lower_poss and "false" in lower_poss:
                is_bool = True
        
        if is_bool:
            # Use Checkbutton (Switch)
            chk = tb.Checkbutton(d, text="Enabled", variable=v_val, onvalue="true", offvalue="false", bootstyle="round-toggle")
            chk.pack(anchor="w", padx=10, pady=5)
            
            # Ensure current value is valid
            if str(current_val).lower() not in ["true", "false"]:
                v_val.set("false")
            else:
                v_val.set(str(current_val).lower())
        else:
            cb_val = tb.Combobox(d, textvariable=v_val)
            if poss_list: cb_val.config(values=poss_list)
            cb_val.pack(fill=X, padx=10, pady=5)
        
        info_frame = tb.Labelframe(d, text="Info", bootstyle="info", padding=10)
        info_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        t_info = tk.Text(info_frame, wrap=tk.WORD, height=12, bg=d.cget("bg"))
        t_info.insert("1.0", f"Default Value: {def_val}\n\n{desc}\n\nPossible Values: {poss_str}")
        t_info.config(state="disabled")
        t_info.pack(fill=BOTH, expand=True)
        
        def save():
            self.expert_tree.item(item, values=(sec, key, v_val.get()))
            self._mark_as_changed()
            d.destroy()
            
        tb.Button(d, text="Save", command=save, bootstyle="success").pack(pady=10)

    def _clear_custom_conf(self):
        # This method is replaced by _reset_to_default_dosbox but kept for safety if referenced elsewhere
        self._reset_to_default_dosbox()

    def _force_regenerate(self):
        if self.custom_conf_text.text.get("1.0", tk.END).strip() and not messagebox.askyesno("Overwrite?", "This will overwrite your custom edits. Continue?", parent=self): return
        self._update_custom_conf_preview()
        self._mark_as_changed()

    def _download_metadata(self):
        search_query = self.v_title.get().strip() or self.name.replace("_", " ")
        results = self.logic.db.search(search_query)
        
        if not results:
            messagebox.showinfo("No Results", f"No games found in offline database for '{search_query}'.", parent=self)
            return

        selected_game = None
        if len(results) == 1:
            if messagebox.askyesno("Game Found", f"Found: {results[0]['name']}\n\nApply metadata?", parent=self):
                selected_game = results[0]
        else:
            adapted_results = []
            for r in results:
                ts = 0
                try:
                    if r['year']: ts = datetime(int(r['year']), 1, 1).timestamp()
                except: pass
                adapted_results.append({'name': r['name'], 'first_release_date': ts, 'platforms': [{'name': 'DOS'}], '_original': r})
            
            dialog = GameSelectionDialog(self, adapted_results, game_name=search_query)
            self.wait_window(dialog)
            if dialog.result: selected_game = dialog.result['_original']

        if selected_game: self._apply_metadata(selected_game, None)

    def _apply_metadata(self, game_data, client):
        # Update Title
        if 'name' in game_data:
             self.v_title.set(game_data['name'])

        def update_if_empty_or_diff(var, new_val):
            if not new_val: return
            current = str(var.get()).strip()
            if not current or current == "0":
                var.set(new_val)
            elif current != str(new_val):
                # If different, we overwrite because user explicitly asked to "Download Metadata"
                var.set(new_val)

        if 'year' in game_data: update_if_empty_or_diff(self.v_year, game_data['year'])
        if 'genre' in game_data: update_if_empty_or_diff(self.v_genre, game_data['genre'])
        if 'developer' in game_data: update_if_empty_or_diff(self.v_developers, game_data['developer'])
        if 'publisher' in game_data: update_if_empty_or_diff(self.v_publishers, game_data['publisher'])
        if 'players' in game_data: update_if_empty_or_diff(self.v_num_players, game_data['players'])
        
        if 'description' in game_data and game_data['description']:
             current_desc = self.t_desc.get("1.0", tk.END).strip()
             if not current_desc or current_desc != game_data['description']:
                 self.t_desc.delete("1.0", tk.END)
                 self.t_desc.insert("1.0", game_data['description'])

        if 'rating' in game_data:
            try: stars = round(float(game_data['rating']))
            except: stars = 0
            if 0 <= stars <= 5: self.cb_rating.current(stars)
            
        # messagebox.showinfo("Success", "Metadata applied from offline database.", parent=self)
        self._mark_as_changed()

    def _sync_quick_settings_ui(self):
        """Updates Quick Settings tab widgets from current game_data."""
        # Prevent triggering change detection during sync
        was_loading = self.loading_data
        self.loading_data = True
        
        try:
            settings = self.game_data.get("dosbox_settings", {})
            cpu = settings.get("cpu", {})
            dosbox = settings.get("dosbox", {})
            dos = settings.get("dos", {})
            render = settings.get("render", {})
            sdl = settings.get("sdl", {})
            mixer = settings.get("mixer", {})
            extra = settings.get("extra", {})
            midi = settings.get("midi", {})
            sblaster = settings.get("sblaster", {})
            gus = settings.get("gus", {})
            
            # Detect Engine - STRICTLY based on loaded metadata if available
            is_staging = False
            is_x = False
            
            # Check if we have loaded metadata info (from Expert tab refresh)
            # This is the most reliable source as it comes from the actual loaded JSON file
            if hasattr(self, 'current_metadata') and hasattr(self, 'lbl_dosbox_version'):
                 # We can try to infer from the label text or store the loaded json name
                 # But let's re-detect from reference conf to be sure, similar to _build_simple_tab
                 pass

            # Re-run detection logic to ensure we are in sync with Expert tab
            ref_conf = self.game_data.get("reference_conf", "")
            variant = "dosbox-standard" # Default
            
            if ref_conf:
                if not os.path.isabs(ref_conf): ref_conf = os.path.join(self.logic.base_dir, ref_conf)
                if os.path.exists(ref_conf):
                    try:
                        with open(ref_conf, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        variant, _ = self.logic.detect_dosbox_version(content)
                    except: pass
            
            # Load metadata to get the strict filename check
            self.current_metadata, loaded_json_name = self.logic.load_dosbox_metadata_json(variant)
            
            if "staging" in loaded_json_name: is_staging = True
            elif "dosbox_x" in loaded_json_name: is_x = True
            
            # Update detected_variant for consistency
            self.detected_variant = "dosbox-staging" if is_staging else ("dosbox-x" if is_x else "dosbox-standard")

            if hasattr(self, 'v_mem'): self.v_mem.set(str(dosbox.get("memsize", "16")))
            
            if hasattr(self, 'v_xms'):
                val = dos.get("xms")
                if not val: val = dosbox.get("xms", "true")
                self.v_xms.set(str(val).lower() == "true")
                
            if hasattr(self, 'v_ems'):
                val = dos.get("ems")
                if not val: val = dosbox.get("ems", "true")
                self.v_ems.set(str(val))
                
            if hasattr(self, 'v_umb'):
                val = dos.get("umb")
                if not val: val = dosbox.get("umb", "true")
                self.v_umb.set(str(val).lower() == "true")
            
            # Update Visual Style Options
            if hasattr(self, 'cb_gfx'):
                if is_staging:
                    self.cb_gfx['values'] = constants.GLSHADER_OPTIONS
                    self.v_gfx.set(render.get("glshader", "none"))
                    # Re-bind to ensure correct key is used
                    self.cb_gfx.bind("<<ComboboxSelected>>", lambda e: self._update_setting_wrapper("render", "glshader", self.v_gfx.get()))
                else:
                    self.cb_gfx['values'] = constants.SCALER_OPTIONS
                    self.v_gfx.set(render.get("scaler", "none"))
                    # Re-bind to ensure correct key is used
                    self.cb_gfx.bind("<<ComboboxSelected>>", lambda e: self._update_setting_wrapper("render", "scaler", self.v_gfx.get()))

            if hasattr(self, 'v_core'): self.v_core.set(cpu.get("core", "auto"))
            if hasattr(self, 'v_cputype'): self.v_cputype.set(cpu.get("cputype", "auto"))
            
            # Update Cycles
            if hasattr(self, 'v_cycles'):
                # Always read from canonical 'cycles' if possible, or map back
                # But here we are reading FROM settings TO UI.
                if is_staging:
                    # Staging uses cpu_cycles
                    val = cpu.get("cpu_cycles")
                    if not val: val = cpu.get("cycles", "auto")
                    self.v_cycles.set(val)
                    if hasattr(self, 'lbl_cycles'): self.lbl_cycles.config(text="CPU Cycles:")
                else:
                    # Standard/X uses cycles
                    val = cpu.get("cycles")
                    if not val: val = cpu.get("cpu_cycles", "auto") # Fallback
                    self.v_cycles.set(val)
                    if hasattr(self, 'lbl_cycles'): self.lbl_cycles.config(text="Cycles:")

            # Update Protected Cycles Visibility
            if hasattr(self, 'f_cycles_prot'):
                if is_staging:
                    if getattr(self, 'has_dos4gw', False):
                        self.f_cycles_prot.grid()
                        if hasattr(self, 'lbl_dos4gw'): self.lbl_dos4gw.config(text="DOS4GW detected: Using Protected Cycles")
                        # Hide regular cycles
                        if hasattr(self, 'lbl_cycles'): self.lbl_cycles.grid_remove()
                        if hasattr(self, 'e_cycles'): self.e_cycles.grid_remove()
                    else:
                        self.f_cycles_prot.grid_remove()
                        if hasattr(self, 'lbl_cycles'): self.lbl_cycles.grid()
                        if hasattr(self, 'e_cycles'): self.e_cycles.grid()
                        
                    if hasattr(self, 'v_cycles_protected'): self.v_cycles_protected.set(cpu.get("cpu_cycles_protected", "auto"))
                else:
                    self.f_cycles_prot.grid_remove()
                    if hasattr(self, 'lbl_cycles'): self.lbl_cycles.grid()
                    if hasattr(self, 'e_cycles'): self.e_cycles.grid()

            if hasattr(self, 'v_fullscreen'): self.v_fullscreen.set(str(sdl.get("fullscreen", "false")).lower() == "true")
            if hasattr(self, 'v_fullres'): self.v_fullres.set(sdl.get("fullresolution", "desktop"))
            if hasattr(self, 'v_winres'): self.v_winres.set(sdl.get("windowresolution", "original"))
            
            if hasattr(self, 'v_intscale'): 
                self.v_intscale.set(render.get("integer_scaling", "off"))
                if hasattr(self, 'cb_intscale'):
                    self.cb_intscale.config(state="readonly" if is_staging else "disabled")
                    
            if hasattr(self, 'v_aspect'): 
                self.v_aspect.set(render.get("aspect", "false"))
                if hasattr(self, 'cb_aspect'):
                    aspect_options = self.current_metadata.get("render", {}).get("aspect", {}).get("possible", ["true", "false"])
                    self.cb_aspect['values'] = aspect_options

            if hasattr(self, 'v_sound'): self.v_sound.set(str(mixer.get("nosound", "false")).lower() == "false")
            
            if hasattr(self, 'v_loadfix'): self.v_loadfix.set(str(extra.get("loadfix", "false")).lower() == "true")
            if hasattr(self, 'v_loadfix_size'): self.v_loadfix_size.set(str(extra.get("loadfix_size", "64")))
            if hasattr(self, 'v_loadhigh'): self.v_loadhigh.set(str(extra.get("loadhigh", "false")).lower() == "true")
            
            if hasattr(self, 'v_mididevice'): self.v_mididevice.set(str(midi.get("mididevice", "default")))
            
            if hasattr(self, 'v_sbtype'): self.v_sbtype.set(str(sblaster.get("sbtype", "sb16")))
            if hasattr(self, 'v_sbbase'): self.v_sbbase.set(str(sblaster.get("sbbase", "220")))
            if hasattr(self, 'v_irq'): self.v_irq.set(str(sblaster.get("irq", "7")))
            if hasattr(self, 'v_dma'): self.v_dma.set(str(sblaster.get("dma", "1")))
            if hasattr(self, 'v_hdma'): self.v_hdma.set(str(sblaster.get("hdma", "5")))
            
            if hasattr(self, 'v_gus'): self.v_gus.set(str(gus.get("gus", "false")).lower() == "true")
            
            if hasattr(self, 'v_sensitivity'): self.v_sensitivity.set(str(sdl.get("sensitivity", "100")))
            if hasattr(self, 'v_autolock'): self.v_autolock.set(str(sdl.get("autolock", "true")).lower() == "true")
            
            if hasattr(self, 'v_rate'): self.v_rate.set(str(mixer.get("rate", "44100")))
            if hasattr(self, 'v_blocksize'): self.v_blocksize.set(str(mixer.get("blocksize", "1024")))
            if hasattr(self, 'v_prebuffer'): self.v_prebuffer.set(str(mixer.get("prebuffer", "20")))
        finally:
            self.loading_data = was_loading

    def _build_simple_tab(self, parent):
        # Detect Engine
        is_staging = False
        is_x = False
        
        # Priority 1: Use detected variant from Expert tab (most accurate as it parses the config)
        if hasattr(self, 'detected_variant') and self.detected_variant:
            if "staging" in self.detected_variant.lower(): is_staging = True
            elif "x" in self.detected_variant.lower() and "dosbox" not in self.detected_variant.lower(): is_x = True # "X"
            elif "dosbox-x" in self.detected_variant.lower(): is_x = True
        else:
            # Priority 2: Check custom path (User selection)
            path = self.game_data.get("custom_dosbox_path", "")
            if path:
                if "staging" in path.lower(): is_staging = True
                elif "dosbox-x" in path.lower(): is_x = True
            elif self.logic.default_dosbox_exe:
                # Priority 2.5: Check default exe
                if "staging" in self.logic.default_dosbox_exe.lower(): is_staging = True
                elif "dosbox-x" in self.logic.default_dosbox_exe.lower(): is_x = True
            else:
                # Priority 3: Fallback to reference conf
                ref_conf = self.game_data.get("reference_conf", "")
                if "staging" in ref_conf.lower(): is_staging = True
                elif "dosbox-x" in ref_conf.lower(): is_x = True
            
        # Load correct metadata based on engine
        variant = "dosbox-staging" if is_staging else ("dosbox-x" if is_x else "dosbox-standard")
        
        # The user requested to use the loaded JSON filename to determine the variant
        # self.logic.load_dosbox_metadata_json returns (metadata, filename)
        self.current_metadata, loaded_json_name = self.logic.load_dosbox_metadata_json(variant)
        
        # Determine strict variant from loaded JSON
        strict_variant = "standard"
        if "staging" in loaded_json_name: strict_variant = "staging"
        elif "dosbox_x" in loaded_json_name: strict_variant = "x"
        
        # Override is_staging/is_x based on strict_variant
        is_staging = (strict_variant == "staging")
        is_x = (strict_variant == "x")

        # Check for DOS4GW
        self.has_dos4gw = self.logic.game_has_dos4gw(self.name)

        # Load reference config for validation
        ref_parser = None
        ref_conf_path = self.game_data.get("reference_conf", "")
        if ref_conf_path:
            if not os.path.isabs(ref_conf_path): ref_conf_path = os.path.join(self.logic.base_dir, ref_conf_path)
            if os.path.exists(ref_conf_path):
                try:
                    from ..logic import DOSBoxConfigParser
                    ref_parser = DOSBoxConfigParser()
                    with open(ref_conf_path, 'r', encoding='utf-8', errors='ignore') as f:
                        ref_parser.parse(f.read())
                except: pass

        settings = self.game_data.get("dosbox_settings", {})
        cpu = settings.get("cpu", {})
        dosbox = settings.get("dosbox", {})
        dos = settings.get("dos", {})
        render = settings.get("render", {})
        sdl = settings.get("sdl", {})
        mixer = settings.get("mixer", {})
        extra = settings.get("extra", {})
        midi = settings.get("midi", {})
        sblaster = settings.get("sblaster", {})
        gus = settings.get("gus", {})
        
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = tb.Scrollbar(parent, orient="vertical", command=canvas.yview, bootstyle="round")
        scrollable_frame = tb.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Helper to update expert tree
        def update_expert_tree():
            if hasattr(self, 'expert_tree'):
                self._refresh_expert_tree_view()

        def update_setting(section, key, value):
            target_key = key
            target_section = section
            
            # Determine target variant for mapping
            target_variant = strict_variant
            
            # Load mapping
            mapping_path = os.path.join(self.logic.base_dir, "database", "mapping_functions.json")
            mapping = {}
            if os.path.exists(mapping_path):
                try:
                    with open(mapping_path, 'r', encoding='utf-8') as f: mapping = json.load(f)
                except: pass
            
            # Check mapping for the canonical key
            # We assume 'key' passed here is the canonical key (e.g. 'cycles')
            if section in mapping and key in mapping[section]:
                map_data = mapping[section][key].get(target_variant)
                if map_data and map_data.get("key"):
                    target_section = map_data.get("section", section)
                    target_key = map_data.get("key")
            
            # Double check against reference config if available to be safe
            if ref_parser:
                # If the mapped key exists, great.
                if ref_parser.get(target_section, target_key) is not None:
                    pass
                # If not, maybe the original key exists? (Fallback)
                elif ref_parser.get(section, key) is not None:
                    target_key = key
                    target_section = section
                # If neither exists, we should probably stick to the mapped key if we are confident about the variant,
                # OR we should not write it at all?
                # But if the user is adding a custom value, we should probably allow it but warn?
                # However, for Quick Settings, we are setting standard values.
                # If Staging is detected, we MUST use cpu_cycles, even if reference config is weird/missing it (unlikely for valid conf).
                # But if reference config is from a different version or broken...
                # Let's trust the mapping if we have a detected variant.
            
            if "dosbox_settings" not in self.game_data: self.game_data["dosbox_settings"] = {}
            if target_section not in self.game_data["dosbox_settings"]: self.game_data["dosbox_settings"][target_section] = {}
            
            # Remove conflicting keys if we are switching (e.g. cycles vs cpu_cycles)
            # This is important because we might have switched engines
            # We need to check ALL potential conflicting keys for this canonical key
            if section in mapping and key in mapping[section]:
                # Iterate all variants to find potential keys to remove
                for var_name, var_data in mapping[section][key].items():
                    if not var_data: continue
                    conflicting_key = var_data.get("key")
                    conflicting_section = var_data.get("section", section)
                    
                    # If the conflicting key is different OR the section is different, check for removal
                    if (conflicting_key and conflicting_key != target_key) or (conflicting_section and conflicting_section != target_section):
                        if conflicting_section in self.game_data["dosbox_settings"] and conflicting_key in self.game_data["dosbox_settings"][conflicting_section]:
                            del self.game_data["dosbox_settings"][conflicting_section][conflicting_key]
                            # Clean up empty section
                            if not self.game_data["dosbox_settings"][conflicting_section]:
                                del self.game_data["dosbox_settings"][conflicting_section]

            # Also handle the specific case where we might have manually set 'cycles' but now want 'cpu_cycles'
            # The loop above handles it if 'cycles' is in the mapping.
            
            self.game_data["dosbox_settings"][target_section][target_key] = value
            self._mark_as_changed()
            update_expert_tree()
            
        # Store update_setting as instance method wrapper to be accessible from _sync_quick_settings_ui
        self._update_setting_wrapper = update_setting

        # Grid Layout Configuration (3 Columns)
        scrollable_frame.columnconfigure(0, weight=1)
        scrollable_frame.columnconfigure(1, weight=1)
        scrollable_frame.columnconfigure(2, weight=1)

        # --- Variables Definition ---
        # Helper to get value from multiple sections (dos vs dosbox)
        def get_mem_val(key, default="true"):
            if key in dos: return dos[key]
            if key in dosbox: return dosbox[key]
            return default

        self.v_mem = tk.StringVar(value=str(dosbox.get("memsize", "16")))
        self.v_xms = tk.BooleanVar(value=(str(get_mem_val("xms")).lower() == "true"))
        self.v_ems = tk.StringVar(value=str(get_mem_val("ems", "true")))
        self.v_umb = tk.BooleanVar(value=(str(get_mem_val("umb")).lower() == "true"))
        
        # Compatibility
        self.v_loadfix = tk.BooleanVar(value=(str(extra.get("loadfix", "false")).lower() == "true"))
        self.v_loadfix_size = tk.StringVar(value=str(extra.get("loadfix_size", "64")))
        self.v_loadhigh = tk.BooleanVar(value=(str(extra.get("loadhigh", "false")).lower() == "true"))
        
        # Visual Style Logic
        if is_staging:
            gfx_key = "glshader"
            gfx_val = render.get("glshader", "none")
        else:
            gfx_key = "scaler"
            gfx_val = render.get("scaler", "none")
            
        self.v_gfx = tk.StringVar(value=gfx_val)
        
        self.v_core = tk.StringVar(value=cpu.get("core", "auto"))
        self.v_cputype = tk.StringVar(value=cpu.get("cputype", "auto"))
        
        self.v_fullscreen = tk.BooleanVar(value=(str(sdl.get("fullscreen", "false")).lower() == "true"))
        self.v_fullres = tk.StringVar(value=sdl.get("fullresolution", "desktop"))
        self.v_winres = tk.StringVar(value=sdl.get("windowresolution", "original"))
        self.v_intscale = tk.StringVar(value=render.get("integer_scaling", "off"))
        self.v_aspect = tk.StringVar(value=render.get("aspect", "false"))
        
        # Audio
        self.v_sound = tk.BooleanVar(value=(str(mixer.get("nosound", "false")).lower() == "false"))
        self.v_rate = tk.StringVar(value=str(mixer.get("rate", "44100")))
        self.v_blocksize = tk.StringVar(value=str(mixer.get("blocksize", "1024")))
        self.v_prebuffer = tk.StringVar(value=str(mixer.get("prebuffer", "20")))
        
        self.v_mididevice = tk.StringVar(value=str(midi.get("mididevice", "default")))
        
        self.v_sbtype = tk.StringVar(value=str(sblaster.get("sbtype", "sb16")))
        self.v_sbbase = tk.StringVar(value=str(sblaster.get("sbbase", "220")))
        self.v_irq = tk.StringVar(value=str(sblaster.get("irq", "7")))
        self.v_dma = tk.StringVar(value=str(sblaster.get("dma", "1")))
        self.v_hdma = tk.StringVar(value=str(sblaster.get("hdma", "5")))
        
        self.v_gus = tk.BooleanVar(value=(str(gus.get("gus", "false")).lower() == "true"))
        
        # Mouse
        self.v_sensitivity = tk.StringVar(value=str(sdl.get("sensitivity", "100")))
        self.v_autolock = tk.BooleanVar(value=(str(sdl.get("autolock", "true")).lower() == "true"))
        
        # Cycles
        cycles_val = cpu.get("cycles", "auto")
        if is_staging and "cpu_cycles" in cpu: cycles_val = cpu.get("cpu_cycles", "auto")
        self.v_cycles = tk.StringVar(value=str(cycles_val))
        self.v_cycles_protected = tk.StringVar(value=str(cpu.get("cpu_cycles_protected", "auto")))

        # Local references for convenience in this method
        v_mem, v_gfx, v_core, v_cputype = self.v_mem, self.v_gfx, self.v_core, self.v_cputype
        v_fullscreen, v_fullres, v_winres = self.v_fullscreen, self.v_fullres, self.v_winres
        v_intscale, v_aspect, v_sound = self.v_intscale, self.v_aspect, self.v_sound
        v_cycles, v_cycles_protected = self.v_cycles, self.v_cycles_protected

        # Check for DOS4GW.EXE
        self.has_dos4gw = False
        try:
            game_folder = os.path.join(self.logic.games_dir, self.name)
            if os.path.exists(game_folder):
                for root, dirs, files in os.walk(game_folder):
                    for file in files:
                        if file.upper() == "DOS4GW.EXE":
                            self.has_dos4gw = True
                            break
                    if self.has_dos4gw: break
        except Exception as e:
            # Fallback if logic.games_dir is not available directly (it is a property installed_dir in logic)
            # But wait, logic.games_dir is NOT a property in GameLogic class shown in read_file output.
            # It has installed_dir.
            try:
                game_folder = self.logic.find_game_folder(self.name)
                if os.path.exists(game_folder):
                    for root, dirs, files in os.walk(game_folder):
                        for file in files:
                            if file.upper() == "DOS4GW.EXE":
                                self.has_dos4gw = True
                                break
                        if self.has_dos4gw: break
            except:
                print(f"Error checking for DOS4GW: {e}")

        # 1. Performance Profile (Templates) - Row 0, Span 3
        f_perf = tb.Labelframe(scrollable_frame, text="Performance Profile (Templates)", bootstyle="primary", padding=10)
        f_perf.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        
        templates_dir = os.path.join(os.getcwd(), "database", "templates")
        if not os.path.exists(templates_dir): os.makedirs(templates_dir)
        template_files = [f for f in os.listdir(templates_dir) if f.lower().endswith(".conf")]
        
        v_template = tk.StringVar()

        def on_template_select(event=None):
            template_name = v_template.get()
            if not template_name: return
            
            template_path = os.path.join(templates_dir, template_name)
            if os.path.exists(template_path):
                try:
                    with open(template_path, 'r') as f:
                        content = f.read()
                    template_settings = self.logic.parse_dosbox_conf_to_json(content)
                    
                    # Apply template settings to game_data using update_setting to ensure mapping
                    for section, keys in template_settings.items():
                        for key, value in keys.items():
                            update_setting(section, key, value)
                    
                    # Update UI Variables
                    # We should read back from game_data to ensure we show what was actually set (mapped)
                    # But for simplicity, we can try to match what we just set.
                    # Actually, since update_setting updates game_data, we can just refresh UI from game_data?
                    # But _sync_quick_settings_ui is not fully implemented to read back everything.
                    # Let's stick to updating variables, but be smart about it.
                    
                    if "cpu" in template_settings:
                        if "core" in template_settings["cpu"]: v_core.set(template_settings["cpu"]["core"])
                        if "cputype" in template_settings["cpu"]: v_cputype.set(template_settings["cpu"]["cputype"])
                    
                    if "render" in template_settings:
                        if gfx_key in template_settings["render"]: v_gfx.set(template_settings["render"][gfx_key])
                        if "integer_scaling" in template_settings["render"]: v_intscale.set(template_settings["render"]["integer_scaling"])
                        if "aspect" in template_settings["render"]: v_aspect.set(template_settings["render"]["aspect"])
                        
                    if "sdl" in template_settings:
                        if "fullscreen" in template_settings["sdl"]: 
                            v_fullscreen.set(str(template_settings["sdl"]["fullscreen"]).lower() == "true")
                        if "fullresolution" in template_settings["sdl"]: v_fullres.set(template_settings["sdl"]["fullresolution"])
                        if "windowresolution" in template_settings["sdl"]: v_winres.set(template_settings["sdl"]["windowresolution"])
                        
                    if "dosbox" in template_settings:
                        if "memsize" in template_settings["dosbox"]: v_mem.set(template_settings["dosbox"]["memsize"])
                        
                    if "mixer" in template_settings:
                        if "nosound" in template_settings["mixer"]:
                             v_sound.set(str(template_settings["mixer"]["nosound"]).lower() == "false")
                            
                    self._mark_as_changed()
                    update_expert_tree()
                except Exception as e:
                    messagebox.showerror("Error", f"Error loading template: {e}", parent=self)

        if template_files:
            tb.Label(f_perf, text="Select a template to apply settings:", bootstyle="secondary").pack(anchor="w", pady=(0, 5))
            cb_templates = tb.Combobox(f_perf, textvariable=v_template, values=template_files, state="readonly")
            cb_templates.pack(fill=tk.X, pady=5)
            cb_templates.bind("<<ComboboxSelected>>", on_template_select)
        else:
            tb.Label(f_perf, text="No templates found in 'templates' folder.", bootstyle="warning").pack(anchor="w")

        # 2. CPU Options - Row 1, Col 0 (Rowspan 3)
        f_cpu = tb.Labelframe(scrollable_frame, text="CPU Options", bootstyle="warning", padding=10)
        f_cpu.grid(row=1, column=0, rowspan=3, sticky="nsew", padx=10, pady=10)
        f_cpu.columnconfigure(1, weight=1)

        # Core
        tb.Label(f_cpu, text="Core:").grid(row=0, column=0, sticky="w", pady=5)
        core_options = self.current_metadata.get("cpu", {}).get("core", {}).get("possible", ["auto", "dynamic", "normal", "simple"])
        cb_core = tb.Combobox(f_cpu, textvariable=v_core, values=core_options, state="readonly")
        cb_core.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        cb_core.bind("<<ComboboxSelected>>", lambda e: update_setting("cpu", "core", v_core.get()))

        # CPU Type
        tb.Label(f_cpu, text="CPU Type:").grid(row=1, column=0, sticky="w", pady=5)
        cputype_options = self.current_metadata.get("cpu", {}).get("cputype", {}).get("possible", ["auto", "386", "486", "pentium", "386_prefetch"])
        cb_cputype = tb.Combobox(f_cpu, textvariable=v_cputype, values=cputype_options, state="readonly")
        cb_cputype.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        cb_cputype.bind("<<ComboboxSelected>>", lambda e: update_setting("cpu", "cputype", v_cputype.get()))

        # Cycles
        cycles_label = "CPU Cycles:" if is_staging else "Cycles:"
        self.lbl_cycles = tb.Label(f_cpu, text=cycles_label)
        self.lbl_cycles.grid(row=2, column=0, sticky="w", pady=5)
        self.e_cycles = tb.Entry(f_cpu, textvariable=v_cycles)
        self.e_cycles.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        
        # Protected Cycles (Container Frame for visibility toggling)
        self.f_cycles_prot = tb.Frame(f_cpu)
        self.f_cycles_prot.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.f_cycles_prot.columnconfigure(1, weight=1)
        
        tb.Label(self.f_cycles_prot, text="Protected Cycles:").grid(row=0, column=0, sticky="w", pady=5)
        e_cycles_prot = tb.Entry(self.f_cycles_prot, textvariable=v_cycles_protected)
        e_cycles_prot.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        # Info label for DOS4GW
        self.lbl_dos4gw = tb.Label(self.f_cycles_prot, text="", font="-size 8", bootstyle="info")
        self.lbl_dos4gw.grid(row=1, column=0, columnspan=2, sticky="w", padx=5)

        # Initial Visibility
        if is_staging:
            # Staging Logic:
            # If DOS4GW is present: Show Protected Cycles, Hide Regular Cycles
            # If DOS4GW is NOT present: Show Regular Cycles, Hide Protected Cycles
            if self.has_dos4gw:
                self.lbl_dos4gw.config(text="DOS4GW detected: Using Protected Cycles")
                self.lbl_cycles.grid_remove()
                self.e_cycles.grid_remove()
                self.f_cycles_prot.grid()
                
                # Ensure cpu_cycles is auto (or default) if we are in protected mode
                # We do this silently on load/switch
                # But we should be careful not to overwrite user's manual setting if they switched back and forth?
                # The user said: "zapisujeme LEN cpu_cycles_protected.. ak tam DOS4GW nie je, tak potom zapisujeme LEN cpu_cycles"
                # This implies we should probably clear or reset the other one?
                # For now, let's just ensure the UI reflects what is editable.
            else:
                self.f_cycles_prot.grid_remove()
                self.lbl_cycles.grid()
                self.e_cycles.grid()
                
                # If we are not in protected mode, we hide protected cycles.
        else:
            # Standard / X Logic:
            # Show Regular Cycles (mapped to 'cycles' or 'cpu_cycles' depending on variant, but here we use canonical 'cycles')
            # Hide Protected Cycles
            self.f_cycles_prot.grid_remove()
            self.lbl_cycles.grid()
            self.e_cycles.grid()
            
            # Also update label text
            self.lbl_cycles.config(text="CPU Cycles:") # Standard/X uses "cycles" but label can be "CPU Cycles"

        # Traces
        
        def on_cycles_change(*args):
            val = v_cycles.get()
            # Use canonical key 'cycles' and let update_setting handle mapping
            update_setting("cpu", "cycles", val)

        def on_cycles_prot_change(*args):
            val = v_cycles_protected.get()
            update_setting("cpu", "cpu_cycles_protected", val)
            # If we are editing protected cycles, we are in Staging+DOS4GW mode.
            # We should ensure cpu_cycles is set to something safe (like auto) or removed?
            # User said: "zapisujeme LEN cpu_cycles_protected"
            # So we might want to ensure 'cpu_cycles' is not set to a conflicting fixed value?
            # But 'auto' is safe.
            if is_staging and self.has_dos4gw:
                 update_setting("cpu", "cycles", "auto")

        # Use bind instead of trace to avoid circular updates or unwanted triggers
        self.e_cycles.bind("<FocusOut>", on_cycles_change)
        self.e_cycles.bind("<Return>", on_cycles_change)
        e_cycles_prot.bind("<FocusOut>", on_cycles_prot_change)
        e_cycles_prot.bind("<Return>", on_cycles_prot_change)

        # 3. Display Options - Row 1, Col 1 (Rowspan 3)
        f_disp = tb.Labelframe(scrollable_frame, text="Display Options", bootstyle="warning", padding=10)
        f_disp.grid(row=1, column=1, rowspan=3, sticky="nsew", padx=10, pady=10)
        f_disp.columnconfigure(1, weight=1)

        # Fullscreen (Toggle)
        tb.Label(f_disp, text="Fullscreen:").grid(row=0, column=0, sticky="w", pady=5)
        def on_fullscreen_change():
            val = "true" if v_fullscreen.get() else "false"
            update_setting("sdl", "fullscreen", val)
        tb.Checkbutton(f_disp, text="Enable", variable=v_fullscreen, bootstyle="round-toggle", command=on_fullscreen_change).grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Fullresolution
        tb.Label(f_disp, text="Full Resolution:").grid(row=1, column=0, sticky="w", pady=5)
        e_fullres = tb.Entry(f_disp, textvariable=v_fullres)
        e_fullres.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        v_fullres.trace("w", lambda *a: update_setting("sdl", "fullresolution", v_fullres.get()))

        # Windowresolution
        tb.Label(f_disp, text="Window Resolution:").grid(row=2, column=0, sticky="w", pady=5)
        e_winres = tb.Entry(f_disp, textvariable=v_winres)
        e_winres.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        v_winres.trace("w", lambda *a: update_setting("sdl", "windowresolution", v_winres.get()))

        # Integer Scaling
        tb.Label(f_disp, text="Integer Scaling:").grid(row=3, column=0, sticky="w", pady=5)
        intscale_options = ["auto", "vertical", "horizontal", "off"]
        intscale_state = "readonly" if is_staging else "disabled"
        self.cb_intscale = tb.Combobox(f_disp, textvariable=v_intscale, values=intscale_options, state=intscale_state)
        self.cb_intscale.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        self.cb_intscale.bind("<<ComboboxSelected>>", lambda e: update_setting("render", "integer_scaling", v_intscale.get()))

        # Aspect
        tb.Label(f_disp, text="Aspect:").grid(row=4, column=0, sticky="w", pady=5)
        aspect_options = self.current_metadata.get("render", {}).get("aspect", {}).get("possible", ["true", "false"])
        self.cb_aspect = tb.Combobox(f_disp, textvariable=v_aspect, values=aspect_options, state="readonly")
        self.cb_aspect.grid(row=4, column=1, sticky="ew", padx=5, pady=5)
        self.cb_aspect.bind("<<ComboboxSelected>>", lambda e: update_setting("render", "aspect", v_aspect.get()))

        # 4. Right Column Stack (Memory, Visual, Audio) - Col 2
        
        # Memory (RAM) - Row 1, Col 2
        f_mem = tb.Labelframe(scrollable_frame, text="Memory (RAM)", bootstyle="info", padding=10)
        f_mem.grid(row=1, column=2, sticky="nsew", padx=10, pady=10)
        
        mem_options = ["1", "4", "8", "16", "32", "64", "128", "256"]
        cb_mem = tb.Combobox(f_mem, textvariable=v_mem, values=mem_options, state="readonly")
        cb_mem.pack(fill=tk.X, pady=5)
        cb_mem.bind("<<ComboboxSelected>>", lambda e: update_setting("dosbox", "memsize", v_mem.get()))
        
        # Extended Memory Options
        f_mem_ext = tb.Frame(f_mem)
        f_mem_ext.pack(fill=X, pady=5)
        
        def update_bool(sec, key, var):
            val = "true" if var.get() else "false"
            update_setting(sec, key, val)
            
        # Use 'dos' section for XMS/EMS/UMB as per mapping_functions.json
        tb.Checkbutton(f_mem_ext, text="XMS", variable=self.v_xms, bootstyle="round-toggle", command=lambda: update_bool("dos", "xms", self.v_xms)).pack(side=LEFT, padx=5)
        
        # EMS as Combobox
        f_ems = tb.Frame(f_mem_ext)
        f_ems.pack(side=LEFT, padx=5)
        tb.Label(f_ems, text="EMS:").pack(side=LEFT)
        ems_opts = ["true", "emsboard", "emm386", "false"]
        cb_ems = tb.Combobox(f_ems, textvariable=self.v_ems, values=ems_opts, state="readonly", width=8)
        cb_ems.pack(side=LEFT, padx=2)
        cb_ems.bind("<<ComboboxSelected>>", lambda e: update_setting("dos", "ems", self.v_ems.get()))

        tb.Checkbutton(f_mem_ext, text="UMB", variable=self.v_umb, bootstyle="round-toggle", command=lambda: update_bool("dos", "umb", self.v_umb)).pack(side=LEFT, padx=5)

        # Compatibility - Row 2, Col 2
        f_compat = tb.Labelframe(scrollable_frame, text="Compatibility", bootstyle="secondary", padding=10)
        f_compat.grid(row=2, column=2, sticky="nsew", padx=10, pady=10)
        
        # Loadfix
        f_loadfix = tb.Frame(f_compat)
        f_loadfix.pack(fill=X, pady=2)
        tb.Checkbutton(f_loadfix, text="Loadfix", variable=self.v_loadfix, bootstyle="round-toggle", command=lambda: update_bool("extra", "loadfix", self.v_loadfix)).pack(side=LEFT)
        tb.Label(f_loadfix, text="Size (KB):").pack(side=LEFT, padx=(10, 5))
        e_loadfix = tb.Entry(f_loadfix, textvariable=self.v_loadfix_size, width=5)
        e_loadfix.pack(side=LEFT)
        e_loadfix.bind("<FocusOut>", lambda e: update_setting("extra", "loadfix_size", self.v_loadfix_size.get()))
        e_loadfix.bind("<Return>", lambda e: update_setting("extra", "loadfix_size", self.v_loadfix_size.get()))
        
        # LoadHigh
        tb.Checkbutton(f_compat, text="LoadHigh (LH)", variable=self.v_loadhigh, bootstyle="round-toggle", command=lambda: update_bool("extra", "loadhigh", self.v_loadhigh)).pack(anchor="w", pady=2)

        # Visual Style - Row 3, Col 2
        f_gfx = tb.Labelframe(scrollable_frame, text="Visual Style", bootstyle="success", padding=10)
        f_gfx.grid(row=3, column=2, sticky="nsew", padx=10, pady=10)
        
        gfx_options = self.current_metadata.get("render", {}).get(gfx_key, {}).get("possible", [])
        if not gfx_options: 
            if is_staging:
                gfx_options = constants.GLSHADER_OPTIONS
            else:
                gfx_options = constants.SCALER_OPTIONS
                
        self.cb_gfx = tb.Combobox(f_gfx, textvariable=v_gfx, values=gfx_options, state="readonly")
        self.cb_gfx.pack(fill=tk.X, pady=5)
        self.cb_gfx.bind("<<ComboboxSelected>>", lambda e: update_setting("render", gfx_key, v_gfx.get()))

        # Audio - Row 4, Col 0-2 (Full Width)
        f_audio = tb.Labelframe(scrollable_frame, text="Audio Settings", bootstyle="secondary", padding=10)
        f_audio.grid(row=4, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        
        # Main Sound Toggle
        def on_audio_change():
            val = "false" if v_sound.get() else "true"
            update_setting("mixer", "nosound", val)
            
        tb.Checkbutton(f_audio, text="Enable Master Sound", variable=v_sound, bootstyle="round-toggle", command=on_audio_change).grid(row=0, column=0, sticky="w", pady=5)
        
        # Mixer Settings
        f_mixer = tb.Frame(f_audio)
        f_mixer.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)
        
        tb.Label(f_mixer, text="Rate:").pack(side=LEFT, padx=(0,5))
        tb.Entry(f_mixer, textvariable=self.v_rate, width=8).pack(side=LEFT, padx=(0,10))
        self.v_rate.trace("w", lambda *a: update_setting("mixer", "rate", self.v_rate.get()))
        
        tb.Label(f_mixer, text="Blocksize:").pack(side=LEFT, padx=(0,5))
        tb.Entry(f_mixer, textvariable=self.v_blocksize, width=6).pack(side=LEFT, padx=(0,10))
        self.v_blocksize.trace("w", lambda *a: update_setting("mixer", "blocksize", self.v_blocksize.get()))
        
        tb.Label(f_mixer, text="Prebuffer:").pack(side=LEFT, padx=(0,5))
        tb.Entry(f_mixer, textvariable=self.v_prebuffer, width=6).pack(side=LEFT)
        self.v_prebuffer.trace("w", lambda *a: update_setting("mixer", "prebuffer", self.v_prebuffer.get()))
        
        # MIDI
        tb.Label(f_audio, text="MIDI Device:").grid(row=2, column=0, sticky="w", pady=5)
        midi_opts = self.current_metadata.get("midi", {}).get("mididevice", {}).get("possible", ["default", "win32", "alsa", "oss", "coreaudio", "coremidi", "none"])
        cb_midi = tb.Combobox(f_audio, textvariable=self.v_mididevice, values=midi_opts)
        cb_midi.grid(row=2, column=1, sticky="ew", padx=5)
        cb_midi.bind("<<ComboboxSelected>>", lambda e: update_setting("midi", "mididevice", self.v_mididevice.get()))
        cb_midi.bind("<FocusOut>", lambda e: update_setting("midi", "mididevice", self.v_mididevice.get()))
        
        # SoundBlaster
        f_sb = tb.Labelframe(f_audio, text="SoundBlaster", padding=5)
        f_sb.grid(row=3, column=0, columnspan=3, sticky="ew", pady=5)
        
        tb.Label(f_sb, text="Type:").pack(side=LEFT, padx=(0,5))
        sb_opts = self.current_metadata.get("sblaster", {}).get("sbtype", {}).get("possible", ["sb16", "sbpro1", "sbpro2", "sb2", "sb1", "none"])
        cb_sb = tb.Combobox(f_sb, textvariable=self.v_sbtype, values=sb_opts, width=10, state="readonly")
        cb_sb.pack(side=LEFT, padx=(0,10))
        cb_sb.bind("<<ComboboxSelected>>", lambda e: update_setting("sblaster", "sbtype", self.v_sbtype.get()))
        
        tb.Label(f_sb, text="Addr:").pack(side=LEFT, padx=(0,2))
        sbbase_opts = ["220", "240", "260", "280", "2a0", "2c0", "300"]
        cb_sbbase = tb.Combobox(f_sb, textvariable=self.v_sbbase, values=sbbase_opts, width=5, state="readonly")
        cb_sbbase.pack(side=LEFT, padx=(0,5))
        cb_sbbase.bind("<<ComboboxSelected>>", lambda e: update_setting("sblaster", "sbbase", self.v_sbbase.get()))
        
        tb.Label(f_sb, text="IRQ:").pack(side=LEFT, padx=(0,2))
        irq_opts = ["3", "5", "7", "9", "10", "11", "12"]
        cb_irq = tb.Combobox(f_sb, textvariable=self.v_irq, values=irq_opts, width=3, state="readonly")
        cb_irq.pack(side=LEFT, padx=(0,5))
        cb_irq.bind("<<ComboboxSelected>>", lambda e: update_setting("sblaster", "irq", self.v_irq.get()))
        
        tb.Label(f_sb, text="DMA:").pack(side=LEFT, padx=(0,2))
        dma_opts = ["0", "1", "3", "5", "6", "7"]
        cb_dma = tb.Combobox(f_sb, textvariable=self.v_dma, values=dma_opts, width=3, state="readonly")
        cb_dma.pack(side=LEFT, padx=(0,5))
        cb_dma.bind("<<ComboboxSelected>>", lambda e: update_setting("sblaster", "dma", self.v_dma.get()))
        
        tb.Label(f_sb, text="HDMA:").pack(side=LEFT, padx=(0,2))
        hdma_opts = ["0", "1", "3", "5", "6", "7"]
        cb_hdma = tb.Combobox(f_sb, textvariable=self.v_hdma, values=hdma_opts, width=3, state="readonly")
        cb_hdma.pack(side=LEFT)
        cb_hdma.bind("<<ComboboxSelected>>", lambda e: update_setting("sblaster", "hdma", self.v_hdma.get()))
        
        # GUS
        tb.Checkbutton(f_audio, text="Enable Gravis Ultrasound (GUS)", variable=self.v_gus, bootstyle="round-toggle", command=lambda: update_bool("gus", "gus", self.v_gus)).grid(row=4, column=0, columnspan=2, sticky="w", pady=5)

    def _build_general_tab(self, parent):
        parent.columnconfigure(0, weight=1); parent.columnconfigure(1, weight=2); parent.rowconfigure(2, weight=1)
        left_frame = tb.Frame(parent, padding=10); left_frame.grid(row=0, rowspan=3, column=0, sticky='nsew', padx=(0, 5)); left_frame.columnconfigure(1, weight=1)
        right_frame = tb.Frame(parent, padding=10); right_frame.grid(row=0, rowspan=3, column=1, sticky='nsew', padx=(5, 0)); right_frame.columnconfigure(1, weight=1); right_frame.rowconfigure(1, weight=1)
        f_top_left = tb.Frame(left_frame); f_top_left.grid(row=0, column=0, columnspan=2, sticky="ew"); tb.Label(f_top_left, text="Game Title:").pack(side=tk.LEFT)
        self.v_title = tk.StringVar(value=self.game_data.get("title", self.name)); entry = tb.Entry(left_frame, textvariable=self.v_title); entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=2); entry.bind("<KeyRelease>", self._mark_as_changed)
        
        btn_frame = tb.Frame(left_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        btn_frame.columnconfigure(0, weight=1); btn_frame.columnconfigure(1, weight=1); btn_frame.columnconfigure(2, weight=1)
        tb.Button(btn_frame, text="Info (Web)", command=self._open_browser_search, bootstyle="info-outline").grid(row=0, column=0, sticky="ew", padx=(0, 2))
        
        # Check database existence
        db_exists = os.path.exists(os.path.join(os.getcwd(), "database", "DOSmetainfo.csv"))
        state = "normal" if db_exists else "disabled"
        tb.Button(btn_frame, text="Download Metadata", command=self._download_metadata, bootstyle="primary-outline", state=state).grid(row=0, column=1, sticky="ew", padx=(2, 2))
        
        tb.Button(btn_frame, text="Clean Metadata", command=self._clean_metadata, bootstyle="warning-outline").grid(row=0, column=2, sticky="ew", padx=(2, 0))

        self.v_year = self._add_entry_to_frame(left_frame, 3, "Year:", self.game_data, "year"); self.v_genre = self._add_combobox_to_frame(left_frame, 4, "Genre:", self.game_data, "genre", constants.GENRE_OPTIONS)
        self.v_developers = self._add_entry_to_frame(left_frame, 5, "Developers:", self.game_data, "developers"); self.v_publishers = self._add_entry_to_frame(left_frame, 6, "Publishers:", self.game_data, "publishers"); self.v_num_players = self._add_entry_to_frame(left_frame, 7, "Number of Players:", self.game_data, "num_players")
        tb.Label(left_frame, text="User Rating:").grid(row=8, column=0, sticky='w', pady=(10,2)); self.cb_rating = tb.Combobox(left_frame, values=["0 Stars"] + [f"{i} Stars" for i in range(1,6)], state='readonly'); self.cb_rating.grid(row=8, column=1, sticky='ew', pady=(10,2)); self.cb_rating.current(self.game_data.get("rating", 0)); self.cb_rating.bind("<<ComboboxSelected>>", self._mark_as_changed)
        self.v_critics_score = self._add_spinbox_to_frame(left_frame, 9, 0, self.game_data, "critics_score", 0, 100, label_text="Critics Score (%):")
        tb.Label(right_frame, text="Description:").grid(row=0, column=0, columnspan=2, sticky='w'); self.t_desc = tk.Text(right_frame, height=8, wrap=tk.WORD); self.t_desc.grid(row=1, column=0, columnspan=2, sticky="nsew"); self.t_desc.insert(tk.END, self.game_data.get("description", "")); self.t_desc.bind("<KeyRelease>", self._mark_as_changed)
        video_labelframe = tb.Labelframe(right_frame, text="Video Links", bootstyle="info", padding=5); video_labelframe.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=10); video_labelframe.rowconfigure(0, weight=1); video_labelframe.columnconfigure(0, weight=1)
        tree_container = tb.Frame(video_labelframe); tree_container.grid(row=0, column=0, sticky="nsew"); tree_container.rowconfigure(0, weight=1); tree_container.columnconfigure(0, weight=1)
        self.video_tree = tb.Treeview(tree_container, columns=("title", "url"), show="headings", selectmode="browse", height=4); self.video_tree.heading("title", text="Video Title"); self.video_tree.heading("url", text="URL"); self.video_tree.column("title", width=150, stretch=True); self.video_tree.column("url", width=250, stretch=True); self.video_tree.grid(row=0, column=0, sticky="nsew"); v_scroll = tb.Scrollbar(tree_container, orient="vertical", command=self.video_tree.yview, bootstyle="round"); v_scroll.grid(row=0, column=1, sticky="ns"); self.video_tree.configure(yscrollcommand=v_scroll.set); self._load_videos()
        video_buttons_frame = tb.Frame(video_labelframe); video_buttons_frame.grid(row=1, column=0, sticky="e", pady=(5,0)); tb.Button(video_buttons_frame, text="▶️ Find on YouTube", command=self._search_youtube, bootstyle="danger-outline").pack(side=tk.LEFT, padx=(0,10)); tb.Button(video_buttons_frame, text="Fetch Titles", command=self._fetch_titles, bootstyle="primary-outline").pack(side=tk.LEFT, padx=(0,10)); tb.Button(video_buttons_frame, text="Add", command=self._add_video, bootstyle="success").pack(side=tk.LEFT, padx=5); tb.Button(video_buttons_frame, text="Edit", command=self._edit_video, bootstyle="warning").pack(side=tk.LEFT, padx=5); tb.Button(video_buttons_frame, text="Remove", command=self._remove_video, bootstyle="danger").pack(side=tk.LEFT)
        custom_header_frame = tb.Frame(right_frame); custom_header_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(10,0)); tb.Label(custom_header_frame, text="Custom Fields (key:value per line):").pack(side=tk.LEFT, anchor='sw'); self.btn_quick_search = tb.Button(custom_header_frame, text="🌐 Quick Search...", command=self._show_quick_search_menu, bootstyle="info-outline"); self.btn_quick_search.pack(side=tk.RIGHT, anchor='se')
        self.t_custom = tk.Text(right_frame, height=6, wrap=tk.WORD); self.t_custom.grid(row=4, column=0, columnspan=2, sticky="ew", pady=2); self.t_custom.insert(tk.END, "\n".join([f"{k}:{v}" for k, v in self.game_data.get("custom_fields", {}).items()])); self.t_custom.bind("<KeyRelease>", self._mark_as_changed)

    def _clean_metadata(self):
        if messagebox.askyesno("Clean Metadata", "Are you sure you want to clear Year, Genre, Developers, Publishers, Number of Players, and Description?", parent=self):
            self.v_year.set("")
            self.v_genre.set("")
            self.v_developers.set("")
            self.v_publishers.set("")
            self.v_num_players.set("")
            self.t_desc.delete("1.0", tk.END)
            self._mark_as_changed()

    def _show_quick_search_menu(self):
        game_title = self.v_title.get() or self.name.replace("_", " "); menu = tb.Menu(self, tearoff=0)
        for label, query in {"Walkthrough": f"{game_title} walkthrough", "Cheats": f"{game_title} cheats", "Manual": f"{game_title} manual pdf", "MobyGames": f"{game_title} dos mobygames"}.items(): menu.add_command(label=f"Search for {label}", command=lambda u=f"https://www.google.com/search?q={quote_plus(query)}": webbrowser.open(u))
        menu.post(self.btn_quick_search.winfo_rootx(), self.btn_quick_search.winfo_rooty() + self.btn_quick_search.winfo_height())
    def _load_videos(self): self.video_tree.delete(*self.video_tree.get_children()); [self.video_tree.insert("", "end", values=(video_info.get("title", ""), video_info.get("url", ""))) for video_info in self.game_data.get("video_links", []) if isinstance(video_info, dict)]
    def _add_video(self):
        try:
            content = self.clipboard_get().strip()
            if "youtube.com/" in content or "youtu.be/" in content:
                existing_urls = [self.video_tree.item(i, "values")[1] for i in self.video_tree.get_children()]
                if content not in existing_urls: self.video_tree.insert("", "end", values=("", content)); self._mark_as_changed()
                else: messagebox.showwarning("Duplicate Video", "This video URL is already in the list.", parent=self)
                return
        except tk.TclError: pass
        dialog = VideoLinkDialog(self, title="Add New Video Link"); self.wait_window(dialog)
        if dialog.result:
            existing_urls = [self.video_tree.item(i, "values")[1] for i in self.video_tree.get_children()]
            if dialog.result["url"] not in existing_urls: self.video_tree.insert("", "end", values=(dialog.result["title"], dialog.result["url"])); self._mark_as_changed()
            else: messagebox.showwarning("Duplicate Video", "This video URL is already in the list.", parent=self)

    def _edit_video(self):
        if not (selected_item := self.video_tree.selection()): return
        item_values = self.video_tree.item(selected_item[0], "values"); video_info = {"title": item_values[0], "url": item_values[1]}; dialog = VideoLinkDialog(self, title="Edit Video Link", video_info=video_info); self.wait_window(dialog)
        if dialog.result: self.video_tree.item(selected_item[0], values=(dialog.result["title"], dialog.result["url"])); self._mark_as_changed()
    def _remove_video(self):
        if selected_item := self.video_tree.selection(): self.video_tree.delete(selected_item[0]); self._mark_as_changed()
    def _clean_yt_url(self, url):
        if 'youtube.com' not in url and 'youtu.be' not in url: return url
        try: parsed_url = urlparse(url); video_id_list = parse_qs(parsed_url.query).get('v'); return f"https://www.youtube.com/watch?v={video_id_list[0]}" if video_id_list else url
        except Exception: return url
    def _fetch_titles(self):
        updated_count = 0
        for item_id in self.video_tree.get_children():
            values = self.video_tree.item(item_id, "values"); current_title, url = values[0], values[1]
            try:
                clean_url = self._clean_yt_url(url); request = urllib.request.Request(clean_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(request) as response: html_content = response.read().decode('utf-8', errors='ignore')
                if match := re.search(r"<title>(.*?)</title>", html_content):
                    new_title = match.group(1).replace("- YouTube", "").strip()
                    if new_title and new_title != current_title and (not current_title or messagebox.askyesno("Update Title?", f"Found new title for:\n{url}\n\nOld: '{current_title}'\nNew: '{new_title}'\n\nDo you want to replace it?", parent=self)): self.video_tree.item(item_id, values=(new_title, clean_url)); updated_count += 1
            except Exception as e: print(f"Could not fetch title for {url}: {e}")
        if updated_count > 0: messagebox.showinfo("Fetch Complete", f"{updated_count} video title(s) updated.", parent=self); self._mark_as_changed()
        else: messagebox.showinfo("Fetch Complete", "No titles needed updating or no new titles were accepted.", parent=self)
    def _search_youtube(self): webbrowser.open_new_tab(f"https://www.youtube.com/results?search_query={quote_plus(f'{(self.v_title.get() or self.name.replace('_', ' '))} DOS gameplay')}")
    def _open_browser_search(self): webbrowser.open(f"https://www.google.com/search?q={quote_plus(f'{self.v_title.get()} dos game info mobygames')}")
    def _add_entry_to_frame(self, frame, row, label_text, data_dict, key): var = tk.StringVar(value=data_dict.get(key, "")); setattr(self, f"v_{key}", var); tb.Label(frame, text=label_text).grid(row=row, column=0, sticky='w', pady=2); entry = tb.Entry(frame, textvariable=var); entry.grid(row=row, column=1, sticky='ew', pady=2); entry.bind("<KeyRelease>", self._mark_as_changed); return var
    def _add_combobox_to_frame(self, frame, row, label_text, data_dict, key, values): var = tk.StringVar(value=data_dict.get(key, "")); setattr(self, f"v_{key}", var); tb.Label(frame, text=label_text).grid(row=row, column=0, sticky='w', pady=2); combo = tb.Combobox(frame, values=values, state='readonly' if key != 'genre' else 'normal', textvariable=var); combo.grid(row=row, column=1, sticky='ew', pady=2); combo.bind("<<ComboboxSelected>>", self._mark_as_changed); combo.bind("<KeyRelease>", self._mark_as_changed); return var
    
    def launch_test_game(self, specific_exe):
        try:
            # Minimize windows to ensure DOSBox is visible
            self.parent_app.iconify()
            self.withdraw() # Use withdraw for transient windows
            self.parent_app.update() # Force update to ensure minimization happens immediately
            
            thread = self.logic.launch_game(self.zip_name, specific_exe=specific_exe, force_fullscreen=self.parent_app.force_fullscreen_var.get(), auto_exit=self.parent_app.auto_exit_var.get())
            
            def check_thread():
                if thread.is_alive():
                    self.after(1000, check_thread)
                else:
                    # Restore windows
                    self.parent_app.deiconify()
                    self.parent_app.state('normal')
                    self.deiconify()
                    self.state('normal')
                    self.lift()
                    self.focus_force()
            
            self.after(1000, check_thread)
            
        except Exception as e:
            self.parent_app.deiconify()
            self.parent_app.state('normal')
            self.deiconify()
            self.state('normal')
            messagebox.showerror("Error", str(e), parent=self)

    def _build_executables_tab(self, parent):
        header = tb.Frame(parent); header.pack(fill=X, padx=10, pady=10)
        tb.Label(header, text="Assign roles and parameters to found executables:", bootstyle="secondary").pack(anchor="w")
        exe_frame = tb.Frame(parent); exe_frame.pack(fill=tk.BOTH, expand=True, padx=10); current_map = self.game_data.get("executables", {}); found_exes = self.logic.get_all_executables(self.name); self.exe_widgets = []; canvas = tk.Canvas(exe_frame, highlightthickness=0); scrollbar = tb.Scrollbar(exe_frame, orient="vertical", command=canvas.yview, bootstyle="round"); scrollable_frame = tb.Frame(canvas); scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set); canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y"); role_options = sorted(list(constants.ROLE_DISPLAY.values()))
        tb.Label(scrollable_frame, text="File", font="-weight bold").grid(row=0, column=0, sticky="w", padx=5); tb.Label(scrollable_frame, text="Run", font="-weight bold").grid(row=0, column=1, padx=5); tb.Label(scrollable_frame, text="Parameters", font="-weight bold").grid(row=0, column=2, padx=5); tb.Label(scrollable_frame, text="Role", font="-weight bold").grid(row=0, column=3, sticky="w", padx=5); tb.Label(scrollable_frame, text="Custom Title", font="-weight bold").grid(row=0, column=4, sticky="w", padx=5)
        for i, exe in enumerate(found_exes):
            r = i + 1; info = current_map.get(exe, {}); current_role_id, current_title, current_params = info.get("role", constants.ROLE_UNASSIGNED), info.get("title", ""), info.get("params", "")
            tb.Label(scrollable_frame, text=truncate_text(exe, 35)).grid(row=r, column=0, sticky="w", padx=5, pady=2); tb.Button(scrollable_frame, text="▶", bootstyle="success-outline", width=2, command=lambda x=exe: self.launch_test_game(x)).grid(row=r, column=1, padx=5)
            var_params = tk.StringVar(value=current_params); ent_params = tb.Entry(scrollable_frame, textvariable=var_params, width=15); ent_params.grid(row=r, column=2, padx=5)
            disp_role = constants.ROLE_DISPLAY.get(current_role_id, constants.ROLE_DISPLAY[constants.ROLE_UNASSIGNED]); var_role = tk.StringVar(value=disp_role); var_title = tk.StringVar(value=current_title); cb_role = tb.Combobox(scrollable_frame, values=role_options, textvariable=var_role, state="readonly", width=18); cb_role.grid(row=r, column=3, padx=5); ent_title = tb.Entry(scrollable_frame, textvariable=var_title, width=20); ent_title.grid(row=r, column=4, padx=5)
            def update_title_state(v_r=var_role, e_t=ent_title): e_t.configure(state="normal" if v_r.get() == constants.ROLE_DISPLAY[constants.ROLE_CUSTOM] else "disabled")
            
            def on_role_change(event, v_r=var_role, e_t=ent_title, current_exe=exe):
                update_title_state(v_r, e_t)
                # Exclusivity logic for Main Game, Setup/Config, and Game Installer
                selected_role = v_r.get()
                target_roles = [constants.ROLE_DISPLAY[constants.ROLE_MAIN], constants.ROLE_DISPLAY[constants.ROLE_SETUP], constants.ROLE_DISPLAY[constants.ROLE_INSTALL]]
                
                if selected_role in target_roles:
                    for other_exe, other_vr, _, _ in self.exe_widgets:
                        if other_exe != current_exe and other_vr.get() == selected_role:
                            other_vr.set(constants.ROLE_DISPLAY[constants.ROLE_UNASSIGNED])
                self._mark_as_changed()
                
            ent_params.bind("<KeyRelease>", self._mark_as_changed); cb_role.bind("<<ComboboxSelected>>", on_role_change); ent_title.bind("<KeyRelease>", self._mark_as_changed); update_title_state(var_role, ent_title); self.exe_widgets.append((exe, var_role, var_title, var_params))

    def _build_drives_tab(self, parent):
        parent.columnconfigure(0, weight=1); parent.rowconfigure(1, weight=1)
        
        # Toolbar
        toolbar = tb.Frame(parent, padding=5)
        toolbar.grid(row=0, column=0, sticky="ew")
        tb.Button(toolbar, text="Add Mount", command=self._add_mount, bootstyle="success").pack(side=LEFT, padx=2)
        tb.Button(toolbar, text="Remove Selected", command=self._remove_mount, bootstyle="danger").pack(side=LEFT, padx=2)
        
        # Treeview
        columns = ("drive", "type", "path", "label", "as")
        self.mounts_tree = tb.Treeview(parent, columns=columns, show="headings", selectmode="browse")
        self.mounts_tree.heading("drive", text="Drive")
        self.mounts_tree.heading("type", text="Type")
        self.mounts_tree.heading("path", text="Path(s)")
        self.mounts_tree.heading("label", text="Label")
        self.mounts_tree.heading("as", text="As")
        
        self.mounts_tree.column("drive", width=50, anchor="center")
        self.mounts_tree.column("type", width=80, anchor="center")
        self.mounts_tree.column("path", width=300)
        self.mounts_tree.column("label", width=100)
        self.mounts_tree.column("as", width=80)
        
        self.mounts_tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # Populate
        mounts = self.game_data.get("mounts", [])
        if not mounts:
            # Convert legacy
            if "mount_c" in self.game_data:
                mounts.append({"drive": "C", "type": "dir", "path": self.game_data["mount_c"]})
            elif os.path.exists(os.path.join(self.logic.find_game_folder(self.name), "drives", "c")):
                mounts.append({"drive": "C", "type": "dir", "path": "drives/c"})
            else:
                mounts.append({"drive": "C", "type": "dir", "path": "."})
                
            if "mount_d" in self.game_data:
                mounts.append({"drive": "D", "type": "image", "path": self.game_data["mount_d"]})
            else:
                isos = self.logic.get_mounted_isos(self.name)
                if isos:
                    mounts.append({"drive": "D", "type": "image", "path": f"cd/{isos[0]}"})

        for m in mounts:
            self.mounts_tree.insert("", "end", values=(m.get("drive"), m.get("type"), m.get("path"), m.get("label", ""), m.get("as", "iso")))
            
        btn_frame = tb.Frame(parent)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        
        tb.Button(btn_frame, text="Add Mount", command=self._add_mount, bootstyle="success").pack(side=LEFT, padx=5)
        tb.Button(btn_frame, text="Edit Mount", command=self._edit_mount, bootstyle="warning").pack(side=LEFT, padx=5)
        tb.Button(btn_frame, text="Remove Mount", command=self._remove_mount, bootstyle="danger").pack(side=LEFT, padx=5)
        
        tb.Label(parent, text="Note: Paths are relative to game folder. Multiple images can be separated by semicolon.", bootstyle="secondary").grid(row=3, column=0, pady=5)
        
        # Automatic Mounts Info
        info_frame = tb.Labelframe(parent, text="Automatic Mounts (if not overridden)", bootstyle="info", padding=10)
        info_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=5)
        tb.Label(info_frame, text="• Drive C: Mounted as 'drives/c' (if exists) or '.' (game root)", bootstyle="info").pack(anchor="w")
        tb.Label(info_frame, text="• Drive D: All ISO/CUE files in 'cd/' folder are mounted automatically.", bootstyle="info").pack(anchor="w")

    def _add_mount(self):
        dialog = AddMountDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            res = dialog.result
            # Relativize path
            game_root = self.logic.find_game_folder(self.name)
            paths = res["path"].split(";")
            rel_paths = []
            for p in paths:
                try:
                    rp = os.path.relpath(p, game_root)
                    if not rp.startswith(".."): rel_paths.append(rp)
                    else: rel_paths.append(p)
                except: rel_paths.append(p)
            
            final_path = ";".join(rel_paths)
            self.mounts_tree.insert("", "end", values=(res["drive"], res["type"], final_path, res["label"], res["as"]))
            self._mark_as_changed()

    def _edit_mount(self):
        if not (sel := self.mounts_tree.selection()): return
        item = sel[0]
        vals = self.mounts_tree.item(item, "values")
        
        # Reconstruct result dict for dialog
        initial_data = {
            "drive": vals[0],
            "type": vals[1],
            "path": vals[2],
            "label": vals[3],
            "as": vals[4]
        }
        
        dialog = AddMountDialog(self, initial_data=initial_data)
        self.wait_window(dialog)
        if dialog.result:
            res = dialog.result
            # Relativize path
            game_root = self.logic.find_game_folder(self.name)
            paths = res["path"].split(";")
            rel_paths = []
            for p in paths:
                try:
                    rp = os.path.relpath(p, game_root)
                    if not rp.startswith(".."): rel_paths.append(rp)
                    else: rel_paths.append(p)
                except: rel_paths.append(p)
            
            final_path = ";".join(rel_paths)
            self.mounts_tree.item(item, values=(res["drive"], res["type"], final_path, res["label"], res["as"]))
            self._mark_as_changed()

    def _remove_mount(self):
        if sel := self.mounts_tree.selection():
            self.mounts_tree.delete(sel[0])
            self._mark_as_changed()

    def _open_mount_dialog(self, drive_letter, var):
        # Legacy method kept for compatibility if needed, but unused by new tab
        pass


    def _browse_mount_c(self):
        # Legacy method removed
        pass

    def _browse_mount_d(self):
        # Legacy method removed
        pass

    def _reset_dosbox_settings(self):
        if not messagebox.askyesno("Reset DOSBox Settings?", "This will reset all DOSBox-related tabs (CPU, Audio, Render, etc.) to the default values from your selected DOSBox installation. This cannot be undone. Continue?", parent=self): return
        default_conf = self.logic.get_default_dosbox_conf(self.game_data.get("custom_dosbox_path"))
        if not default_conf: messagebox.showerror("Error", "Could not load default DOSBox configuration.", parent=self); return
        self.game_data['dosbox_settings'] = self.logic.parse_dosbox_conf_to_json(default_conf)
        current_tab_index = self.tabs.index(self.tabs.select()); self._load_game_data(self.zip_name, existing_data=self.game_data); self.tabs.select(current_tab_index)
        self._mark_as_changed()

    def _apply_template_dialog(self):
        templates_dir = os.path.join(os.getcwd(), "database", "templates")
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir)
            
        templates = [f for f in os.listdir(templates_dir) if f.lower().endswith(".conf")]
        if not templates:
            messagebox.showinfo("No Templates", "No templates found in 'templates' folder.", parent=self)
            return

        dialog = tb.Toplevel(self)
        dialog.title("Apply Template")
        dialog.geometry("300x400")
        
        tb.Label(dialog, text="Select a template to apply:", bootstyle="info").pack(pady=10)
        
        frame = tb.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = tb.Scrollbar(frame, orient="vertical")
        lb = tk.Listbox(frame, yscrollcommand=scrollbar.set)
        scrollbar.config(command=lb.yview)
        
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        for t in templates:
            lb.insert(tk.END, os.path.splitext(t)[0])
            
        def apply():
            if not lb.curselection(): return
            idx = lb.curselection()[0]
            filename = templates[idx]
            self._apply_template(os.path.join(templates_dir, filename))
            dialog.destroy()
            
        tb.Button(dialog, text="Apply", command=apply, bootstyle="success").pack(pady=10)

    def _apply_template(self, filepath):
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            # Parse template to get the new values
            template_settings = self.logic.parse_dosbox_conf_to_json(content)
            
            # 1. Update Visual State (self.game_data['dosbox_settings'])
            # Deep merge
            current_settings = self.game_data.get("dosbox_settings", {})
            for section, keys in template_settings.items():
                if section not in current_settings:
                    current_settings[section] = {}
                for key, value in keys.items():
                    current_settings[section][key] = value
            self.game_data["dosbox_settings"] = current_settings
            
            # 2. Update Source File (self.game_data['custom_config_content'])
            # If custom content exists, we update it textually.
            # If it doesn't exist, we might generate it?
            # User said: "V Zdrojovom súbore nájdi riadky... Zmeň iba <hodnota>"
            
            current_custom_content = self.game_data.get("custom_config_content", "")
            if not current_custom_content.strip():
                # If empty, maybe generate it first so we have something to update?
                # Or just leave it empty and let the generator use dosbox_settings?
                # If we leave it empty, _generate_conf_content will be used, which uses dosbox_settings.
                # So if we updated dosbox_settings, the generated content will be correct!
                # BUT if the user had custom content, we must update it.
                pass
            else:
                # Update the text content
                updated_content = self.logic.update_dosbox_conf_content(current_custom_content, template_settings)
                self.game_data["custom_config_content"] = updated_content
            
            # Reload UI
            current_tab_index = self.tabs.index(self.tabs.select())
            self._load_game_data(self.zip_name, existing_data=self.game_data)
            
            # Restore tab
            if current_tab_index < len(self.tabs.tabs()):
                self.tabs.select(current_tab_index)
                
            messagebox.showinfo("Template Applied", f"Template '{os.path.basename(filepath)}' applied successfully.\nSettings have been updated.", parent=self)
            self._mark_as_changed()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply template: {e}", parent=self)
                
            self._mark_as_changed()
            
            messagebox.showinfo("Success", f"Template applied successfully.", parent=self)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply template:\n{e}", parent=self)

    def _build_dosbox_tab(self, parent):
        settings = self.game_data.get("dosbox_settings", {}); dosbox = settings.get("dosbox", {}); dos = settings.get("dos", {}); canvas = tk.Canvas(parent, highlightthickness=0); scrollbar = tb.Scrollbar(parent, orient="vertical", command=canvas.yview, bootstyle="round"); scrollable_frame = tb.Frame(canvas); scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set); canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        
        # DOSBox Version Override
        f_version = tb.Labelframe(scrollable_frame, text="DOSBox Version Override", bootstyle="primary", padding=10); f_version.pack(fill=tk.X, padx=10, pady=(5, 10)); f_version.columnconfigure(1, weight=1)
        self.v_dosbox_path_name = self._add_opt(f_version, 0, 0, "Version:", ["(Use Default)"] + [inst['name'] for inst in self.dosbox_installations], "", False, "Select a specific DOSBox version for this game.")
        self.v_dosbox_path_name.set(next((inst['name'] for inst in self.dosbox_installations if inst['path'] == self.game_data.get("custom_dosbox_path", "")), "(Use Default)"))
        
        btn_frame = tb.Frame(f_version)
        btn_frame.grid(row=0, column=2, padx=(20, 10))
        tb.Button(btn_frame, text="Apply Template...", command=self._apply_template_dialog, bootstyle="info-outline").pack(side=tk.LEFT, padx=5)
        tb.Button(btn_frame, text="Reset to Defaults", command=self._reset_dosbox_settings, bootstyle="danger-outline").pack(side=tk.LEFT)
        
        # General DOSBox Settings
        f_gen = tb.Labelframe(scrollable_frame, text="General Settings", bootstyle="info", padding=10); f_gen.pack(fill=tk.X, padx=10, pady=5)
        self.v_language = self._add_opt(f_gen, 0, 0, "Language:", ["", "br", "de", "en", "es", "fr", "it", "nl", "pl", "ru"], dosbox.get("language", ""), True, "Language code.")
        self.v_machine = self._add_opt(f_gen, 0, 2, "Machine:", ["svga_s3", "hercules", "cga_mono", "cga", "pcjr", "tandy", "ega", "svga_et3000", "svga_et4000", "svga_paradise", "vesa_nolfb", "vesa_oldvbe"], dosbox.get("machine", "svga_s3"), False, "Machine type.", var_name="machine")
        self.v_memsize = self._add_opt(f_gen, 1, 0, "Memory (MB):", ["16", "1", "2", "4", "8", "32", "64", "128"], str(dosbox.get("memsize", "16")), True, "RAM in MB.", var_name="memsize")
        self.v_mcb_fault = self._add_opt(f_gen, 1, 2, "MCB Fault:", ["repair", "report", "allow", "deny"], dosbox.get("mcb_fault_strategy", "repair"), False, "MCB fault strategy.")
        self.v_vmemsize = self._add_opt(f_gen, 2, 0, "VRAM:", ["auto", "1", "2", "4", "8", "256", "512", "1024", "2048", "4096", "8192"], str(dosbox.get("vmemsize", "auto")), True, "Video RAM.")
        self.v_vmem_delay = self._add_opt(f_gen, 2, 2, "VRAM Delay:", ["off", "on"], str(dosbox.get("vmem_delay", "off")), True, "VRAM delay (ns or off/on).")
        self.v_dos_rate = self._add_opt(f_gen, 3, 0, "DOS Rate:", ["default", "host"], str(dosbox.get("dos_rate", "default")), True, "DOS refresh rate.")
        self.v_vesa_modes = self._add_opt(f_gen, 3, 2, "VESA Modes:", ["compatible", "all", "halfline"], dosbox.get("vesa_modes", "compatible"), False, "VESA modes.")
        self.v_vga_8dot = self._add_bool(f_gen, "VGA 8-dot Font", dosbox.get("vga_8dot_font", False), 4, 0, "Use 8-pixel-wide fonts.")
        self.v_vga_render = self._add_bool(f_gen, "VGA Scanline Render", dosbox.get("vga_render_per_scanline", True), 4, 2, "Accurate per-scanline rendering.")
        self.v_speed_mods = self._add_bool(f_gen, "Speed Mods", dosbox.get("speed_mods", True), 5, 0, "Permit performance improvements.")
        self.v_autoexec_section = self._add_opt(f_gen, 5, 2, "Autoexec:", ["join", "overwrite"], dosbox.get("autoexec_section", "join"), False, "Autoexec section behavior.")
        self.v_automount = self._add_bool(f_gen, "Automount", dosbox.get("automount", True), 6, 0, "Mount drives automatically.")
        self.v_startup_verbosity = self._add_opt(f_gen, 6, 2, "Verbosity:", ["auto", "high", "low", "quiet"], dosbox.get("startup_verbosity", "auto"), False, "Startup verbosity.")
        self.v_write_protected = self._add_bool(f_gen, "Allow Write-Protected", dosbox.get("allow_write_protected_files", True), 7, 0, "Allow reading write-protected files.")
        self.v_shell_shortcuts = self._add_bool(f_gen, "Shell Shortcuts", dosbox.get("shell_config_shortcuts", True), 7, 2, "Allow config shortcuts.")

        # DOS Settings
        f_dos = tb.Labelframe(scrollable_frame, text="DOS", bootstyle="success", padding=10); f_dos.pack(fill=tk.X, padx=10, pady=5); self.v_ver = self._add_opt(f_dos, 0, 0, "DOS Version:", [], dos.get("ver", "5.0"), True, "DOS version to report to programs (e.g., 5.0, 6.22)."); self.v_keyboardlayout = self._add_opt(f_dos, 0, 2, "Keyboard:", ["auto", "us", "sk", "cz"], dos.get("keyboardlayout", "auto"), True, "Keyboard layout code."); f_mem_bools = tb.Frame(f_dos); f_mem_bools.grid(row=1, column=0, columnspan=4, sticky="w", padx=5, pady=5); self.v_xms = self._add_bool(f_mem_bools, "XMS", dos.get("xms", True), tooltip="Enable XMS memory."); tb.Label(f_mem_bools, text="EMS:").pack(side=tk.LEFT, padx=(10, 2)); self.v_ems = tk.StringVar(value=str(dos.get("ems", "true"))) if not hasattr(self, "v_ems") else self.v_ems; cb_ems = tb.Combobox(f_mem_bools, textvariable=self.v_ems, values=["true", "emsboard", "emm386", "false"], state="readonly", width=8); cb_ems.pack(side=tk.LEFT, padx=2); cb_ems.bind("<<ComboboxSelected>>", self._mark_as_changed); ToolTip(cb_ems, text="Enable EMS memory.", bootstyle="info"); self.v_umb = self._add_bool(f_mem_bools, "UMB", dos.get("umb", True), tooltip="Enable Upper Memory Blocks.")
        self.v_hard_drive_data_rate_limit = self._add_opt(f_dos, 2, 0, "HDD Rate Limit:", ["0", "-1"], str(dos.get("hard_drive_data_rate_limit", "0")), True, "HDD data rate limit.")
        self.v_file_locking = self._add_bool(f_dos, "File Locking", dos.get("file_locking", True), 2, 2, "Enable file locking.")
        self.v_automount_all_drives = self._add_bool(f_dos, "Automount All", dos.get("automount_all_drives", True), 3, 0, "Automount all drives.")
        self.v_files = self._add_spinbox_to_frame(f_dos, 3, 2, dos, "files", 0, 255, "Files:", "Number of file handles.", default_val=127)
        self.v_minimum_mcb_free = self._add_opt(f_dos, 4, 0, "Min MCB Free:", ["0"], str(dos.get("minimum_mcb_free", "0")), True, "Minimum free MCB.")
        self.v_lfn = self._add_opt(f_dos, 4, 2, "LFN:", ["auto", "true", "false"], str(dos.get("lfn", "auto")).lower(), False, "Long filename support.")
        self.v_fat32 = self._add_bool(f_dos, "FAT32", dos.get("fat32", True), 5, 0, "Enable FAT32 support.")
        self.v_int33 = self._add_bool(f_dos, "INT 33", dos.get("int33", True), 5, 2, "Enable INT 33 mouse support.")

    def _build_cpu_tab(self, parent):
        settings = self.game_data.get("dosbox_settings", {}); cpu = settings.get("cpu", {}); dosbox = settings.get("dosbox", {}); f_cpu = tb.Labelframe(parent, text="CPU Settings", bootstyle="primary", padding=10); f_cpu.pack(fill=tk.X, padx=10, pady=10); self.v_core = self._add_opt(f_cpu, 0, 0, "Core:", ["auto", "dynamic", "normal", "simple"], cpu.get("core", "auto"), False, "CPU emulation core.", var_name="core"); self.v_cputype = self._add_opt(f_cpu, 0, 2, "CPU Type:", ["auto", "386", "386_fast", "386_prefetch", "486", "pentium", "pentium_mmx"], cpu.get("cputype", "auto"), False, "CPU generation.", var_name="cputype"); self.v_cpu_cycles = self._add_opt(f_cpu, 1, 0, "Cycles (Real):", constants.CYCLES_OPTIONS, str(cpu.get("cpu_cycles", "3000")), True, "CPU speed for real-mode games.", var_name="cpu_cycles"); self.v_cpu_cycles_protected = self._add_opt(f_cpu, 1, 2, "Cycles (Prot.):", constants.CYCLES_PROT_OPTIONS, str(cpu.get("cpu_cycles_protected", "60000")), True, "CPU speed for protected-mode games.", var_name="cpu_cycles_protected"); 
        self.v_cpu_throttle = self._add_opt(f_cpu, 2, 2, "Throttle:", ["auto"], cpu.get("cpu_throttle", "auto"), True, "Throttle down CPU cycles if host CPU cannot keep up.")
        self.v_cycleup = self._add_spinbox_to_frame(f_cpu, 3, 0, cpu, "cycleup", 1, 1000, "Cycle Up:", "Cycles to add.", default_val=10)
        self.v_cycledown = self._add_spinbox_to_frame(f_cpu, 3, 2, cpu, "cycledown", 1, 1000, "Cycle Down:", "Cycles to subtract.", default_val=20)
        
        # Moved to row 4 to avoid overlap with throttle/cycle settings
        prot_mode_frame = tb.Frame(f_cpu); prot_mode_frame.grid(row=4, column=0, columnspan=4, sticky='w', pady=(5,0))
        self.v_use_protected_cycles = self._add_bool(prot_mode_frame, "Use Protected Mode Cycles", cpu.get("use_protected_cycles", False), tooltip="Use different cycles for protected mode.", var_name="use_protected_cycles")
        
        if self.logic.game_has_dos4gw(self.name): 
            tb.Label(prot_mode_frame, text="(DOS/4GW detected)", bootstyle="info").pack(side=tk.LEFT, padx=5)
            if not self.v_use_protected_cycles.get():
                self.v_use_protected_cycles.set(True)
                # We don't mark as changed here to avoid annoying "unsaved changes" just by viewing tabs, 
                # but the user will see the checkbox checked.
                # If they save, it will be saved.
        
        f_mem = tb.Labelframe(parent, text="Memory", bootstyle="info", padding=10); f_mem.pack(fill=tk.X, padx=10, pady=5); self.v_memsize = self._add_opt(f_mem, 0, 0, "Memory (MB):", ["1", "2", "4", "8", "16", "32", "64", "128"], str(dosbox.get("memsize", "16")), True, "Amount of emulated RAM in megabytes.", var_name="memsize")

    def _build_audio_tab(self, parent):
        settings = self.game_data.get("dosbox_settings", {}); canvas = tk.Canvas(parent, highlightthickness=0); scrollbar = tb.Scrollbar(parent, orient="vertical", command=canvas.yview, bootstyle="round"); scrollable_frame = tb.Frame(canvas); scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set); canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        
        mixer = settings.get("mixer", {}); f_mixer = tb.Labelframe(scrollable_frame, text="Mixer", bootstyle="info", padding=10); f_mixer.pack(fill=tk.X, padx=10, pady=5)
        self.v_nosound = self._add_bool(f_mixer, "No Sound", mixer.get("nosound", False), 0, 0, "Enable silent mode.", var_name="nosound")
        self.v_rate = self._add_opt(f_mixer, 1, 0, "Rate:", ["48000", "44100", "22050", "11025", "8000"], str(mixer.get("rate", "48000")), True, "Sample rate.")
        self.v_blocksize = self._add_opt(f_mixer, 1, 2, "Blocksize:", ["1024", "2048", "4096", "512", "256", "128", "64"], str(mixer.get("blocksize", "1024")), True, "Audio block size.")
        self.v_prebuffer = self._add_opt(f_mixer, 2, 0, "Prebuffer (ms):", [], str(mixer.get("prebuffer", "25")), True, "Audio pre-buffer size.")
        self.v_compressor = self._add_bool(f_mixer, "Compressor", mixer.get("compressor", True), 2, 2, "Enable auto-leveling compressor.")
        self.v_crossfeed = self._add_opt(f_mixer, 3, 0, "Crossfeed:", ["off", "light", "normal", "strong"], mixer.get("crossfeed", "off"), False, "Headphone crossfeed.")
        self.v_reverb = self._add_opt(f_mixer, 3, 2, "Reverb:", ["off", "on", "tiny", "small", "medium", "large", "huge"], mixer.get("reverb", "off"), False, "Global reverb effect.")
        self.v_chorus = self._add_opt(f_mixer, 4, 0, "Chorus:", ["off", "on", "light", "normal", "strong"], mixer.get("chorus", "off"), False, "Global chorus effect.")
        self.v_negotiate = self._add_bool(f_mixer, "Negotiate", mixer.get("negotiate", True), 4, 2, "Negotiate audio format with host.")

        midi = settings.get("midi", {}); f_midi = tb.Labelframe(scrollable_frame, text="MIDI", bootstyle="warning", padding=10); f_midi.pack(fill=tk.X, padx=10, pady=5)
        self.v_mididevice = self._add_opt(f_midi, 0, 0, "MIDI Device:", ["auto", "fluidsynth", "mt32", "win32", "none"], midi.get("mididevice", "auto"), False, "MPU-401 device.")
        self.v_midiconfig = self._add_opt(f_midi, 0, 2, "Config:", [], midi.get("midiconfig", ""), True, "MIDI interface config.")
        self.v_mpu401 = self._add_opt(f_midi, 1, 0, "MPU-401 Mode:", ["intelligent", "uart", "none"], midi.get("mpu401", "intelligent"), False, "MPU-401 emulation mode.")
        self.v_raw_midi_output = self._add_bool(f_midi, "Raw MIDI Output", midi.get("raw_midi_output", False), 1, 2, "Enable raw, unaltered MIDI output.")

        fluidsynth = settings.get("fluidsynth", {}); f_fluid = tb.Labelframe(scrollable_frame, text="FluidSynth", bootstyle="primary", padding=10); f_fluid.pack(fill=tk.X, padx=10, pady=5)
        self.v_soundfont = self._add_opt(f_fluid, 0, 0, "SoundFont:", [], fluidsynth.get("soundfont", "default.sf2"), True, "Path to .sf2 file.")
        self.v_fsynth_chorus = self._add_opt(f_fluid, 0, 2, "Chorus:", ["auto", "on", "off"], fluidsynth.get("fsynth_chorus", "auto"), True, "FluidSynth chorus.")
        self.v_fsynth_reverb = self._add_opt(f_fluid, 1, 0, "Reverb:", ["auto", "on", "off"], fluidsynth.get("fsynth_reverb", "auto"), True, "FluidSynth reverb.")
        self.v_fsynth_filter = self._add_opt(f_fluid, 1, 2, "Filter:", ["off"], fluidsynth.get("fsynth_filter", "off"), True, "FluidSynth filter.")

        mt32 = settings.get("mt32", {}); f_mt32 = tb.Labelframe(scrollable_frame, text="MT-32", bootstyle="secondary", padding=10); f_mt32.pack(fill=tk.X, padx=10, pady=5)
        self.v_mt32_model = self._add_opt(f_mt32, 0, 0, "Model:", ["auto", "cm32l", "mt32", "mt32_old", "mt32_new"], mt32.get("model", "auto"), True, "MT-32 model.")
        self.v_romdir = self._add_opt(f_mt32, 0, 2, "ROM Dir:", [], mt32.get("romdir", ""), True, "Directory with ROMs.")
        self.v_mt32_filter = self._add_opt(f_mt32, 1, 0, "Filter:", ["off"], mt32.get("mt32_filter", "off"), True, "MT-32 filter.")

        sblaster = settings.get("sblaster", {}); f_sb = tb.Labelframe(scrollable_frame, text="Sound Blaster", bootstyle="danger", padding=10); f_sb.pack(fill=tk.X, padx=10, pady=5)
        self.v_sbtype = self._add_opt(f_sb, 0, 0, "SB Type:", ["sb16", "sbpro2", "sbpro1", "sb2", "sb1", "gb", "ess", "none"], sblaster.get("sbtype", "sb16"), False, "Sound Blaster model.")
        self.v_sbmixer = self._add_bool(f_sb, "SB Mixer", sblaster.get("sbmixer", True), 0, 2, "Allow SB mixer change.")
        self.v_oplmode = self._add_opt(f_sb, 1, 0, "OPL Mode:", ["auto", "opl3", "dualopl2", "opl2", "cms", "esfm", "none"], sblaster.get("oplmode", "auto"), False, "OPL chip emulation.")
        self.v_irq = self._add_opt(f_sb, 2, 0, "IRQ:", ["7", "5", "3"], str(sblaster.get("irq", "7")), True, "IRQ.")
        self.v_dma = self._add_opt(f_sb, 2, 2, "DMA:", ["1", "0", "3"], str(sblaster.get("dma", "1")), True, "DMA channel.")
        self.v_hdma = self._add_opt(f_sb, 2, 4, "HDMA:", ["5", "1", "7"], str(sblaster.get("hdma", "5")), True, "High DMA channel.")
        self.v_sb_filter = self._add_opt(f_sb, 3, 0, "Filter:", ["off"], sblaster.get("sb_filter", "off"), True, "SB filter.")
        self.v_opl_filter = self._add_opt(f_sb, 3, 2, "OPL Filter:", ["off"], sblaster.get("opl_filter", "off"), True, "OPL filter.")
        self.v_sb_warmup = self._add_bool(f_sb, "Warmup", sblaster.get("sb_warmup", False), 3, 4, "SB warmup.")

        gus = settings.get("gus", {}); f_gus = tb.Labelframe(scrollable_frame, text="Gravis UltraSound", bootstyle="success", padding=10); f_gus.pack(fill=tk.X, padx=10, pady=5)
        self.v_gus = self._add_bool(f_gus, "Enable GUS", gus.get("gus", False), 0, 0, "Enable Gravis UltraSound.")
        self.v_ultradir = self._add_opt(f_gus, 1, 0, "UltraDir:", [], gus.get("ultradir", "C:\\ULTRASND"), True, "UltraSound directory path.")
        self.v_gus_rate = self._add_opt(f_gus, 0, 2, "Rate:", ["44100", "22050"], str(gus.get("gus_rate", "44100")), True, "GUS sample rate.")
        self.v_gus_base = self._add_opt(f_gus, 1, 2, "Base:", ["240", "220", "260", "280", "2a0", "2c0", "2e0", "300"], str(gus.get("gus_base", "240")), True, "GUS base address.")
        self.v_gus_irq1 = self._add_opt(f_gus, 2, 0, "IRQ1:", ["5", "3", "7", "9", "10", "11", "12"], str(gus.get("gus_irq1", "5")), True, "GUS IRQ1.")
        self.v_gus_irq2 = self._add_opt(f_gus, 2, 2, "IRQ2:", ["5", "3", "7", "9", "10", "11", "12"], str(gus.get("gus_irq2", "5")), True, "GUS IRQ2.")
        self.v_gus_dma1 = self._add_opt(f_gus, 3, 0, "DMA1:", ["3", "0", "1", "5", "6", "7"], str(gus.get("gus_dma1", "3")), True, "GUS DMA1.")
        self.v_gus_dma2 = self._add_opt(f_gus, 3, 2, "DMA2:", ["3", "0", "1", "5", "6", "7"], str(gus.get("gus_dma2", "3")), True, "GUS DMA2.")
        self.v_gus_filter = self._add_opt(f_gus, 4, 0, "Filter:", ["off"], gus.get("gus_filter", "off"), True, "GUS filter.")

        imfc = settings.get("imfc", {}); f_imfc = tb.Labelframe(scrollable_frame, text="IMFC", bootstyle="info", padding=10); f_imfc.pack(fill=tk.X, padx=10, pady=5)
        self.v_imfc = self._add_bool(f_imfc, "Enable IMFC", imfc.get("imfc", False), 0, 0, "Enable IBM Music Feature Card.")
        self.v_imfc_base = self._add_opt(f_imfc, 0, 2, "Base:", ["2a20"], str(imfc.get("imfc_base", "2a20")), True, "IMFC base address.")

        innovation = settings.get("innovation", {}); f_inn = tb.Labelframe(scrollable_frame, text="Innovation", bootstyle="warning", padding=10); f_inn.pack(fill=tk.X, padx=10, pady=5)
        self.v_innovation = self._add_bool(f_inn, "Enable Innovation", innovation.get("innovation", False), 0, 0, "Enable Innovation SSI-2001.")
        self.v_innovation_base = self._add_opt(f_inn, 0, 2, "Base:", ["280"], str(innovation.get("innovation_base", "280")), True, "Innovation base address.")
        self.v_innovation_model = self._add_opt(f_inn, 1, 0, "Model:", ["sid6581", "sid8580"], innovation.get("innovation_model", "sid6581"), False, "SID chip model.")
        self.v_innovation_filter = self._add_opt(f_inn, 1, 2, "Filter:", ["off"], innovation.get("innovation_filter", "off"), True, "Innovation filter.")

        speaker = settings.get("speaker", {}); f_spk = tb.Labelframe(scrollable_frame, text="PC Speaker & Other DACs", bootstyle="secondary", padding=10); f_spk.pack(fill=tk.X, padx=10, pady=5)
        self.v_pcspeaker = self._add_opt(f_spk, 0, 0, "PC Speaker:", ["impulse", "discrete", "none"], speaker.get("pcspeaker", "impulse"), False, "PC speaker model.")
        self.v_tandy = self._add_opt(f_spk, 0, 2, "Tandy 3-Voice:", ["auto", "on", "psg", "off"], speaker.get("tandy", "auto"), False, "Tandy/PCjr sound.")
        self.v_lpt_dac = self._add_opt(f_spk, 1, 0, "LPT DAC:", ["none", "disney", "covox", "ston1"], speaker.get("lpt_dac", "none"), False, "Parallel port DAC.")
        self.v_ps1audio = self._add_bool(f_spk, "PS/1 Audio", speaker.get("ps1audio", False), 1, 2, "Enable PS/1 audio.")
        self.v_pcspeaker_filter = self._add_opt(f_spk, 2, 0, "PC Spk Filter:", ["off"], speaker.get("pcspeaker_filter", "off"), True, "PC speaker filter.")
        self.v_tandy_filter = self._add_opt(f_spk, 2, 2, "Tandy Filter:", ["off"], speaker.get("tandy_filter", "off"), True, "Tandy filter.")
        self.v_lpt_dac_filter = self._add_opt(f_spk, 3, 0, "LPT DAC Filter:", ["off"], speaker.get("lpt_dac_filter", "off"), True, "LPT DAC filter.")

    def _build_sdl_tab(self, parent):
        settings = self.game_data.get("dosbox_settings", {}); sdl = settings.get("sdl", {}); canvas = tk.Canvas(parent, highlightthickness=0); scrollbar = tb.Scrollbar(parent, orient="vertical", command=canvas.yview, bootstyle="round"); scrollable_frame = tb.Frame(canvas); scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set); canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        
        f_display = tb.Labelframe(scrollable_frame, text="Display & Window", bootstyle="primary", padding=10); f_display.pack(fill=tk.X, padx=10, pady=5)
        self.v_fullscreen = self._add_bool(f_display, "Start Fullscreen", sdl.get("fullscreen", False), 0, 0, "Start directly in fullscreen.")
        self.v_output = self._add_opt(f_display, 0, 2, "Output:", ["opengl", "texture", "texturenb", "surface", "overlay", "ddraw"], sdl.get("output", "opengl"), False, "Video system for output.")
        self.v_fullresolution = self._add_opt(f_display, 1, 0, "Fullscreen Res.:", constants.FULL_RES_OPTIONS, sdl.get("fullresolution", "desktop"), True, "Fullscreen resolution.", var_name="fullresolution")
        self.v_windowresolution = self._add_opt(f_display, 1, 2, "Window Res.:", constants.WIN_RES_OPTIONS, sdl.get("windowresolution", "default"), True, "Window size.", var_name="windowresolution")
        self.v_display = self._add_spinbox_to_frame(f_display, 2, 0, sdl, "display", 0, 10, "Display #:", "Number of display to use (0 by default).")
        self.v_window_position = self._add_opt(f_display, 2, 2, "Window Pos:", ["auto"], sdl.get("window_position", "auto"), True, "Window position (auto or X,Y).")
        self.v_window_decorations = self._add_bool(f_display, "Window Decorations", sdl.get("window_decorations", True), 3, 0, "Enable window decorations.")
        self.v_transparency = self._add_spinbox_to_frame(f_display, 3, 2, sdl, "transparency", 0, 90, "Transparency:", "0 (no transparency) to 90 (high).")
        self.v_window_titlebar = self._add_opt(f_display, 4, 0, "Titlebar:", [], sdl.get("window_titlebar", "program=name dosbox=auto cycles=on mouse=full"), True, "Titlebar info.")

        f_render = tb.Labelframe(scrollable_frame, text="Rendering & VSync", bootstyle="info", padding=10); f_render.pack(fill=tk.X, padx=10, pady=5)
        self.v_texture_renderer = self._add_opt(f_render, 0, 0, "Texture Renderer:", ["auto", "direct3d", "direct3d11", "direct3d12", "opengl", "opengles2", "software"], sdl.get("texture_renderer", "auto"), False, "Texture renderer.")
        self.v_vsync = self._add_opt(f_render, 0, 2, "VSync:", ["auto", "on", "adaptive", "off", "yield"], sdl.get("vsync", "auto"), False, "Synchronize with refresh rate.")
        self.v_vsync_skip = self._add_spinbox_to_frame(f_render, 1, 0, sdl, "vsync_skip", 0, 100000, "VSync Skip:", "Microseconds to allow rendering to block.")
        self.v_presentation_mode = self._add_opt(f_render, 1, 2, "Presentation:", ["auto", "cfr", "vfr"], sdl.get("presentation_mode", "auto"), False, "Presentation mode.")
        self.v_host_rate = self._add_opt(f_render, 2, 0, "Host Rate:", ["auto", "sdi", "vrr"], sdl.get("host_rate", "auto"), True, "Host refresh rate.")

        f_misc = tb.Labelframe(scrollable_frame, text="Misc", bootstyle="secondary", padding=10); f_misc.pack(fill=tk.X, padx=10, pady=5)
        self.v_waitonerror = self._add_bool(f_misc, "Wait on Error", sdl.get("waitonerror", True), 0, 0, "Keep console open on error.")
        self.v_priority = self._add_opt(f_misc, 0, 2, "Priority:", ["auto auto", "lowest", "lower", "normal", "higher", "highest"], sdl.get("priority", "auto auto"), True, "Process priority.")
        self.v_mute_inactive = self._add_bool(f_misc, "Mute Inactive", sdl.get("mute_when_inactive", False), 1, 0, "Mute when inactive.")
        self.v_pause_inactive = self._add_bool(f_misc, "Pause Inactive", sdl.get("pause_when_inactive", False), 1, 2, "Pause when inactive.")
        self.v_mapperfile = self._add_opt(f_misc, 2, 0, "Mapper File:", [], sdl.get("mapperfile", "mapper-sdl2-0.82.2.map"), True, "Path to mapper file.")
        self.v_screensaver = self._add_opt(f_misc, 2, 2, "Screensaver:", ["auto", "allow", "block"], sdl.get("screensaver", "auto"), False, "Screensaver handling.")

    def _build_render_tab(self, parent):
        settings = self.game_data.get("dosbox_settings", {}); render = settings.get("render", {}); sdl = settings.get("sdl", {}); voodoo = settings.get("voodoo", {}); dosbox = settings.get("dosbox", {}); composite = settings.get("composite", {}); canvas = tk.Canvas(parent, highlightthickness=0); scrollbar = tb.Scrollbar(parent, orient="vertical", command=canvas.yview, bootstyle="round"); scrollable_frame = tb.Frame(canvas); scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set); canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        
        f_render = tb.Labelframe(scrollable_frame, text="Scaling & Shaders", bootstyle="info", padding=10); f_render.pack(fill=tk.X, padx=10, pady=5)
        self.v_glshader = self._add_opt(f_render, 0, 0, "GL Shader:", ["crt-auto", "crt-auto-machine", "crt-auto-arcade", "sharp", "bilinear", "nearest", "none"], render.get("glshader", "crt-auto"), False, "Pixel-art/CRT shader.", var_name="glshader")
        self.v_aspect = self._add_opt(f_render, 0, 2, "Aspect:", ["auto", "on", "square-pixels", "off", "stretch"], str(render.get("aspect", "auto")), False, "Aspect ratio correction.", var_name="aspect")
        self.v_integer_scaling = self._add_opt(f_render, 1, 0, "Int. Scaling:", ["auto", "vertical", "horizontal", "off"], str(render.get("integer_scaling", "auto")), False, "Integer-only scaling.", var_name="integer_scaling")
        self.v_viewport = self._add_opt(f_render, 1, 2, "Viewport:", ["fit"], render.get("viewport", "fit"), True, "Viewport size (fit, WxH, N%, etc).")
        self.v_monochrome = self._add_opt(f_render, 2, 0, "Monochrome:", ["amber", "green", "white", "paperwhite"], render.get("monochrome_palette", "amber"), False, "Monochrome palette.")
        self.v_cga_colors = self._add_opt(f_render, 2, 2, "CGA Colors:", ["default", "tandy", "tandy-warm", "ibm5153", "agi-amiga-v1", "agi-amiga-v2", "agi-amiga-v3", "colodore", "dga16"], render.get("cga_colors", "default"), True, "CGA color palette.")

        f_comp = tb.Labelframe(scrollable_frame, text="Composite (CGA/PCjr/Tandy)", bootstyle="warning", padding=10); f_comp.pack(fill=tk.X, padx=10, pady=5)
        self.v_composite = self._add_opt(f_comp, 0, 0, "Composite:", ["auto", "on", "off"], composite.get("composite", "auto"), False, "Enable composite mode.")
        self.v_era = self._add_opt(f_comp, 0, 2, "Era:", ["auto", "old", "new"], composite.get("era", "auto"), False, "Composite era.")
        self.v_hue = self._add_spinbox_to_frame(f_comp, 1, 0, composite, "hue", -180, 180, "Hue:", "Hue of RGB palette.", default_val=0)
        self.v_saturation = self._add_spinbox_to_frame(f_comp, 1, 2, composite, "saturation", 0, 200, "Saturation:", "Intensity of colors.", default_val=100)
        self.v_contrast = self._add_spinbox_to_frame(f_comp, 2, 0, composite, "contrast", 0, 200, "Contrast:", "Contrast ratio.", default_val=100)
        self.v_brightness = self._add_spinbox_to_frame(f_comp, 2, 2, composite, "brightness", -100, 100, "Brightness:", "Luminosity.", default_val=0)
        self.v_convergence = self._add_spinbox_to_frame(f_comp, 3, 0, composite, "convergence", -100, 100, "Convergence:", "Convergence of subpixels.", default_val=0)

        f_machine = tb.Labelframe(scrollable_frame, text="Machine & Video Memory", bootstyle="success", padding=10); f_machine.pack(fill=tk.X, padx=10, pady=5)
        self.v_machine = self._add_opt(f_machine, 0, 0, "Machine Type:", ["svga_s3", "svga_et4000", "svga_paradise", "vesa_nolfb", "hercules", "cga", "tandy", "pcjr", "ega"], dosbox.get("machine", "svga_s3"), False, "Type of machine and video card to emulate.", var_name="machine")
        self.v_vmemsize = self._add_opt(f_machine, 0, 2, "VRAM (KB):", ["auto", "512", "1024", "2048", "4096", "8192"], str(dosbox.get("vmemsize", "auto")), True, "Amount of emulated video memory.")
        
        f_voodoo = tb.Labelframe(scrollable_frame, text="3dfx Voodoo", bootstyle="secondary", padding=10); f_voodoo.pack(fill=tk.X, padx=10, pady=5)
        self.v_voodoo = self._add_bool(f_voodoo, "Enable Voodoo", voodoo.get("voodoo", True), 0, 0, "Enable 3dfx Voodoo emulation.", var_name="voodoo")
        self.v_voodoo_memsize = self._add_opt(f_voodoo, 0, 2, "VRAM (MB):", ["4", "12"], str(voodoo.get("voodoo_memsize", "4")), False, "Voodoo VRAM amount.")
        self.v_voodoo_threads = self._add_opt(f_voodoo, 1, 0, "Threads:", ["auto", "1", "2", "4"], str(voodoo.get("voodoo_threads", "auto")), True, "Number of threads.")
        self.v_voodoo_bilinear = self._add_bool(f_voodoo, "Bilinear Filtering", voodoo.get("voodoo_bilinear_filtering", True), 1, 2, "Use bilinear filtering.")

    def _build_joystick_other_tab(self, parent):
        settings = self.game_data.get("dosbox_settings", {}); joystick = settings.get("joystick", {}); serial = settings.get("serial", {}); reelmagic = settings.get("reelmagic", {}); mouse = settings.get("mouse", {}); canvas = tk.Canvas(parent, highlightthickness=0); scrollbar = tb.Scrollbar(parent, orient="vertical", command=canvas.yview, bootstyle="round"); scrollable_frame = tb.Frame(canvas); scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set); canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y"); f_mouse = tb.Labelframe(scrollable_frame, text="Mouse", bootstyle="info", padding=10); f_mouse.pack(fill=tk.X, padx=10, pady=5); self.v_mouse_capture = self._add_opt(f_mouse, 0, 0, "Capture:", ["onclick", "onstart", "seamless", "nomouse"], mouse.get("mouse_capture", "onclick"), False, "How mouse is captured."); self.v_dos_mouse_driver = self._add_bool(f_mouse, "Built-in Driver", mouse.get("dos_mouse_driver", True), 0, 2, "Use built-in DOS mouse driver."); self.v_mouse_sensitivity = self._add_spinbox_to_frame(f_mouse, 1, 0, mouse, "mouse_sensitivity", 1, 1000, "Sensitivity (%):", "Mouse sensitivity.", default_val=100); self.v_ps2_mouse_model = self._add_opt(f_mouse, 2, 0, "PS/2 Mouse:", ["standard", "intellimouse", "explorer", "none"], mouse.get("ps2_mouse_model", "explorer"), False, "Emulated PS/2 mouse type."); 
        
        # New Mouse Settings
        self.v_mouse_middle_release = self._add_bool(f_mouse, "Middle Click Release", mouse.get("mouse_middle_release", True), 0, 3, "Release captured mouse by middle-clicking."); self.v_mouse_multi_display_aware = self._add_bool(f_mouse, "Multi-Display Aware", mouse.get("mouse_multi_display_aware", True), 1, 2, "Allow seamless mouse in fullscreen on multi-display."); self.v_mouse_raw_input = self._add_bool(f_mouse, "Raw Input", mouse.get("mouse_raw_input", True), 1, 3, "Bypass OS mouse acceleration."); self.v_dos_mouse_immediate = self._add_bool(f_mouse, "Immediate Update", mouse.get("dos_mouse_immediate", False), 2, 2, "Update mouse movement counters immediately."); self.v_com_mouse_model = self._add_opt(f_mouse, 2, 3, "COM Mouse:", ["2button", "3button", "wheel", "msm", "2button+msm", "3button+msm", "wheel+msm"], mouse.get("com_mouse_model", "wheel+msm"), False, "Serial mouse model."); self.v_vmware_mouse = self._add_bool(f_mouse, "VMware Mouse", mouse.get("vmware_mouse", True), 3, 0, "VMware mouse interface."); self.v_virtualbox_mouse = self._add_bool(f_mouse, "VirtualBox Mouse", mouse.get("virtualbox_mouse", True), 3, 1, "VirtualBox mouse interface.")
        
        f_joy = tb.Labelframe(scrollable_frame, text="Joystick", bootstyle="success", padding=10); f_joy.pack(fill=tk.X, padx=10, pady=5)
        self.v_joysticktype = self._add_opt(f_joy, 0, 0, "Type:", ["auto", "2axis", "4axis", "fcs", "ch", "hidden", "disabled"], joystick.get("joysticktype", "auto"), False, "Emulated joystick type.")
        self.v_timed = self._add_bool(f_joy, "Timed Intervals", joystick.get("timed", True), 0, 2, "Enable timed intervals for axes.")
        self.v_autofire = self._add_bool(f_joy, "Autofire", joystick.get("autofire", False), 0, 3, "Enable autofire.")
        self.v_swap34 = self._add_bool(f_joy, "Swap 3/4", joystick.get("swap34", False), 1, 2, "Swap 3rd and 4th axes.")
        self.v_button_wrap = self._add_bool(f_joy, "Button Wrap", joystick.get("button_wrap", False), 1, 3, "Wrap buttons.")
        self.v_deadzone = self._add_spinbox_to_frame(f_joy, 1, 0, joystick, "deadzone", 0, 100, "Deadzone (%):", "Axis movement deadzone.")
        self.v_circularinput = self._add_bool(f_joy, "Circular Input", joystick.get("circularinput", False), 2, 0, "Circular input.")
        
        f_serial = tb.Labelframe(scrollable_frame, text="Serial Ports", bootstyle="secondary", padding=10); f_serial.pack(fill=tk.X, padx=10, pady=5); self.v_serial1 = self._add_opt(f_serial, 0, 0, "Serial 1:", ["dummy", "disabled", "mouse", "modem", "nullmodem", "direct"], serial.get("serial1", "dummy"), False, "Device on COM1."); self.v_serial2 = self._add_opt(f_serial, 0, 2, "Serial 2:", ["dummy", "disabled", "mouse", "modem", "nullmodem", "direct"], serial.get("serial2", "dummy"), False, "Device on COM2."); f_reel = tb.Labelframe(scrollable_frame, text="ReelMagic", bootstyle="warning", padding=10); f_reel.pack(fill=tk.X, padx=10, pady=5); self.v_reelmagic = self._add_bool(f_reel, "Enable ReelMagic", reelmagic.get("reelmagic", False), 0, 0, "Enable ReelMagic MPEG card support.")

    def _build_network_tab(self, parent):
        settings = self.game_data.get("dosbox_settings", {}); ipx = settings.get("ipx", {}); ether = settings.get("ethernet", {}); canvas = tk.Canvas(parent, highlightthickness=0); scrollbar = tb.Scrollbar(parent, orient="vertical", command=canvas.yview, bootstyle="round"); scrollable_frame = tb.Frame(canvas); scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set); canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")

        f_ipx = tb.Labelframe(scrollable_frame, text="IPX", bootstyle="info", padding=10); f_ipx.pack(fill=tk.X, padx=10, pady=5)
        self.v_ipx = self._add_bool(f_ipx, "Enable IPX", ipx.get("ipx", False), 0, 0, "Enable IPX over UDP/IP emulation.")

        f_eth = tb.Labelframe(scrollable_frame, text="Ethernet (NE2000)", bootstyle="success", padding=10); f_eth.pack(fill=tk.X, padx=10, pady=5)
        self.v_ne2000 = self._add_bool(f_eth, "Enable NE2000", ether.get("ne2000", False), 0, 0, "Enable NE2000 network card.")
        self.v_nicbase = self._add_opt(f_eth, 0, 2, "Base Address:", ["300", "200", "220", "240", "260", "280", "2c0", "320", "340", "360"], str(ether.get("nicbase", "300")), True, "Base address of the card.")
        self.v_nicirq = self._add_opt(f_eth, 1, 0, "IRQ:", ["3", "4", "5", "9", "10", "11", "12", "15"], str(ether.get("nicirq", "3")), True, "IRQ of the card.")
        self.v_macaddr = self._add_opt(f_eth, 1, 2, "MAC Address:", ["AC:DE:48:88:99:AA"], ether.get("macaddr", "AC:DE:48:88:99:AA"), True, "MAC address.")
        self.v_backend = self._add_opt(f_eth, 2, 0, "Backend:", ["auto", "slirp", "pcap", "tap"], ether.get("backend", "auto"), False, "Network backend.")

    def _get_current_ui_values(self):
        # Use game_data as base to capture Expert tab changes
        base_data = getattr(self, 'game_data', self.initial_data)
        data = json.loads(json.dumps(base_data))
        
        data.update({'title': self.v_title.get().strip() or self.name, 'year': self.v_year.get().strip(), 'genre': self.v_genre.get(), 'developers': self.v_developers.get().strip(), 'publishers': self.v_publishers.get().strip(), 'num_players': self.v_num_players.get().strip(), 'rating': self.cb_rating.current(), 'critics_score': int(self.v_critics_score.get()), 'description': self.t_desc.get(1.0, tk.END).strip(), "video_links": [{"title": self.video_tree.item(i, "values")[0], "url": self.video_tree.item(i, "values")[1]} for i in self.video_tree.get_children()], "custom_fields": {k:v for line in self.t_custom.get(1.0, tk.END).strip().splitlines() if ":" in line and (k_v := line.split(":", 1)) and (k:=k_v[0].strip()) and (v:=k_v[1].strip())}})
        
        # Explicitly save Reference Config
        if hasattr(self, 'selected_conf_var'):
            data['reference_conf'] = self.selected_conf_var.get()

        if self.is_installed:
            # Save Mounts
            if hasattr(self, 'mounts_tree'):
                mounts = []
                for item in self.mounts_tree.get_children():
                    vals = self.mounts_tree.item(item, "values")
                    mounts.append({
                        "drive": vals[0],
                        "type": vals[1],
                        "path": vals[2],
                        "label": vals[3],
                        "as": vals[4]
                    })
                data['mounts'] = mounts
            elif hasattr(self, 'mount_c_var'):
                data['mount_c'] = self.mount_c_var.get().strip()
                if hasattr(self, 'mount_d_var'): data['mount_d'] = self.mount_d_var.get().strip()
            
            if hasattr(self, 'custom_conf_text'):
                data['custom_config_content'] = self.custom_conf_text.text.get(1.0, tk.END).strip()
            
            # Capture new Autoexec fields
            if hasattr(self, 't_autoexec_pre'):
                text = self.t_autoexec_pre.text.get("1.0", tk.END).strip()
                if text:
                    data['autoexec_pre'] = text.splitlines()
                else:
                    data['autoexec_pre'] = []
            
            if hasattr(self, 't_autoexec_post'):
                text = self.t_autoexec_post.text.get("1.0", tk.END).strip()
                if text:
                    data['autoexec_post'] = text.splitlines()
                else:
                    data['autoexec_post'] = []
            
            # Legacy support: If we have custom_autoexec but no pre/post, maybe we should keep it?
            # But we are moving away from it.
            # If the user edits the new fields, we should probably clear the old custom_autoexec to avoid confusion
            # or use it as a fallback.
            # For now, let's clear custom_autoexec if we are using the new system
            if 'custom_autoexec' in data:
                del data['custom_autoexec']

            if hasattr(self, 'exe_widgets'):
                data["executables"] = {exe: {"role": constants.ROLE_KEYS.get(vr.get()), "title": vt.get().strip(), "params": vp.get().strip()} for exe, vr, vt, vp in self.exe_widgets}
            else:
                # If exe_widgets not initialized (tab not visited), keep existing executables data
                # But we must ensure we don't lose it.
                # base_data already has it.
                pass
            
            if hasattr(self, 'v_dosbox_path_name'):
                selected_dosbox_name = self.v_dosbox_path_name.get()
            else:
                selected_dosbox_name = "(Use Default)"
                
            data["custom_dosbox_path"] = ""
            
            # Check if selected name matches a known installation
            known_inst = next((inst for inst in self.dosbox_installations if inst['name'] == selected_dosbox_name), None)
            
            if known_inst:
                data["custom_dosbox_path"] = known_inst['path']
            elif selected_dosbox_name != "(Use Default)":
                # Assume it's a custom path directly set (e.g. by Expert tab)
                data["custom_dosbox_path"] = selected_dosbox_name

            if "dosbox_settings" not in data: data["dosbox_settings"] = {}
            
            # Only update from variables if they exist (tabs might be removed)
            # We need to be careful here. If we removed the tabs, the variables (v_machine, etc.) might not be initialized
            # unless we initialize them somewhere else or check for existence.
            # The _add_opt helper creates them as attributes of self.
            # But if _build_dosbox_tab wasn't called, v_machine won't exist.
            # We should check for existence before accessing .get()
            
            def get_val(var_name, default=None):
                if hasattr(self, f"v_{var_name}"):
                    val = getattr(self, f"v_{var_name}").get()
                    if isinstance(val, bool): return str(val).lower()
                    return val
                # If variable doesn't exist, try to get from current game_data to preserve it
                # But we need to know where in game_data it is.
                # This is getting complicated because the mapping is implicit in the update structure below.
                # For now, let's just use safe access.
                return default

            # We can't easily preserve values if we don't know where they come from without the mapping.
            # However, since we removed the tabs, the user can't change them via UI (except Expert tab).
            # So we should probably NOT overwrite them with empty/default values if the UI is missing.
            # Instead, we should start with existing dosbox_settings and only update what we have UI for.
            
            # data['dosbox_settings'] already has the initial data (from self.initial_data deep copy)
            # So we just need to update the keys that we actually have widgets for.
            
            # Let's define a helper to update only if widget exists
            def update_if_exists(section, key, var_name, is_bool=False):
                if hasattr(self, f"v_{var_name}"):
                    val = getattr(self, f"v_{var_name}").get()
                    if is_bool: val = str(val).lower()
                    if section not in data['dosbox_settings']: data['dosbox_settings'][section] = {}
                    data['dosbox_settings'][section][key] = val

            # Update DOSBox settings
            update_if_exists('dosbox', 'machine', 'machine')
            update_if_exists('dosbox', 'memsize', 'memsize')
            update_if_exists('dosbox', 'vmemsize', 'vmemsize')
            update_if_exists('dosbox', 'language', 'language')
            update_if_exists('dosbox', 'mcb_fault_strategy', 'mcb_fault')
            update_if_exists('dosbox', 'vmem_delay', 'vmem_delay')
            update_if_exists('dosbox', 'dos_rate', 'dos_rate')
            update_if_exists('dosbox', 'vesa_modes', 'vesa_modes')
            update_if_exists('dosbox', 'vga_8dot_font', 'vga_8dot', True)
            update_if_exists('dosbox', 'vga_render_per_scanline', 'vga_render', True)
            update_if_exists('dosbox', 'speed_mods', 'speed_mods', True)
            update_if_exists('dosbox', 'autoexec_section', 'autoexec_section')
            update_if_exists('dosbox', 'automount', 'automount', True)
            update_if_exists('dosbox', 'startup_verbosity', 'startup_verbosity')
            update_if_exists('dosbox', 'allow_write_protected_files', 'write_protected', True)
            update_if_exists('dosbox', 'shell_config_shortcuts', 'shell_shortcuts', True)
            
            update_if_exists('cpu', 'core', 'core')
            update_if_exists('cpu', 'cputype', 'cputype')
            
            # Special handling for cycles/cpu_cycles
            # If we are in Staging mode, we should NOT write 'cycles' if 'cpu_cycles' is present.
            # And we should ensure 'cycles' is removed if it exists.
            
            is_staging = False
            if hasattr(self, 'detected_variant') and "staging" in self.detected_variant.lower(): is_staging = True
            elif "staging" in data.get("custom_dosbox_path", "").lower(): is_staging = True
            elif "staging" in data.get("reference_conf", "").lower(): is_staging = True
            elif not data.get("custom_dosbox_path") and self.logic.default_dosbox_exe and "staging" in self.logic.default_dosbox_exe.lower(): is_staging = True
            
            if is_staging:
                # Use v_cycles for cpu_cycles if available (since we bind v_cycles to cpu_cycles in Staging)
                if hasattr(self, 'v_cycles'):
                     if 'cpu' not in data['dosbox_settings']: data['dosbox_settings']['cpu'] = {}
                     data['dosbox_settings']['cpu']['cpu_cycles'] = self.v_cycles.get()
                else:
                     # Fallback if v_cycles missing (e.g. tab not built), try v_cpu_cycles if it existed
                     update_if_exists('cpu', 'cpu_cycles', 'cpu_cycles')

                # Check for DOS4GW logic
                has_dos4gw = getattr(self, 'has_dos4gw', False)
                if has_dos4gw:
                     if 'cpu' not in data['dosbox_settings']: data['dosbox_settings']['cpu'] = {}
                     data['dosbox_settings']['cpu']['cpu_cycles'] = 'auto'
                
                # Explicitly remove 'cycles' if it exists in data['dosbox_settings']['cpu']
                if 'cpu' in data['dosbox_settings'] and 'cycles' in data['dosbox_settings']['cpu']:
                    del data['dosbox_settings']['cpu']['cycles']
            else:
                update_if_exists('cpu', 'cycles', 'cycles')
                # We don't necessarily remove cpu_cycles here as it might be harmless or used by X too?
                # But usually X uses cycles.
            
            # Final cleanup for Staging-like keys (Aggressive check)
            # If we have cpu_cycles or cpu_cycles_protected, we assume we don't want cycles.
            if 'cpu' in data['dosbox_settings']:
                cpu_sec = data['dosbox_settings']['cpu']
                if 'cpu_cycles' in cpu_sec or 'cpu_cycles_protected' in cpu_sec:
                    if 'cycles' in cpu_sec:
                        del cpu_sec['cycles']
            
            update_if_exists('cpu', 'cpu_cycles_protected', 'cpu_cycles_protected')
            update_if_exists('cpu', 'use_protected_cycles', 'use_protected_cycles', True)
            update_if_exists('cpu', 'cpu_throttle', 'cpu_throttle')
            update_if_exists('cpu', 'cycleup', 'cycleup')
            update_if_exists('cpu', 'cycledown', 'cycledown')
            
            update_if_exists('mouse', 'mouse_capture', 'mouse_capture')
            update_if_exists('mouse', 'dos_mouse_driver', 'dos_mouse_driver', True)
            update_if_exists('mouse', 'mouse_sensitivity', 'mouse_sensitivity')
            update_if_exists('mouse', 'ps2_mouse_model', 'ps2_mouse_model')
            update_if_exists('mouse', 'mouse_middle_release', 'mouse_middle_release', True)
            update_if_exists('mouse', 'mouse_multi_display_aware', 'mouse_multi_display_aware', True)
            update_if_exists('mouse', 'mouse_raw_input', 'mouse_raw_input', True)
            update_if_exists('mouse', 'dos_mouse_immediate', 'dos_mouse_immediate', True)
            update_if_exists('mouse', 'com_mouse_model', 'com_mouse_model')
            update_if_exists('mouse', 'vmware_mouse', 'vmware_mouse', True)
            update_if_exists('mouse', 'virtualbox_mouse', 'virtualbox_mouse', True)
            
            update_if_exists('mixer', 'nosound', 'nosound', True)
            update_if_exists('mixer', 'rate', 'rate')
            update_if_exists('mixer', 'blocksize', 'blocksize')
            update_if_exists('mixer', 'prebuffer', 'prebuffer')
            update_if_exists('mixer', 'compressor', 'compressor', True)
            update_if_exists('mixer', 'crossfeed', 'crossfeed')
            update_if_exists('mixer', 'reverb', 'reverb')
            update_if_exists('mixer', 'chorus', 'chorus')
            update_if_exists('mixer', 'negotiate', 'negotiate', True)
            
            update_if_exists('midi', 'mididevice', 'mididevice')
            update_if_exists('midi', 'midiconfig', 'midiconfig')
            update_if_exists('midi', 'mpu401', 'mpu401')
            update_if_exists('midi', 'raw_midi_output', 'raw_midi_output', True)
            
            update_if_exists('fluidsynth', 'soundfont', 'soundfont')
            update_if_exists('fluidsynth', 'fsynth_chorus', 'fsynth_chorus')
            update_if_exists('fluidsynth', 'fsynth_reverb', 'fsynth_reverb')
            update_if_exists('fluidsynth', 'fsynth_filter', 'fsynth_filter')
            
            update_if_exists('mt32', 'model', 'mt32_model')
            update_if_exists('mt32', 'romdir', 'romdir')
            update_if_exists('mt32', 'mt32_filter', 'mt32_filter')
            
            update_if_exists('sblaster', 'sbtype', 'sbtype')
            update_if_exists('sblaster', 'sbmixer', 'sbmixer', True)
            update_if_exists('sblaster', 'oplmode', 'oplmode')
            update_if_exists('sblaster', 'irq', 'irq')
            update_if_exists('sblaster', 'dma', 'dma')
            update_if_exists('sblaster', 'hdma', 'hdma')
            update_if_exists('sblaster', 'sb_filter', 'sb_filter')
            update_if_exists('sblaster', 'opl_filter', 'opl_filter')
            update_if_exists('sblaster', 'sb_warmup', 'sb_warmup', True)
            
            update_if_exists('gus', 'gus', 'gus', True)
            update_if_exists('gus', 'ultradir', 'ultradir')
            update_if_exists('gus', 'gus_rate', 'gus_rate')
            update_if_exists('gus', 'gus_base', 'gus_base')
            update_if_exists('gus', 'gus_irq1', 'gus_irq1')
            update_if_exists('gus', 'gus_irq2', 'gus_irq2')
            update_if_exists('gus', 'gus_dma1', 'gus_dma1')
            update_if_exists('gus', 'gus_dma2', 'gus_dma2')
            update_if_exists('gus', 'gus_filter', 'gus_filter')
            
            update_if_exists('speaker', 'pcspeaker', 'pcspeaker')
            update_if_exists('speaker', 'tandy', 'tandy')
            update_if_exists('speaker', 'lpt_dac', 'lpt_dac')
            update_if_exists('speaker', 'ps1audio', 'ps1audio', True)
            update_if_exists('speaker', 'pcspeaker_filter', 'pcspeaker_filter')
            update_if_exists('speaker', 'tandy_filter', 'tandy_filter')
            update_if_exists('speaker', 'lpt_dac_filter', 'lpt_dac_filter')
            
            update_if_exists('imfc', 'imfc', 'imfc', True)
            update_if_exists('imfc', 'imfc_base', 'imfc_base')
            
            update_if_exists('innovation', 'innovation', 'innovation', True)
            update_if_exists('innovation', 'innovation_base', 'innovation_base')
            update_if_exists('innovation', 'innovation_model', 'innovation_model')
            update_if_exists('innovation', 'innovation_filter', 'innovation_filter')
            
            update_if_exists('joystick', 'joysticktype', 'joysticktype')
            update_if_exists('joystick', 'timed', 'timed', True)
            update_if_exists('joystick', 'deadzone', 'deadzone')
            update_if_exists('joystick', 'autofire', 'autofire', True)
            update_if_exists('joystick', 'swap34', 'swap34', True)
            update_if_exists('joystick', 'button_wrap', 'button_wrap', True)
            update_if_exists('joystick', 'circularinput', 'circularinput', True)
            
            update_if_exists('serial', 'serial1', 'serial1')
            update_if_exists('serial', 'serial2', 'serial2')
            
            update_if_exists('reelmagic', 'reelmagic', 'reelmagic', True)
            
            update_if_exists('dos', 'ver', 'ver')
            update_if_exists('dos', 'keyboardlayout', 'keyboardlayout')
            update_if_exists('dos', 'xms', 'xms', True)
            update_if_exists('dos', 'ems', 'ems')
            update_if_exists('dos', 'umb', 'umb', True)
            update_if_exists('dos', 'hard_drive_data_rate_limit', 'hard_drive_data_rate_limit')
            update_if_exists('dos', 'file_locking', 'file_locking', True)
            update_if_exists('dos', 'automount_all_drives', 'automount_all_drives', True)
            update_if_exists('dos', 'files', 'files')
            update_if_exists('dos', 'minimum_mcb_free', 'minimum_mcb_free')
            update_if_exists('dos', 'lfn', 'lfn')
            update_if_exists('dos', 'fat32', 'fat32', True)
            update_if_exists('dos', 'int33', 'int33', True)
            
            update_if_exists('sdl', 'output', 'output')
            update_if_exists('sdl', 'fullscreen', 'fullscreen', True)
            update_if_exists('sdl', 'vsync', 'vsync')
            update_if_exists('sdl', 'windowresolution', 'windowresolution')
            update_if_exists('sdl', 'fullresolution', 'fullresolution')
            update_if_exists('sdl', 'texture_renderer', 'texture_renderer')
            update_if_exists('sdl', 'display', 'display')
            update_if_exists('sdl', 'window_position', 'window_position')
            update_if_exists('sdl', 'window_decorations', 'window_decorations', True)
            update_if_exists('sdl', 'window_titlebar', 'window_titlebar')
            update_if_exists('sdl', 'transparency', 'transparency')
            update_if_exists('sdl', 'host_rate', 'host_rate')
            update_if_exists('sdl', 'vsync_skip', 'vsync_skip')
            update_if_exists('sdl', 'presentation_mode', 'presentation_mode')
            update_if_exists('sdl', 'waitonerror', 'waitonerror', True)
            update_if_exists('sdl', 'priority', 'priority')
            update_if_exists('sdl', 'mute_when_inactive', 'mute_inactive', True)
            update_if_exists('sdl', 'pause_when_inactive', 'pause_inactive', True)
            update_if_exists('sdl', 'mapperfile', 'mapperfile')
            update_if_exists('sdl', 'screensaver', 'screensaver')
            
            update_if_exists('render', 'aspect', 'aspect', True)
            update_if_exists('render', 'glshader', 'glshader')
            update_if_exists('render', 'integer_scaling', 'integer_scaling')
            update_if_exists('render', 'viewport', 'viewport')
            update_if_exists('render', 'monochrome_palette', 'monochrome')
            update_if_exists('render', 'cga_colors', 'cga_colors')
            
            update_if_exists('composite', 'composite', 'composite')
            update_if_exists('composite', 'era', 'era')
            update_if_exists('composite', 'hue', 'hue')
            update_if_exists('composite', 'saturation', 'saturation')
            update_if_exists('composite', 'contrast', 'contrast')
            update_if_exists('composite', 'brightness', 'brightness')
            update_if_exists('composite', 'convergence', 'convergence')
            
            update_if_exists('voodoo', 'voodoo', 'voodoo', True)
            update_if_exists('voodoo', 'voodoo_memsize', 'voodoo_memsize')
            update_if_exists('voodoo', 'voodoo_threads', 'voodoo_threads')
            update_if_exists('voodoo', 'voodoo_bilinear_filtering', 'voodoo_bilinear', True)
            
            update_if_exists('ipx', 'ipx', 'ipx', True)
            
            update_if_exists('ethernet', 'ne2000', 'ne2000', True)
            update_if_exists('ethernet', 'nicbase', 'nicbase')
            update_if_exists('ethernet', 'nicirq', 'nicirq')
            update_if_exists('ethernet', 'macaddr', 'macaddr')
            update_if_exists('ethernet', 'backend', 'backend')
            
            # Apply Expert Overrides
            if hasattr(self, 'expert_tree'):
                for item in self.expert_tree.get_children():
                    vals = self.expert_tree.item(item, "values")
                    sec, key, val = vals[0], vals[1], vals[2]
                    if sec not in data['dosbox_settings']: data['dosbox_settings'][sec] = {}
                    data['dosbox_settings'][sec][key] = val
                    
        return data

    def _save(self, new_data=None, refresh=True, close=True):
        if new_data is None: new_data = self._get_current_ui_values()
        
        # Explicitly save Reference Config
        if hasattr(self, 'selected_conf_var'):
            new_data['reference_conf'] = self.selected_conf_var.get()

        # Auto-regenerate config content from settings (User Request)
        # Use minimal=True to only write differences from reference config
        main_exe = next((exe for exe, info in new_data.get("executables", {}).items() if info.get("role") == constants.ROLE_MAIN), None)
        generated_lines = self.logic.generate_config_content(self.name, main_exe, new_data, minimal=True)
        new_data['custom_config_content'] = "\n".join(generated_lines)

        new_title = new_data.get('title', self.name)
        renamed_zip = None
        if new_title != self.original_name:
            new_name, error = self.logic.rename_game(self.original_name, new_title)
            if error: messagebox.showerror("Rename Error", error, parent=self); return
            self.name = new_name; self.zip_name = f"{new_name}.zip"; self.original_name = new_name; self.title(f"Configuration: {self.name}"); renamed_zip = self.zip_name
        self.logic.save_game_details(self.name, new_data); self.logic.update_dosbox_conf(self.name, new_data, from_content=True); self.initial_data = json.loads(json.dumps(new_data)); self.save_button.config(state="disabled", bootstyle="success"); self.has_unsaved_changes = False
        
        if not close and hasattr(self, 'custom_conf_text') and self.custom_conf_text.winfo_exists():
             self.custom_conf_text.text.delete("1.0", tk.END)
             self.custom_conf_text.text.insert("1.0", new_data.get('custom_config_content', ''))

        if refresh: self.parent_app.refresh_library(renamed_zip=renamed_zip)
        if close: self.destroy()

    def _add_opt(self, parent, row, col, label, opts, val, editable=False, tooltip=None, var_name=None):
        # If var_name is provided, try to use existing variable or create and store it
        if var_name and hasattr(self, f"v_{var_name}"):
            var = getattr(self, f"v_{var_name}")
            # Update value if needed? No, keep existing value as it might be shared.
        else:
            var = tk.StringVar(value=val)
            if var_name: setattr(self, f"v_{var_name}", var)
            
        label_widget = tb.Label(parent, text=label); label_widget.grid(row=row, column=col, sticky="w", padx=(10,5), pady=2)
        widget = tb.Combobox(parent, values=opts, textvariable=var, state="normal" if editable else "readonly", width=15) if opts else tb.Entry(parent, textvariable=var, width=18); widget.grid(row=row, column=col+1, sticky="w", padx=5, pady=2)
        widget.bind("<<ComboboxSelected>>", self._mark_as_changed)
        if editable: widget.bind("<KeyRelease>", self._mark_as_changed)
        if tooltip: ToolTip(label_widget, text=tooltip, bootstyle="info"); ToolTip(widget, text=tooltip, bootstyle="info")
        return var
        
    def _add_bool_to_var(self, var, parent, txt, command=None, padx=0):
        def on_change(): self._mark_as_changed(); command and command()
        cb = tb.Checkbutton(parent, text=txt, variable=var, bootstyle="round-toggle", command=on_change); cb.pack(side=tk.LEFT, padx=padx); return var

    def _add_bool(self, parent, txt, val_str, row=None, col=None, tooltip=None, var_name=None):
        if var_name and hasattr(self, f"v_{var_name}"):
            v = getattr(self, f"v_{var_name}")
        else:
            v = tk.BooleanVar(value=(str(val_str).lower() == "true"))
            if var_name: setattr(self, f"v_{var_name}", v)
            
        cb = tb.Checkbutton(parent, text=txt, variable=v, bootstyle="round-toggle", command=self._mark_as_changed)
        if row is not None and col is not None: cb.grid(row=row, column=col, sticky='w', padx=10, pady=2)
        else: cb.pack(side=tk.LEFT, padx=10)
        if tooltip: ToolTip(cb, text=tooltip, bootstyle="info")
        return v
        
    def _add_spinbox_to_frame(self, frame, row, col, data_dict, key, from_, to, label_text=None, tooltip=None, default_val=0):
        if hasattr(self, f"v_{key}"):
            var = getattr(self, f"v_{key}")
        else:
            var = tk.IntVar(value=data_dict.get(key, default_val)); setattr(self, f"v_{key}", var)
            
        label_widget = tb.Label(frame, text=label_text or f"{key.capitalize()}:"); label_widget.grid(row=row, column=col, sticky='w', pady=2, padx=(10,5))
        widget = tb.Spinbox(frame, from_=from_, to=to, textvariable=var, width=8, command=self._mark_as_changed); widget.grid(row=row, column=col+1, sticky='w', pady=2, padx=5)
        if tooltip: ToolTip(label_widget, text=tooltip, bootstyle="info"); ToolTip(widget, text=tooltip, bootstyle="info")
        widget.bind("<KeyRelease>", self._mark_as_changed); return var