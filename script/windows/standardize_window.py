import tkinter as tk
from tkinter import simpledialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import os
import shutil
import re

class StandardizeWindow(tb.Toplevel):
    def __init__(self, parent, logic, game_name):
        super().__init__(parent)
        self.parent = parent
        self.logic = logic
        self.game_name = game_name
        self.game_folder = self.logic.find_game_folder(self.game_name)
        self.steps = []
        self.title(f"Standardizing: {self.game_name}")
        self.geometry("600x400")
        self.transient(parent)
        self.grab_set()

        main_frame = tb.Frame(self, padding=15)
        main_frame.pack(fill=BOTH, expand=YES)
        
        self.results_text = tk.Text(main_frame, wrap=WORD, font=("Consolas", 10))
        self.results_text.pack(fill=BOTH, expand=YES, pady=(0, 10))
        self.results_text.tag_config("ok", foreground=self.style.colors.success)
        self.results_text.tag_config("warn", foreground=self.style.colors.warning)
        self.results_text.tag_config("info", foreground=self.style.colors.info)
        self.results_text.tag_config("error", foreground=self.style.colors.danger)

        self.start_button = tb.Button(main_frame, text="Start Standardization", command=self.run_standardization, bootstyle="success")
        self.start_button.pack(side=LEFT, padx=(0, 10))
        self.close_button = tb.Button(main_frame, text="Close", command=self.destroy, bootstyle="secondary")
        self.close_button.pack(side=RIGHT)
        
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after(250, self.run_standardization) # Auto-start

    def log(self, message, tag="info"):
        self.results_text.insert(END, message + "\n", (tag,))
        self.results_text.see(END)
        self.update_idletasks()

    def run_standardization(self):
        self.start_button.config(state=DISABLED)
        try:
            # 1. Check existing structure
            self.log("Step 1: Checking current folder structure...")
            drives_dir = os.path.join(self.game_folder, "drives")
            c_dir = os.path.join(drives_dir, "c")
            cd_dir = os.path.join(self.game_folder, "cd")
            docs_dir = os.path.join(self.game_folder, "docs")

            if all(os.path.isdir(p) for p in [c_dir, cd_dir, docs_dir]):
                self.log("✅ All standard folders (drives/c, cd, docs) already exist.", "ok")
                self.log("Game appears to be already standardized. No action taken.", "warn")
                return

            self.log("-> Structure is not standard. Proceeding...")
            os.makedirs(c_dir, exist_ok=True); self.log("➕ Created folder: drives/c")
            os.makedirs(cd_dir, exist_ok=True); self.log("➕ Created folder: cd")
            os.makedirs(docs_dir, exist_ok=True); self.log("➕ Created folder: docs")
            self.log("✅ Standard folders are ready.", "ok")

            # 2. Find and move CD images (RECURSIVELY)
            self.log("\nStep 2: Searching for CD images (.iso, .cue/.bin) recursively...")
            moved_images = self._move_cd_images(self.game_folder, cd_dir)
            if moved_images:
                self.log(f"💿 Moved {len(moved_images)} CD image(s) to 'cd' folder:", "ok")
                for img in moved_images: self.log(f"  - {img}")
            else:
                self.log("-> No valid CD images found to move.", "info")

            # 3. Find game data and move it
            self.log("\nStep 3: Locating and moving game data...")
            game_data_root = self._find_game_data_root(self.game_folder, exclude=[cd_dir, docs_dir, drives_dir])
            
            if not game_data_root:
                 self.log("❌ Could not determine main game data directory.", "error")
                 return
                 
            self.log(f"-> Found potential game data at: {os.path.relpath(game_data_root, self.game_folder)}")

            # Determine 8-char name
            parent_dir = os.path.dirname(game_data_root)
            dos_name = ""
            if parent_dir != self.game_folder:
                 folder_name = os.path.basename(game_data_root)
                 if len(folder_name) <= 8 and " " not in folder_name:
                     dos_name = folder_name.upper()
                     self.log(f"-> Using existing folder name '{dos_name}' as DOS name.", "info")

            if not dos_name:
                self.log("-> Game data seems to be at the root. Asking for a DOS folder name.", "warn")
                dos_name = simpledialog.askstring("DOS Folder Name", "Enter an 8-character name for the game folder (no spaces):", parent=self, initialvalue=re.sub(r'[\W_]+', '', self.game_name)[:8].upper())
                if not dos_name:
                    self.log("❌ Standardization cancelled by user.", "error"); return

            target_dos_dir = os.path.join(c_dir, dos_name)
            os.makedirs(target_dos_dir, exist_ok=True)
            self.log(f"-> Moving files to: drives/c/{dos_name}", "info")
            
            # Ensure we don't try to move directories we've created
            items_to_move = [item for item in os.listdir(game_data_root) if os.path.normpath(os.path.join(game_data_root, item)) not in [os.path.normpath(p) for p in [cd_dir, docs_dir, drives_dir]]]

            for item in items_to_move:
                shutil.move(os.path.join(game_data_root, item), target_dos_dir)
            self.log("-> Game data moved.", "ok")

            # Cleanup empty source dirs
            if game_data_root != self.game_folder and not os.listdir(game_data_root):
                try: os.rmdir(game_data_root)
                except OSError: pass # May not be empty due to other empty subdirs

            # Final check
            self.log("\nStep 4: Final verification...")
            if os.path.isdir(target_dos_dir) and len(os.listdir(target_dos_dir)) > 0:
                 self.log("✅ Game data is inside drives/c/<dos_folder>.", "ok")
            else:
                 self.log("❌ Verification failed. Game data not in place.", "error")
            
            self.log("\n🎉 Standardization complete! Please check the new structure.", "ok")
            self.parent.refresh_library()

        except Exception as e:
            self.log(f"\nAn error occurred: {e}", "error")

    def _move_cd_images(self, source_root, cd_target_dir):
        moved_files = []
        for root, dirs, files in os.walk(source_root, topdown=False):
            # Don't search in the target directory itself
            if os.path.normpath(root) == os.path.normpath(cd_target_dir):
                continue

            cue_files_in_dir = {os.path.splitext(f.lower())[0] for f in files if f.lower().endswith('.cue')}

            for item in files:
                item_path = os.path.join(root, item)
                lower_item = item.lower()

                try:
                    if lower_item.endswith('.iso'):
                        shutil.move(item_path, cd_target_dir)
                        moved_files.append(item)
                    elif lower_item.endswith('.bin'):
                        if os.path.splitext(lower_item)[0] in cue_files_in_dir:
                            cue_file_name = os.path.splitext(item)[0] + ".cue"
                            cue_path = os.path.join(root, cue_file_name)
                            if os.path.exists(cue_path): # Find original case-sensitive name
                                shutil.move(item_path, cd_target_dir)
                                shutil.move(cue_path, cd_target_dir)
                                moved_files.append(f"{item} + {cue_file_name}")
                except Exception as e:
                    self.log(f"Error moving {item}: {e}", "error")
        return moved_files
    
    def _find_game_data_root(self, path, exclude):
        best_candidate = None
        for root, _, files in os.walk(path):
            norm_root = os.path.normpath(root)
            if any(norm_root.startswith(os.path.normpath(p)) for p in exclude): continue
            
            if any(f.lower().endswith(('.exe', '.com', '.bat')) for f in files):
                # We want the highest-level directory that contains executables
                if best_candidate is None or len(root) < len(best_candidate):
                    best_candidate = root
        return best_candidate if best_candidate is not None else path
