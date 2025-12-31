import tkinter as tk
from tkinter import messagebox, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import os
import webbrowser
import shutil

class StartWizard(tb.Toplevel):
    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.logic = parent_app.logic
        self.settings = parent_app.settings
        
        self.title("First Run Setup Wizard")
        self.geometry("900x700")
        self.transient(parent_app)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.current_step = 0
        self.steps = [
            self.step_intro,
            self.step_create_folders,
            self.step_dosbox_install,
            self.step_database_check,
            self.step_finish
        ]
        
        self._init_ui()
        self._show_step(0)

    def on_close(self):
        if messagebox.askyesno("Exit Setup?", "Setup is not complete. Are you sure you want to exit? The application may not function correctly.", parent=self):
            self.destroy()
            self.parent_app.destroy()

    def _init_ui(self):
        self.main_container = tb.Frame(self, padding=20)
        self.main_container.pack(fill=BOTH, expand=YES)
        
        # Header
        self.header_frame = tb.Frame(self.main_container)
        self.header_frame.pack(fill=X, pady=(0, 20))
        
        self.header_lbl = tb.Label(self.header_frame, text="", font="-size 18 -weight bold", bootstyle="primary")
        self.header_lbl.pack(side=LEFT)
        
        self.step_lbl = tb.Label(self.header_frame, text="", font="-size 10", bootstyle="secondary")
        self.step_lbl.pack(side=RIGHT, anchor="e")
        
        # Content Area
        self.content_frame = tb.Frame(self.main_container)
        self.content_frame.pack(fill=BOTH, expand=YES, padx=5, pady=5)
        
        # Footer (Buttons)
        self.footer_frame = tb.Frame(self.main_container)
        self.footer_frame.pack(fill=X, side=BOTTOM, pady=(20, 0))
        
        self.btn_cancel = tb.Button(self.footer_frame, text="Cancel", command=self.on_close, bootstyle="danger-outline")
        self.btn_cancel.pack(side=LEFT)
        
        self.btn_next = tb.Button(self.footer_frame, text="Next >", command=self._next_step, bootstyle="success")
        self.btn_next.pack(side=RIGHT)
        
        self.btn_prev = tb.Button(self.footer_frame, text="< Back", command=self._prev_step, bootstyle="secondary-outline")
        self.btn_prev.pack(side=RIGHT, padx=10)

    def _show_step(self, step_index):
        if step_index < 0 or step_index >= len(self.steps): return
        
        # Clear content frame
        for widget in self.content_frame.winfo_children():
            widget.destroy()
            
        self.current_step = step_index
        self.step_lbl.config(text=f"Step {step_index + 1} of {len(self.steps)}")
        
        # Update buttons
        self.btn_prev.config(state="normal" if step_index > 0 else "disabled")
        self.btn_next.config(text="Finish & Launch" if step_index == len(self.steps) - 1 else "Next >")
        
        self.steps[step_index]()

    def _prev_step(self):
        self._show_step(self.current_step - 1)

    def _next_step(self):
        # Validation logic
        if self.current_step == 2: # DOSBox Install
            if not self._validate_dosbox_install(): return
        
        if self.current_step < len(self.steps) - 1:
            self._show_step(self.current_step + 1)
        else:
            run_config = getattr(self, 'run_config_var', None) and self.run_config_var.get()
            self.destroy()
            self.parent_app.post_init_load(first_run_done=True)
            if run_config:
                self.parent_app.open_settings()

    # --- Step 1: Intro ---
    def step_intro(self):
        self.header_lbl.config(text="Welcome to DOSBVault")
        tb.Label(self.content_frame, text="It looks like this is your first time running the application.", font="-size 12").pack(anchor="w", pady=10)
        tb.Label(self.content_frame, text="This wizard will guide you through the initial setup to ensure everything is configured correctly.", wraplength=600).pack(anchor="w")
        tb.Label(self.content_frame, text="\nWe will set up folders, check for DOSBox, and configure your library.", wraplength=600).pack(anchor="w")

    # --- Step 2: Create Folders ---
    def step_create_folders(self):
        self.header_lbl.config(text="Creating Folders")
        tb.Label(self.content_frame, text="The following folders will be created in your application directory:", font="-weight bold").pack(anchor="w", pady=10)
        
        folders = {
            "archive": "Game archives...",
            "database": "Metadatas, conf files, screenshots etc.",
            "DOSBox": "Directory for dosboxes.",
            "export": "Exported games.",
            "games": "Your installed game library.",
            "log": "Application logs.",
            "themes": "UI themes."
        }
        
        sorted_folders = dict(sorted(folders.items()))
        
        for folder, desc in sorted_folders.items():
            f = tb.Frame(self.content_frame)
            f.pack(fill=X, pady=2)
            tb.Label(f, text=folder, font="-weight bold", width=10).pack(side=LEFT)
            tb.Label(f, text=f"- {desc}").pack(side=LEFT)
            
            # Create them now
            try:
                os.makedirs(os.path.join(os.getcwd(), folder), exist_ok=True)
            except OSError as e:
                messagebox.showerror("Error", f"Failed to create folder '{folder}': {e}", parent=self)
        
        # Create subfolders for database
        try:
            os.makedirs(os.path.join(os.getcwd(), "database", "templates"), exist_ok=True)
            os.makedirs(os.path.join(os.getcwd(), "database", "games_datainfo"), exist_ok=True)
        except OSError: pass
            
        tb.Label(self.content_frame, text="\nFolders created successfully!", bootstyle="success").pack(anchor="w", pady=20)

    # --- Step 3: DOSBox Installation ---
    def step_dosbox_install(self):
        self.header_lbl.config(text="DOSBox Installation")
        
        info_text = (
            "You need at least one DOSBox emulator installed.\n"
            "We recommend using 'Portable' versions placed in the 'DOSBox' folder.\n\n"
            "Recommended Structure:\n"
            "  DOSBox/\n"
            "    DosBox_Staging_v0.81/ (contains dosbox.exe)\n"
            "    DosBox_X_v2023/ (contains dosbox-x.exe)\n\n"
            "Please download and extract a DOSBox version now."
        )
        tb.Label(self.content_frame, text=info_text, justify=LEFT, wraplength=600).pack(anchor="w")
        
        # Links
        link_frame = tb.Frame(self.content_frame)
        link_frame.pack(fill=X, pady=10)
        
        def open_url(url): webbrowser.open(url)
        
        tb.Button(link_frame, text="Get DOSBox Staging", command=lambda: open_url("https://www.dosbox-staging.org/releases/windows/"), bootstyle="info-outline").pack(side=LEFT, padx=5)
        tb.Button(link_frame, text="Get DOSBox-X", command=lambda: open_url("https://github.com/joncampbell123/dosbox-x/releases"), bootstyle="info-outline").pack(side=LEFT, padx=5)
        tb.Button(link_frame, text="Get DOSBox (Original)", command=lambda: open_url("https://www.dosbox.com/download.php?main=1"), bootstyle="info-outline").pack(side=LEFT, padx=5)
        
        # Check area
        self.check_frame = tb.Frame(self.content_frame, bootstyle="secondary", padding=10)
        self.check_frame.pack(fill=X, pady=20)
        
        self.lbl_status = tb.Label(self.check_frame, text="Checking...", bootstyle="warning")
        self.lbl_status.pack(side=LEFT)
        
        tb.Button(self.check_frame, text="Refresh / Check Again", command=self._check_dosbox, bootstyle="warning").pack(side=RIGHT)
        
        # Default selection area (hidden initially)
        self.default_frame = tb.Frame(self.content_frame)
        self.default_frame.pack(fill=X, pady=10)
        
        # Initial check
        self._check_dosbox(initial=True)

    def _check_dosbox(self, initial=False):
        found = self.logic.check_dosbox_exists()
        
        # Clear previous radio buttons
        for widget in self.default_frame.winfo_children():
            widget.destroy()
            
        if found:
            self.lbl_status.config(text="DOSBox executable found!", bootstyle="success")
            self.btn_next.config(state="normal")
            
            # Show default selection
            tb.Label(self.default_frame, text="Select the default DOSBox version to use:", font="-weight bold").pack(anchor="w", pady=(10, 5))
            self.installations = self._scan_dosbox_installations()
            self.dosbox_var = tk.StringVar()
            
            if self.installations:
                for name, path in self.installations:
                    tb.Radiobutton(self.default_frame, text=f"{name} ({path})", variable=self.dosbox_var, value=path).pack(anchor="w", pady=2)
                self.dosbox_var.set(self.installations[0][1])
            
        else:
            self.lbl_status.config(text="No DOSBox executable found in 'DOSBox' folder.", bootstyle="danger")
            self.btn_next.config(state="disabled")
            if not initial:
                messagebox.showinfo("Not Found", "Could not find 'dosbox.exe' or 'dosbox-x.exe' in the DOSBox folder.\n\nPlease ensure you have extracted the emulator correctly.", parent=self)
        return found

    def _scan_dosbox_installations(self):
        found = []
        dosbox_root = os.path.join(os.getcwd(), "DOSBox")
        if os.path.exists(dosbox_root):
            for root, dirs, files in os.walk(dosbox_root):
                for f in files:
                    if f.lower() in ['dosbox.exe', 'dosbox-x.exe']:
                        full_path = os.path.join(root, f)
                        try:
                            rel_path = os.path.relpath(full_path, os.getcwd())
                        except ValueError:
                            rel_path = full_path
                        name = os.path.basename(os.path.dirname(full_path))
                        if name == "DOSBox": name = "DOSBox Root"
                        found.append((name, rel_path))
        return found

    def _validate_dosbox_install(self):
        if not self._check_dosbox(): return False
        
        selected = self.dosbox_var.get()
        if not selected:
            messagebox.showerror("Error", "Please select a default DOSBox version.", parent=self)
            return False
            
        # Save to settings
        install_list = []
        for name, path in self.installations:
            install_list.append({
                "name": name,
                "path": path,
                "default": (path == selected)
            })
        
        self.settings.set("dosbox_installations", install_list)
        return True

    # --- Step 4: Database Check ---
    def step_database_check(self):
        self.header_lbl.config(text="Offline Database")
        
        db_path = os.path.join(os.getcwd(), "database", "DOSmetainfo.csv")
        if os.path.exists(db_path):
            tb.Label(self.content_frame, text="✓ 'database/DOSmetainfo.csv' found.", bootstyle="success", font="-size 14").pack(pady=20)
            tb.Label(self.content_frame, text="You can use offline metadata lookup.").pack()
        else:
            tb.Label(self.content_frame, text="⚠ 'database/DOSmetainfo.csv' NOT found.", bootstyle="warning", font="-size 14").pack(pady=20)
            tb.Label(self.content_frame, text="Offline metadata lookup will not be available.").pack()
            tb.Label(self.content_frame, text="You can add this file later to the database folder.").pack()

    # --- Step 5: DOSBox Configuration ---
    # Removed as merged into Step 3

    # --- Step 5: Finish ---
    def step_finish(self):
        self.header_lbl.config(text="Setup Complete!")
        self.btn_next.config(text="Finish & Launch")
        
        # Summary
        summary_frame = tb.Labelframe(self.content_frame, text="Setup Summary", padding=10)
        summary_frame.pack(fill=X, pady=10)
        
        # Folders
        tb.Label(summary_frame, text="✓ Folders created successfully.", bootstyle="success").pack(anchor="w")
        
        # DOSBox
        dosbox_installs = self.settings.get("dosbox_installations", [])
        default_db = next((d for d in dosbox_installs if d.get("default")), None)
        if default_db:
            tb.Label(summary_frame, text=f"✓ DOSBox found: {default_db['name']}", bootstyle="success").pack(anchor="w")
        else:
            tb.Label(summary_frame, text="⚠ DOSBox not configured.", bootstyle="warning").pack(anchor="w")
            
        # Database
        if os.path.exists(os.path.join(os.getcwd(), "database", "DOSmetainfo.csv")):
            tb.Label(summary_frame, text="✓ Database found.", bootstyle="success").pack(anchor="w")
        else:
            tb.Label(summary_frame, text="⚠ Database not found.", bootstyle="warning").pack(anchor="w")

        # Tips
        tips_frame = tb.Labelframe(self.content_frame, text="Tips & Tricks", padding=10)
        tips_frame.pack(fill=X, pady=10)
        
        tips = [
            "• Import games using 'Import ZIP(S)' (single or batch).",
            "• Right-click on any game in the list for more options.",
            "• Press CTRL+F5 in-game to take a screenshot (saved to 'screens').",
            "• 'DOSmetainfo.csv' makes filling metadata much easier."
        ]
        for tip in tips:
            tb.Label(tips_frame, text=tip).pack(anchor="w")

        # Run Config Checkbox
        self.run_config_var = tk.BooleanVar(value=False)
        tb.Checkbutton(self.content_frame, text="Run general configuration after wizard", variable=self.run_config_var, bootstyle="round-toggle").pack(pady=20)
