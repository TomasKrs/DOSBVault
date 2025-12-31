import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import os

class BatchUtilsWizard(tb.Toplevel):
    def __init__(self, parent, logic):
        super().__init__(parent)
        self.parent = parent
        self.logic = logic
        self.title("Batch Utilities")
        self.geometry("600x500")
        self.transient(parent)
        
        self.step = 1
        self.selected_games = []
        self.action = tk.StringVar(value="metadata")
        
        self._init_ui()
        self._show_step_1()

    def _init_ui(self):
        self.main_frame = tb.Frame(self, padding=10)
        self.main_frame.pack(fill=BOTH, expand=True)
        
        self.header = tb.Label(self.main_frame, text="Batch Utilities", font="-size 16 -weight bold")
        self.header.pack(pady=(0, 10))
        
        self.content_frame = tb.Frame(self.main_frame)
        self.content_frame.pack(fill=BOTH, expand=True)
        
        self.btn_frame = tb.Frame(self.main_frame)
        self.btn_frame.pack(fill=X, pady=(10, 0))
        
        self.btn_next = tb.Button(self.btn_frame, text="Next >", command=self._next, bootstyle="success")
        self.btn_next.pack(side=RIGHT)
        
        self.btn_cancel = tb.Button(self.btn_frame, text="Cancel", command=self.destroy, bootstyle="secondary")
        self.btn_cancel.pack(side=RIGHT, padx=10)

    def _show_step_1(self):
        for w in self.content_frame.winfo_children(): w.destroy()
        self.header.config(text="Step 1: Select Games")
        
        tb.Label(self.content_frame, text="Select the games you want to process:").pack(anchor="w", pady=(0, 5))
        
        # Listbox with checkboxes
        self.check_vars = {}
        
        scroll_frame = tb.Frame(self.content_frame)
        scroll_frame.pack(fill=BOTH, expand=True)
        
        canvas = tk.Canvas(scroll_frame)
        scrollbar = tb.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
        self.list_frame = tb.Frame(canvas)
        
        self.list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # Populate
        game_zips, _ = self.logic.get_game_list()
        
        # "Select All"
        self.var_all = tk.BooleanVar(value=False)
        def toggle_all():
            val = self.var_all.get()
            for v in self.check_vars.values(): v.set(val)
            
        tb.Checkbutton(self.list_frame, text="Select All", variable=self.var_all, command=toggle_all, bootstyle="round-toggle").pack(anchor="w", pady=5)
        tb.Separator(self.list_frame).pack(fill=X, pady=5)
        
        for zip_name in game_zips:
            name = os.path.splitext(zip_name)[0]
            var = tk.BooleanVar(value=False)
            self.check_vars[zip_name] = var
            tb.Checkbutton(self.list_frame, text=name, variable=var).pack(anchor="w")

    def _show_step_2(self):
        for w in self.content_frame.winfo_children(): w.destroy()
        self.header.config(text="Step 2: Select Action")
        
        tb.Label(self.content_frame, text=f"Selected {len(self.selected_games)} games.").pack(anchor="w", pady=(0, 10))
        
        modes = [
            ("Fetch Metadata (Offline DB)", "metadata"),
            ("Update Reference Config", "ref_config"),
            ("Delete Games", "delete"),
            ("Clear Metadata", "clear_meta")
        ]
        
        for text, mode in modes:
            tb.Radiobutton(self.content_frame, text=text, variable=self.action, value=mode).pack(anchor="w", pady=5)

        self.btn_next.config(text="Next >" if self.action.get() == "ref_config" else "Execute")
        
        def on_mode_change(*args):
            self.btn_next.config(text="Next >" if self.action.get() == "ref_config" else "Execute")
        self.action.trace("w", on_mode_change)

    def _show_step_3_ref_config(self):
        for w in self.content_frame.winfo_children(): w.destroy()
        self.header.config(text="Step 3: Select Reference Config")
        
        tb.Label(self.content_frame, text="Select the Reference Config to apply to selected games:").pack(anchor="w", pady=(0, 10))
        
        self.available_confs = self.logic.get_available_dosbox_confs()
        self.selected_conf_var = tk.StringVar()
        if self.available_confs:
            self.selected_conf_var.set(self.available_confs[0])
            
        cb_conf = tb.Combobox(self.content_frame, textvariable=self.selected_conf_var, values=self.available_confs, width=60, state="readonly")
        cb_conf.pack(fill=X, pady=10)
        
        self.btn_next.config(text="Execute")

    def _next(self):
        if self.step == 1:
            self.selected_games = [z for z, v in self.check_vars.items() if v.get()]
            if not self.selected_games:
                messagebox.showwarning("Selection", "Please select at least one game.", parent=self)
                return
            self.step = 2
            self._show_step_2()
        elif self.step == 2:
            if self.action.get() == "ref_config":
                self.step = 3
                self._show_step_3_ref_config()
            else:
                if messagebox.askyesno("Confirm", "Are you sure you want to proceed?", parent=self):
                    self._execute()
        elif self.step == 3:
            if messagebox.askyesno("Confirm", "Are you sure you want to proceed?", parent=self):
                self._execute()

    def _execute(self):
        action = self.action.get()
        count = 0
        
        if action == "ref_config":
            ref_conf = self.selected_conf_var.get()
            for zip_name in self.selected_games:
                try:
                    game_name = os.path.splitext(zip_name)[0]
                    details = self.logic.get_game_details(game_name)
                    details["reference_conf"] = ref_conf
                    
                    # Also clear custom_dosbox_path so it gets re-detected based on the new config
                    # or try to resolve it immediately
                    if "custom_dosbox_path" in details:
                        del details["custom_dosbox_path"]
                        
                    # We can try to resolve the engine path from the config path
                    # Similar logic to edit_window._refresh_expert_metadata
                    if not os.path.isabs(ref_conf):
                        abs_conf_path = os.path.join(self.logic.base_dir, ref_conf)
                    else:
                        abs_conf_path = ref_conf
                        
                    conf_dir = os.path.dirname(abs_conf_path)
                    local_dosbox_exe = None
                    potential_exes = ["dosbox.exe", "dosbox-x.exe", "dosbox-staging.exe"]
                    for exe in potential_exes:
                        p = os.path.join(conf_dir, exe)
                        if os.path.exists(p):
                            local_dosbox_exe = p
                            break
                            
                    if local_dosbox_exe:
                        details["custom_dosbox_path"] = local_dosbox_exe
                    
                    self.logic.save_game_details(game_name, details)
                    count += 1
                except Exception as e:
                    print(f"Error updating {zip_name}: {e}")
            messagebox.showinfo("Done", f"Updated Reference Config for {count} games.", parent=self)
        
        elif action == "metadata":
            self.parent.batch_metatag(self.selected_games) # Reuse existing logic but pass list
            self.destroy()
            return
            
        elif action == "delete":
            for zip_name in self.selected_games:
                try:
                    game_name = os.path.splitext(zip_name)[0]
                    # Delete installed folder
                    folder = self.logic.find_game_folder(game_name)
                    if os.path.exists(folder):
                        import shutil
                        shutil.rmtree(folder)
                    # Delete ZIP
                    zip_path = os.path.join(self.logic.zipped_dir, zip_name)
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                    # Delete Info
                    meta_dir = os.path.join(self.logic.base_dir, "database", "games_datainfo", game_name)
                    if os.path.exists(meta_dir):
                        shutil.rmtree(meta_dir)
                    count += 1
                except Exception as e:
                    print(f"Error deleting {zip_name}: {e}")
            messagebox.showinfo("Done", f"Deleted {count} games.", parent=self)
            
        elif action == "clear_meta":
            for zip_name in self.selected_games:
                game_name = os.path.splitext(zip_name)[0]
                details = self.logic.get_game_details(game_name)
                # Clear fields
                for key in ['year', 'genre', 'developers', 'publishers', 'num_players', 'description']:
                    details[key] = ""
                self.logic.save_game_details(game_name, details)
                count += 1
            messagebox.showinfo("Done", f"Cleared metadata for {count} games.", parent=self)

        self.parent.refresh_library()
        self.destroy()
