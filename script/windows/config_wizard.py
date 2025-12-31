import tkinter as tk
from tkinter import messagebox, simpledialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import os
import shutil
import re
import json
import zipfile
from datetime import datetime

from .. import constants
from .edit_window import EditWindow, GameSelectionDialog

class ConfigWizard(tb.Toplevel):
    def __init__(self, parent_app, zip_name, source_path=None, is_import=False, disable_config_option=False):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.logic = parent_app.logic
        self.zip_name = zip_name
        self.game_name = os.path.splitext(zip_name)[0]
        self.is_import = is_import
        self.source_path = source_path
        self.disable_config_option = disable_config_option
        
        if is_import and source_path:
            self.game_folder = source_path # Currently in !TEMP
            self.game_details = {} # Empty details for new import
        else:
            self.game_folder = self.logic.find_game_folder(self.game_name)
            self.game_details = self.logic.get_game_details(self.game_name)
        
        self.title(f"Config Wizard: {self.game_name}")
        self.geometry("800x600")
        self.transient(parent_app)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
        self.current_step = 0
        self.steps = [
            self.step_rename_game,
            self.step_dos_folder,
            self.step_metadata,
            self.step_mount_drives,
            self.step_executables,
            self.step_backup
        ]
        
        self.step_titles = [
            "1. Confirm Name & Import" if is_import else "1. Rename Game",
            "2. MS-DOS Folder Name",
            "3. Metadata",
            "4. Structure & Drives",
            "5. Executables",
            "6. Backup & Finish"
        ]
        
        # Skip Metadata step if database/DOSmetainfo.csv is missing
        if not os.path.exists(os.path.join(os.getcwd(), "database", "DOSmetainfo.csv")):
            self.steps.pop(2)
            self.step_titles.pop(2)
            # Renumber titles
            for i in range(len(self.step_titles)):
                parts = self.step_titles[i].split(". ", 1)
                if len(parts) == 2 and parts[0].isdigit():
                    self.step_titles[i] = f"{i+1}. {parts[1]}"
        
        # Data holder for the wizard session
        self.wizard_data = {}
        
        self._init_ui()
        self._show_step(0)

    def on_cancel(self):
        if self.is_import:
            if messagebox.askyesno("Cancel Import?", "This will cancel the import process.\n\n- The game will NOT be imported.\n- Temporary files will be deleted.\n- The original source ZIP/Folder will remain untouched.\n\nAre you sure?", parent=self):
                # Cleanup
                try:
                    if os.path.exists(self.game_folder):
                        shutil.rmtree(self.game_folder)
                    
                    # Remove placeholder zip if we created it
                    zip_path = os.path.join(self.logic.zipped_dir, self.zip_name)
                    if os.path.exists(zip_path):
                        # Check if it's really our placeholder (small size?)
                        # Or just assume yes since we are in import mode
                        os.remove(zip_path)
                except Exception as e:
                    print(f"Cleanup error: {e}")
                
                self.destroy()
                self.parent_app.refresh_library()
        else:
            self.destroy()

    def _init_ui(self):
        self.main_container = tb.Frame(self, padding=10)
        self.main_container.pack(fill=BOTH, expand=YES)
        
        # Header
        self.header_lbl = tb.Label(self.main_container, text="", font="-size 16 -weight bold", bootstyle="primary")
        self.header_lbl.pack(pady=(0, 10), anchor="w")
        
        # Progress Bar
        self.progress = tb.Floodgauge(self.main_container, bootstyle="success", font="-size 10", mask="Step {}/6")
        self.progress.pack(fill=X, pady=(0, 15))
        
        # Content Area
        self.content_frame = tb.Frame(self.main_container) # Removed bootstyle="light" to fix color issues
        self.content_frame.pack(fill=BOTH, expand=YES, padx=5, pady=5)
        
        # Footer (Buttons)
        self.footer_frame = tb.Frame(self.main_container)
        self.footer_frame.pack(fill=X, pady=(10, 0))
        
        self.btn_back = tb.Button(self.footer_frame, text="< Back", command=self._prev_step, bootstyle="secondary-outline")
        self.btn_back.pack(side=LEFT)
        
        self.btn_cancel = tb.Button(self.footer_frame, text="Cancel", command=self.on_cancel, bootstyle="danger-outline")
        self.btn_cancel.pack(side=LEFT, padx=10)
        
        self.btn_next = tb.Button(self.footer_frame, text="Next >", command=self._next_step, bootstyle="success")
        self.btn_next.pack(side=RIGHT)

    def _show_step(self, step_index):
        if step_index < 0 or step_index >= len(self.steps): return
        
        # Clear content frame
        for widget in self.content_frame.winfo_children():
            widget.destroy()
            
        self.current_step = step_index
        self.header_lbl.config(text=self.step_titles[step_index])
        self.progress.configure(value=((step_index + 1) / len(self.steps)) * 100, mask=f"Step {step_index + 1}/{len(self.steps)}")
        
        # Update buttons
        self.btn_back.config(state="normal" if step_index > 0 else "disabled")
        self.btn_next.config(text="Finish" if step_index == len(self.steps) - 1 else "Next >")
        
        # Execute step builder
        self.steps[step_index]()

    def _next_step(self):
        try:
            # Validation logic could go here based on current step
            if self.current_step == 0: # Rename
                if not self._validate_rename(): return
                # Auto-run standardization after rename/import confirmation
                self._run_standardization_logic()
                
            elif self.current_step == 1: # DOS Folder
                if not self._validate_dos_folder(): return
            elif self.current_step == 2: # Metadata
                 self._save_metadata()
            elif self.current_step == 4: # Executables
                 # Save executables config before moving on
                 self._save_executables()
            elif self.current_step == 5: # Backup
                 self._perform_backup()
                 self.destroy()
                 return

            self._show_step(self.current_step + 1)
        except Exception as e:
            messagebox.showerror("Wizard Error", f"An error occurred during this step:\n{e}", parent=self)
            print(f"Wizard Error: {e}")

    def _prev_step(self):
        self._show_step(self.current_step - 1)

    # --- Step 1: Rename Game ---
    def step_rename_game(self):
        if self.is_import:
            tb.Label(self.content_frame, text="Confirm Game Name & Import", font="-size 14 -weight bold").pack(anchor="w", pady=(10, 5))
            # Show ZIP name
            zip_base = os.path.splitext(self.zip_name)[0]
            tb.Label(self.content_frame, text=f"Importing: {zip_base}", bootstyle="info").pack(anchor="w", padx=10, pady=5)
            
            tb.Label(self.content_frame, text="The game is currently in a temporary folder. Please confirm the name to import it into your library.", wraplength=700).pack(anchor="w", padx=10, pady=5)
        else:
            tb.Label(self.content_frame, text="Current Game Name:", font="-weight bold").pack(anchor="w", pady=(10, 5))
            tb.Label(self.content_frame, text=self.game_name, bootstyle="info").pack(anchor="w", padx=10)
        
        tb.Label(self.content_frame, text="New Name (optional):" if not self.is_import else "Game Name:", font="-weight bold").pack(anchor="w", pady=(20, 5))
        
        entry_frame = tb.Frame(self.content_frame)
        entry_frame.pack(fill=X, padx=10)
        
        self.rename_var = tk.StringVar(value=self.game_name)
        tb.Entry(entry_frame, textvariable=self.rename_var).pack(side=LEFT, fill=X, expand=True)
        
        if not self.is_import:
            tb.Label(self.content_frame, text="Note: Renaming will update the game folder, info file, and screens folder.", bootstyle="secondary").pack(anchor="w", padx=10, pady=5)

    def _validate_rename(self):
        new_name = self.rename_var.get().strip()
        if not new_name:
            messagebox.showerror("Error", "Name cannot be empty.", parent=self)
            return False

        if self.is_import:
            # Import Logic: Move from !TEMP to games/<new_name>
            target_dir = os.path.join(self.logic.installed_dir, new_name)
            if os.path.exists(target_dir):
                messagebox.showerror("Error", f"Game '{new_name}' already exists in library.", parent=self)
                return False
            
            try:
                # Ensure parent dir exists
                os.makedirs(self.logic.installed_dir, exist_ok=True)
                
                # Move the folder
                shutil.move(self.source_path, target_dir)
                self.game_folder = target_dir
                self.game_name = new_name
                self.zip_name = f"{new_name}.zip"
                
                # Placeholder ZIP creation removed as per user request
                # We rely on the final Backup step to create the ZIP if desired.
                
                self.is_import = False # Now it's a normal game
                self.game_details = self.logic.get_game_details(self.game_name) # Reload (empty) details
                
                # Set installed date
                self.game_details['installed_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                self.logic.save_game_details(self.game_name, self.game_details)
                
                # Create install manifest for backup tracking
                self.logic.create_install_manifest(self.game_name)
                
                self.parent_app.refresh_library(renamed_zip=self.zip_name)
                return True
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to move game to library:\n{e}", parent=self)
                return False

        # Normal Rename Logic
        # Check for case-insensitive equality
        if new_name and new_name.lower() == self.game_name.lower() and new_name != self.game_name:
             # Case-only rename. Windows can be tricky with this.
             # We can rename to a temp name then to new name, or let logic handle it if it's smart.
             # Logic's rename_game checks if new_game_dir exists. On Windows "Exhumed" exists if "EXUHMED" exists.
             # So we need to bypass that check or handle it.
             # Let's try a temp rename strategy here if logic fails, or modify logic.
             # But modifying logic is safer. Let's assume logic needs update.
             # For now, let's try to call logic. If it fails with "exists", we try temp rename.
             pass

        if new_name and new_name != self.game_name:
            # Special handling for case-only rename on Windows
            if new_name.lower() == self.game_name.lower():
                temp_name = f"{self.game_name}_TEMP_{int(datetime.now().timestamp())}"
                _, err = self.logic.rename_game(self.game_name, temp_name)
                if err:
                    messagebox.showerror("Rename Error", f"Intermediate rename failed: {err}", parent=self)
                    return False
                self.game_name = temp_name # Update current state to temp
                # Now rename temp to new_name (which is just case change of original)
                renamed_name, error = self.logic.rename_game(self.game_name, new_name)
            else:
                renamed_name, error = self.logic.rename_game(self.game_name, new_name)
            
            if error:
                messagebox.showerror("Rename Error", error, parent=self)
                return False
            self.game_name = renamed_name
            self.zip_name = f"{renamed_name}.zip"
            self.game_folder = self.logic.find_game_folder(self.game_name)
            self.game_details = self.logic.get_game_details(self.game_name) # Reload details
            self.parent_app.refresh_library(renamed_zip=self.zip_name)
        return True

    # --- Step 2: Standardize Structure ---
    def step_standardize_structure(self):
        tb.Label(self.content_frame, text="This step will create standard folders (cd, docs, drives/c) and move ISO/CUE/BIN files.", wraplength=700).pack(anchor="w", pady=10)
        
        self.log_text = tb.Text(self.content_frame, height=15, width=80, state="disabled")
        self.log_text.pack(pady=10)
        
        btn = tb.Button(self.content_frame, text="Run Standardization", command=self._run_standardization_logic, bootstyle="warning")
        btn.pack(pady=10)
        
        # Auto-run if not already done in this session? Or let user click?
        # Let user click to see what happens.

    def _log(self, msg):
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.config(state="normal")
            self.log_text.insert(END, msg + "\n")
            self.log_text.see(END)
            self.log_text.config(state="disabled")
        else:
            print(f"[Standardize] {msg}")

    def _run_standardization_logic(self):
        self._log("Checking structure...")
        drives_dir = os.path.join(self.game_folder, "drives")
        c_dir = os.path.join(drives_dir, "c")
        cd_dir = os.path.join(self.game_folder, "cd")
        docs_dir = os.path.join(self.game_folder, "docs")
        
        try:
            os.makedirs(c_dir, exist_ok=True)
            os.makedirs(cd_dir, exist_ok=True)
            os.makedirs(docs_dir, exist_ok=True)
            self._log("Standard folders created/verified.")
        except Exception as e:
            self._log(f"Error creating folders: {e}")
            return # Stop if we can't create folders
        
        # Move CD images
        # Reuse logic from StandardizeWindow roughly
        moved_count = 0
        for root, dirs, files in os.walk(self.game_folder):
            if root.startswith(cd_dir): continue
            
            # Check for cue/bin pairs
            cue_files = [f for f in files if f.lower().endswith('.cue')]
            for cue in cue_files:
                base = os.path.splitext(cue)[0]
                bin_file = next((f for f in files if f.lower() == f"{base.lower()}.bin"), None)
                if bin_file:
                    try:
                        shutil.move(os.path.join(root, cue), os.path.join(cd_dir, cue))
                        shutil.move(os.path.join(root, bin_file), os.path.join(cd_dir, bin_file))
                        self._log(f"Moved {cue} and {bin_file}")
                        moved_count += 1
                    except Exception as e: self._log(f"Error moving {cue}: {e}")
            
            # Check for ISOs
            for f in files:
                if f.lower().endswith('.iso'):
                    try:
                        shutil.move(os.path.join(root, f), os.path.join(cd_dir, f))
                        self._log(f"Moved {f}")
                        moved_count += 1
                    except Exception as e: self._log(f"Error moving {f}: {e}")
                    
        if moved_count == 0: self._log("No CD images found to move.")
        else: self._log(f"Moved {moved_count} CD image sets.")

    # --- Step 3: MS-DOS Folder Name ---
    def step_dos_folder(self):
        tb.Label(self.content_frame, text="Enter an 8-character name for the game folder under drives/c:", font="-weight bold").pack(anchor="w", pady=10)
        
        # Check if we can find an existing DOS folder in the game folder
        c_dir = os.path.join(self.game_folder, "drives", "c")
        found_dos_folder = None
        suggested = ""
        
        if os.path.exists(c_dir):
            items = [d for d in os.listdir(c_dir) if os.path.isdir(os.path.join(c_dir, d))]
            if len(items) > 1:
                tb.Label(self.content_frame, text=f"Multiple folders found: {', '.join(items)}", bootstyle="warning").pack(anchor="w", padx=10, pady=(0, 5))
                tb.Label(self.content_frame, text="Please select one or enter a new name:", bootstyle="info").pack(anchor="w", padx=10)
                
                self.folder_choice = tk.StringVar(value=items[0])
                cb = tb.Combobox(self.content_frame, textvariable=self.folder_choice, values=items, state="readonly")
                cb.pack(anchor="w", padx=10, pady=5)
                
                def on_select(e):
                    self.dos_name_var.set(self.folder_choice.get())
                cb.bind("<<ComboboxSelected>>", on_select)
                
                suggested = items[0]
            elif items:
                found_dos_folder = items[0]
                tb.Label(self.content_frame, text=f"MSDOS folder FOUND: {found_dos_folder}", bootstyle="success").pack(anchor="w", padx=10, pady=(0, 5))
                suggested = found_dos_folder
        
        if not suggested:
            # Suggest name based on game name
            clean_name = re.sub(r'[\W_]+', '', self.game_name)
            suggested = clean_name[:8].upper()
        
        self.dos_name_var = tk.StringVar(value=suggested)
        
        # If we already have a combobox (multiple folders), we don't need another entry
        # But if we don't have multiple folders, we need an entry.
        # Actually, user wants just ONE box.
        # If multiple folders, we used a Combobox above. We should just use that one.
        # If no multiple folders, we use an Entry.
        
        if os.path.exists(c_dir) and len([d for d in os.listdir(c_dir) if os.path.isdir(os.path.join(c_dir, d))]) > 1:
             # We already created a Combobox above linked to self.folder_choice
             # We need to ensure self.dos_name_var is updated when combobox changes
             # The combobox above updates self.dos_name_var via on_select
             pass
        else:
             # Single folder or no folder found - show Entry
             tb.Entry(self.content_frame, textvariable=self.dos_name_var, width=20).pack(anchor="w", padx=10)
        
        tb.Label(self.content_frame, text="All game files (except cd/docs) will be moved to: drives/c/<NAME>", bootstyle="info").pack(anchor="w", padx=10, pady=10)

    def _validate_dos_folder(self):
        dos_name = self.dos_name_var.get().strip().upper()
        # Allow dots, check length (8.3 format roughly, but for directory just ensure it's not too long and valid chars)
        # User requested: "moze mat . a 3 dalsie pismena" -> 8.3
        if not dos_name or len(dos_name) > 12 or " " in dos_name:
            messagebox.showerror("Invalid Name", "Name must be valid DOS format (max 8.3), no spaces.", parent=self)
            return False
            
        c_dir = os.path.join(self.game_folder, "drives", "c")
        target_dir = os.path.join(c_dir, dos_name)
        
        if os.path.exists(target_dir):
            # If it exists, assume it's already done or user wants to use it
            pass
        else:
            # Move files
            os.makedirs(target_dir, exist_ok=True)
            # Move everything from game_folder except cd, docs, drives
            for item in os.listdir(self.game_folder):
                if item.lower() in ['cd', 'docs', 'drives']: continue
                src = os.path.join(self.game_folder, item)
                dst = os.path.join(target_dir, item)
                try:
                    if os.path.isdir(src):
                        shutil.move(src, dst)
                    else:
                        shutil.move(src, dst)
                except Exception as e:
                    print(f"Error moving {item}: {e}")
        
        # Update executables paths in game_details
        # We need to prepend "drives/c/<dos_name>/" to existing executable paths if they were relative to root
        # But only if they are not already in drives/c
        new_prefix = f"drives/c/{dos_name}/"
        new_executables = {}
        for exe, info in self.game_details.get("executables", {}).items():
            # Check if exe path is already deep
            # If it was "GAME.EXE", it is now "drives/c/DOSNAME/GAME.EXE"
            # If it was "drives/c/DOSNAME/GAME.EXE", it stays same.
            # If it was "sub/GAME.EXE", it is now "drives/c/DOSNAME/sub/GAME.EXE"
            
            # Normalize separators
            exe_norm = exe.replace("\\", "/")
            if exe_norm.lower().startswith("drives/c/"):
                # Already in drives/c, assume it's correct or user manually set it
                new_executables[exe] = info
            else:
                # It was relative to game root, now it's inside the DOS folder
                new_path = f"{new_prefix}{exe_norm}"
                new_executables[new_path] = info
        
        self.game_details["executables"] = new_executables
        self.logic.save_game_details(self.game_name, self.game_details)
        
        return True

    # --- Step 4: Metadata ---
    def step_metadata(self):
        # Reuse EditWindow logic partially? Or just simple fields?
        # User asked for "General" tab like table.
        
        grid = tb.Frame(self.content_frame)
        grid.pack(fill=X, padx=10, pady=10)
        grid.columnconfigure(1, weight=1)
        
        self.meta_vars = {}
        def add_row(row, label, key):
            tb.Label(grid, text=label).grid(row=row, column=0, sticky="w", pady=5)
            var = tk.StringVar(value=self.game_details.get(key, ""))
            tb.Entry(grid, textvariable=var).grid(row=row, column=1, sticky="ew", padx=10, pady=5)
            self.meta_vars[key] = var
            
        add_row(0, "Year:", "year")
        add_row(1, "Genre:", "genre")
        add_row(2, "Developer:", "developers")
        add_row(3, "Publisher:", "publishers")
        
        # Description
        tb.Label(grid, text="Description:").grid(row=4, column=0, sticky="nw", pady=5)
        self.desc_text = tb.Text(grid, height=4, width=40)
        self.desc_text.grid(row=4, column=1, sticky="ew", padx=10, pady=5)
        self.desc_text.insert("1.0", self.game_details.get("description", ""))
        
        # Rating
        tb.Label(grid, text="User Rating:").grid(row=5, column=0, sticky="w", pady=5)
        self.rating_var = tk.IntVar(value=self.game_details.get("rating", 0))
        rating_frame = tb.Frame(grid)
        rating_frame.grid(row=5, column=1, sticky="w", padx=10, pady=5)
        for i in range(1, 6):
            tb.Radiobutton(rating_frame, text=str(i), variable=self.rating_var, value=i).pack(side=LEFT, padx=2)
        
        btn_dl = tb.Button(self.content_frame, text="Fetch Metadata", command=self._download_metadata, bootstyle="primary-outline")
        btn_dl.pack(pady=10)
        
        # Save metadata on Next is handled by _next_step implicitly updating self.game_details?
        # No, we need to save it.

    def _download_metadata(self):
        # Simplified version of EditWindow._download_metadata
        results = self.logic.db.search(self.game_name.replace("_", " "))
        if not results:
            messagebox.showinfo("No Results", "No games found.", parent=self)
            return
            
        selected = None
        if len(results) == 1:
            if messagebox.askyesno("Found", f"Found: {results[0]['name']}\nApply?"): selected = results[0]
        else:
            # We need to adapt results for GameSelectionDialog
            adapted = []
            for r in results:
                ts = 0
                try:
                    if r['year']: ts = datetime(int(r['year']), 1, 1).timestamp()
                except: pass
                adapted.append({'name': r['name'], 'first_release_date': ts, 'platforms': [{'name': 'DOS'}], '_original': r})
            
            dlg = GameSelectionDialog(self, adapted, game_name=self.game_name)
            self.wait_window(dlg)
            if dlg.result: selected = dlg.result['_original']
            
        if selected:
            self.meta_vars['year'].set(selected.get('year', ''))
            self.meta_vars['genre'].set(selected.get('genre', ''))
            self.meta_vars['developers'].set(selected.get('developer', ''))
            self.meta_vars['publishers'].set(selected.get('publisher', ''))
            self.desc_text.delete("1.0", END)
            self.desc_text.insert("1.0", selected.get('description', ''))
            try: self.rating_var.set(int(selected.get('rating', 0)))
            except: pass
            
            # Also update game details dict
            self.game_details.update({
                'year': selected.get('year', ''),
                'genre': selected.get('genre', ''),
                'developers': selected.get('developer', ''),
                'publishers': selected.get('publisher', ''),
                'description': selected.get('description', ''),
                'rating': int(selected.get('rating', 0)),
                'num_players': selected.get('players', '')
            })
            self.logic.save_game_details(self.game_name, self.game_details)

    def _save_metadata(self):
        # Helper to save manual edits before moving next
        if hasattr(self, 'meta_vars'):
            self.game_details['year'] = self.meta_vars['year'].get()
            self.game_details['genre'] = self.meta_vars['genre'].get()
            self.game_details['developers'] = self.meta_vars['developers'].get()
            self.game_details['publishers'] = self.meta_vars['publishers'].get()
            self.game_details['description'] = self.desc_text.get("1.0", END).strip()
            self.game_details['rating'] = self.rating_var.get()
            self.logic.save_game_details(self.game_name, self.game_details)

    # --- Step 4: Structure & Drives ---
    def step_mount_drives(self):
        self.header_lbl.config(text="4. Automatic mounted drives")
        
        tb.Label(self.content_frame, text="The wizard has detected the following drive structure:", font="-size 12").pack(anchor="w", pady=10)
        
        # Drive C
        dos_name = self.dos_name_var.get() if hasattr(self, 'dos_name_var') else "Unknown"
        c_path = f"drives/c/{dos_name}"
        
        f_c = tb.Frame(self.content_frame, bootstyle="secondary", padding=10)
        f_c.pack(fill=X, pady=5)
        tb.Label(f_c, text="Drive C (Hard Disk):", font="-weight bold").pack(side=LEFT)
        tb.Label(f_c, text=c_path).pack(side=RIGHT)
        
        # Drive D
        cd_dir = os.path.join(self.game_folder, "cd")
        isos = [f for f in os.listdir(cd_dir) if f.lower().endswith(('.iso', '.cue'))] if os.path.exists(cd_dir) else []
        
        f_d = tb.Frame(self.content_frame, bootstyle="secondary", padding=10)
        f_d.pack(fill=X, pady=5)
        tb.Label(f_d, text="Drive D (CD-ROM):", font="-weight bold").pack(side=LEFT)
        
        if isos:
            tb.Label(f_d, text=f"cd/{isos[0]}").pack(side=RIGHT)
            if len(isos) > 1:
                tb.Label(self.content_frame, text=f"(+ {len(isos)-1} other images found)", font="-size 8").pack(anchor="e")
        else:
            tb.Label(f_d, text="None").pack(side=RIGHT)

    # --- Step 5: Executables ---
    def step_executables(self):
        self.header_lbl.config(text="5. Configure Executables")

        # Preserve existing selections if refreshing
        preserved_roles = {}
        preserved_titles = {}
        preserved_params = {}
        
        if hasattr(self, 'exe_vars') and self.exe_vars:
            for exe, role_var, param_var, title_var in self.exe_vars:
                preserved_roles[exe] = role_var.get()
                preserved_titles[exe] = title_var.get()
                preserved_params[exe] = param_var.get()
        
        top_bar = tb.Frame(self.content_frame)
        top_bar.pack(fill=X, pady=(0, 10))
        tb.Label(top_bar, text="Assign Roles to Executables:", font="-weight bold").pack(side=LEFT)
        tb.Button(top_bar, text="Refresh List", command=lambda: self._show_step(self.current_step), bootstyle="info-outline", padding=2).pack(side=RIGHT)
        
        found_exes = self.logic.get_all_executables(self.game_name)
        if not found_exes:
            tb.Label(self.content_frame, text="No executables found! Game might not be installed.", bootstyle="danger").pack(pady=10)
            
            btn_frame = tb.Frame(self.content_frame)
            btn_frame.pack()
            tb.Button(btn_frame, text="Launch DOSBox Prompt (Install Game)", command=self._launch_dos_prompt, bootstyle="success").pack(side=LEFT, padx=5)
            tb.Button(btn_frame, text="Refresh", command=lambda: self._show_step(self.current_step), bootstyle="info").pack(side=LEFT, padx=5)
            return

        # Simple role assigner
        self.exe_vars = []
        
        # Header for columns
        header_frame = tb.Frame(self.content_frame)
        header_frame.pack(fill=X, pady=(0, 5))
        header_frame.columnconfigure(0, weight=3) # Executable
        header_frame.columnconfigure(1, weight=2) # Parameters
        header_frame.columnconfigure(2, weight=2) # Role
        header_frame.columnconfigure(3, weight=3) # Title/Desc
        header_frame.columnconfigure(4, weight=1) # Test Button
        
        tb.Label(header_frame, text="Executable", font="-weight bold").grid(row=0, column=0, sticky="w", padx=5)
        tb.Label(header_frame, text="Parameters", font="-weight bold").grid(row=0, column=1, sticky="w", padx=5)
        tb.Label(header_frame, text="Role", font="-weight bold").grid(row=0, column=2, sticky="w", padx=5)
        tb.Label(header_frame, text="Title/Desc", font="-weight bold").grid(row=0, column=3, sticky="w", padx=5)

        # Scrollable area
        canvas = tk.Canvas(self.content_frame, bd=0, highlightthickness=0)
        scrollbar = tb.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scroll_frame = tb.Frame(canvas)
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=canvas.winfo_reqwidth()) # Try to match width
        # Better: bind canvas configure to update window width
        def on_canvas_configure(event): canvas.itemconfig(canvas_window, width=event.width)
        canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.bind("<Configure>", on_canvas_configure)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        scroll_frame.columnconfigure(0, weight=3)
        scroll_frame.columnconfigure(1, weight=2)
        scroll_frame.columnconfigure(2, weight=2)
        scroll_frame.columnconfigure(3, weight=3)
        scroll_frame.columnconfigure(4, weight=1)

        current_map = self.game_details.get("executables", {})
        
        for i, exe in enumerate(found_exes):
            info = current_map.get(exe, {})
            
            # Restore preserved values if available, else use info from details, else empty
            default_params = preserved_params.get(exe, info.get("params", ""))
            default_role_display = preserved_roles.get(exe, constants.ROLE_DISPLAY.get(info.get("role", constants.ROLE_UNASSIGNED), "Unassigned"))
            default_title = preserved_titles.get(exe, info.get("title", ""))
            
            # Executable Name
            tb.Label(scroll_frame, text=exe, anchor="w").grid(row=i, column=0, sticky="ew", padx=5, pady=2)
            
            # Parameters
            param_var = tk.StringVar(value=default_params)
            tb.Entry(scroll_frame, textvariable=param_var).grid(row=i, column=1, sticky="ew", padx=5, pady=2)

            # Role
            role_var = tk.StringVar(value=default_role_display)
            cb = tb.Combobox(scroll_frame, textvariable=role_var, values=sorted(list(constants.ROLE_DISPLAY.values())), state="readonly")
            cb.grid(row=i, column=2, sticky="ew", padx=5, pady=2)
            
            # Title/Desc
            title_var = tk.StringVar(value=default_title)
            title_entry = tb.Entry(scroll_frame, textvariable=title_var)
            title_entry.grid(row=i, column=3, sticky="ew", padx=5, pady=2)
            
            # Enable/Disable Title based on Role
            def on_role_change(event, entry=title_entry, var=role_var, current_exe=exe):
                # Get the display value from the combobox
                display_val = var.get()
                # Check if it maps to ROLE_CUSTOM
                if display_val == constants.ROLE_DISPLAY.get(constants.ROLE_CUSTOM):
                    entry.config(state="normal")
                else:
                    entry.config(state="disabled")
                    
                # Exclusivity logic for Main Game, Setup/Config, and Game Installer
                target_roles = [constants.ROLE_DISPLAY[constants.ROLE_MAIN], constants.ROLE_DISPLAY[constants.ROLE_SETUP], constants.ROLE_DISPLAY[constants.ROLE_INSTALL]]
                
                if display_val in target_roles:
                    for other_exe, other_role_var, _, _ in self.exe_vars:
                        if other_exe != current_exe and other_role_var.get() == display_val:
                            other_role_var.set(constants.ROLE_DISPLAY[constants.ROLE_UNASSIGNED])
            
            cb.bind("<<ComboboxSelected>>", on_role_change)
            # Initial state
            on_role_change(None)
            
            # Test Button
            tb.Button(scroll_frame, text="Test", command=lambda x=exe: self._test_executable(x), bootstyle="info-outline").grid(row=i, column=4, padx=5, pady=2)
            
            self.exe_vars.append((exe, role_var, param_var, title_var))

    def _test_executable(self, exe):
        # Minimize wizard to ensure DOSBox is visible
        # self.iconify()
        try:
            # Ensure wizard is not topmost during test
            self.attributes("-topmost", False)
            self.logic.launch_game(self.zip_name, specific_exe=exe)
        except Exception as e:
            # self.deiconify()
            messagebox.showerror("Error", str(e), parent=self)
        finally:
            # Restore topmost if it was set (ConfigWizard is usually transient, not topmost, but just in case)
            # Actually, transient windows are always on top of parent.
            # If we want DOSBox on top, we rely on launch_game's window management.
            pass
            messagebox.showerror("Launch Error", str(e), parent=self)

    def _launch_dos_prompt(self):
        self.logic.launch_game(self.zip_name, dos_prompt_only=True)

    def _save_executables(self):
        if not hasattr(self, 'exe_vars'): return
        new_map = {}
        for exe, var, param_var, title_var in self.exe_vars:
            role_display = var.get()
            role_id = constants.ROLE_KEYS.get(role_display, constants.ROLE_UNASSIGNED)
            new_map[exe] = {
                "role": role_id, 
                "title": title_var.get().strip(), 
                "params": param_var.get().strip()
            }
        
        self.game_details["executables"] = new_map
        self.logic.save_game_details(self.game_name, self.game_details)



    # --- Step 7: Backup ---
    def step_backup(self):
        tb.Label(self.content_frame, text="Wizard Complete!", font="-size 14 -weight bold", bootstyle="success").pack(pady=20)
        
        # Summary
        summary_frame = tb.Labelframe(self.content_frame, text="Configuration Summary", padding=10)
        summary_frame.pack(fill=X, pady=10)
        
        self.run_config_var = tk.BooleanVar(value=not self.disable_config_option)
        cb_config = tb.Checkbutton(self.content_frame, text="Run configuration of game", variable=self.run_config_var)
        cb_config.pack(pady=5, anchor="w")
        
        if self.disable_config_option:
            cb_config.config(state="disabled")
            tb.Label(self.content_frame, text="(Configuration disabled during bulk import)", bootstyle="warning", font="-size 8").pack(anchor="w", padx=20)
        
        # DOS Folder
        dos_name = self.dos_name_var.get() if hasattr(self, 'dos_name_var') else "Unknown"
        tb.Label(summary_frame, text=f"DOS Folder: drives/c/{dos_name}").pack(anchor="w")
        
        # Executables
        exes = self.game_details.get("executables", {})
        main_exe = next((k for k, v in exes.items() if v.get("role") == constants.ROLE_MAIN), "None")
        tb.Label(summary_frame, text=f"Main Executable: {main_exe}").pack(anchor="w")
        
        # Mounts
        isos = self.logic.get_mounted_isos(self.game_name)
        mounts = "C: (Local)"
        if isos: mounts += ", D: (CD-ROM)"
        tb.Label(summary_frame, text=f"Mounts: {mounts}").pack(anchor="w")

        # Options
        self.backup_var = tk.BooleanVar(value=False)
        tb.Checkbutton(self.content_frame, text="Archive game", variable=self.backup_var).pack(pady=5, anchor="w")
        
        # Re-use existing run_config_var if possible, or ensure it's set
        if not hasattr(self, 'run_config_var'):
            self.run_config_var = tk.BooleanVar(value=not self.disable_config_option)
            cb = tb.Checkbutton(self.content_frame, text="Run configuration of game", variable=self.run_config_var)
            cb.pack(pady=5, anchor="w")
            if self.disable_config_option: cb.config(state="disabled")
        
        tb.Label(self.content_frame, text="Click Finish to apply final changes and close.", bootstyle="secondary").pack(pady=10)

    def _perform_backup(self):
        if self.backup_var.get():
            # Zip the entire game folder to zipped_dir
            try:
                # Show busy window
                from ..gui import BusyWindow
                busy = BusyWindow(self, message=f"Archiving {self.game_name}...\nPlease wait.")
                self.update()
                
                # Determine extension based on availability
                ext = ".7z" if self.logic.HAS_7ZIP else ".zip"
                archive_path = os.path.join(self.logic.zipped_dir, f"{self.game_name}{ext}")
                
                # Use logic helper which should handle 7z if available
                self.logic.make_zip_archive(self.game_name, archive_path)
                
                busy.destroy()
            except Exception as e:
                if 'busy' in locals() and busy.winfo_exists(): busy.destroy()
                messagebox.showerror("Archive Error", f"Failed to create archive:\n{e}", parent=self)
        
        # Final refresh
        self.parent_app.refresh_library()
        
        # Set result for parent to know we finished successfully
        self.parent_app.last_imported_game = self.game_name
        self.parent_app.newly_imported.add(self.game_name)
        
        # Run configuration if requested
        if self.run_config_var.get():
            # We need to signal the parent to open the edit window
            # We can do this by setting a flag or calling a method on parent
            # But parent waits for this window to close.
            # So we can just set a flag on parent.
            self.parent_app.should_open_config = True
        else:
            self.parent_app.should_open_config = False
