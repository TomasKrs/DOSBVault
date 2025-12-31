import tkinter as tk
from tkinter import messagebox, font, simpledialog, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText
import os
import sys
import shutil
import re
import webbrowser
from urllib.parse import quote_plus
import zipfile
import threading
import queue
import subprocess
from datetime import datetime

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

try:
    from PIL import Image, ImageTk
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

from .logic import GameLogic
from .settings import SettingsManager
from .windows.settings_window import SettingsWindow
from .windows.edit_window import EditWindow, GameSelectionDialog
from .windows.standardize_window import StandardizeWindow
from .windows.config_wizard import ConfigWizard
from .windows.start_wizard import StartWizard
from .windows.batch_wizard import BatchUtilsWizard
from .components.detail_panel import DetailPanel
from .components.library_panel import LibraryPanel
from .components.gamepad_handler import GamepadHandler
from .utils import format_size, truncate_text, get_folder_size, get_file_size, restart_program
from . import constants
from .logger import Logger

class BusyWindow(tk.Toplevel):
    def __init__(self, parent, message="Working, please wait..."):
        super().__init__(parent)
        self.transient(parent); self.title("Working..."); self.resizable(False, False); self.grab_set()
        self.label = tb.Label(self, text=message, padding=20)
        self.label.pack()
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"+{x}+{y}")
    
    def update_message(self, msg):
        self.label.config(text=msg)
        self.update()

class DOSManagerApp(TkinterDnD.Tk if HAS_DND else tb.Window):
    DETAIL_PANEL_WIDTH = 550; LIBRARY_PANEL_DEFAULT_WIDTH = 880; WINDOW_PADDING_X = 20
    FULL_HEIGHT = 880; COMPACT_HEIGHT = 720 
    LIST_OFF_WIDTH = DETAIL_PANEL_WIDTH + WINDOW_PADDING_X

    def __init__(self):
        if HAS_DND:
            super().__init__()
            self.style = tb.Style(theme="darkly")
        else:
            super().__init__(themename="darkly")

        self.settings = SettingsManager(); theme = self.settings.get("theme") or "darkly"
        
        # Load external themes
        themes_dir = os.path.join(os.getcwd(), "themes")
        if os.path.exists(themes_dir):
            for f in os.listdir(themes_dir):
                if f.endswith(".json"):
                    try:
                        self.style.load_user_themes(os.path.join(themes_dir, f))
                    except Exception as e:
                        # Ignore specific error for standard themes that might be conflicting or malformed
                        if "string indices must be integers" not in str(e):
                            print(f"Failed to load theme {f}: {e}")
        
        # If the theme is one of the standard ones but failed to load from file (or wasn't in file),
        # ttkbootstrap might still have it built-in.
        try:
            self.style.theme_use(theme)
        except:
            # Fallback
            print(f"Theme {theme} not found, falling back to darkly")
            self.style.theme_use("darkly")

        self.logger = Logger(self.settings)
        
        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.on_drop)

        self.title(f"DOSBVault v{constants.VERSION}"); self.logic = GameLogic(self.settings)
        # Ensure window is not topmost by default
        self.attributes('-topmost', 0)
        
        self.win_edit, self.win_settings, self.win_standardize = None, None, None
        self.playlist_visible, self.description_visible = False, True
        self.last_library_width = self.settings.get("last_library_width", self.LIBRARY_PANEL_DEFAULT_WIDTH)
        self.current_images, self.current_img_index = [], 0
        self.search_var = tk.StringVar(); self.fav_only_var = tk.BooleanVar(value=False)
        self.search_var.trace("w", lambda *args: self.refresh_library()); self.sort_col, self.sort_desc = "name", False
        self.force_fullscreen_var = tk.BooleanVar(value=self.settings.get("force_fullscreen", False))
        self.auto_exit_var = tk.BooleanVar(value=self.settings.get("auto_exit", False))
        self.vlc_path = self.logic.find_vlc()
        self.first_load_complete = False 
        self.newly_imported = set()

        # --- Gamepad Support ---
        self.gamepad_handler = GamepadHandler(self)
        self.gamepad_handler.start()

        # --- Dynamic Initial Sizing ---
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        initial_height = int(screen_height * 0.85)
        self.FULL_HEIGHT = initial_height
        initial_width = int(screen_width * 0.6)
        min_width = self.DETAIL_PANEL_WIDTH + self.WINDOW_PADDING_X + 300
        initial_width = max(initial_width, min_width)
        self.last_library_width = initial_width - self.DETAIL_PANEL_WIDTH
        
        self.init_ui()
        if not self.playlist_visible:
            initial_width = self.LIST_OFF_WIDTH
            min_width = self.LIST_OFF_WIDTH
            self.resizable(False, True)
        
        self.geometry(f"{initial_width}x{initial_height}"); self.minsize(min_width, 500)
        self.after(100, self.post_init_load)
        self.bind("<Configure>", self._on_resize)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Force normal stacking order
        self.lift()
        self.attributes('-topmost', False)

    def _on_close(self):
        if hasattr(self, 'gamepad_handler'):
            self.gamepad_handler.stop()
        if self.playlist_visible and hasattr(self, 'library_panel') and self.library_panel.winfo_exists():
            self.settings.set("last_library_width", self.library_panel.winfo_width())
        self.destroy()

    def _on_resize(self, event):
        if self.playlist_visible and hasattr(self, 'library_panel') and self.library_panel.winfo_exists() and self.library_panel.winfo_width() > 1:
            self.last_library_width = self.library_panel.winfo_width()

    def on_drop(self, event):
        if event.data:
            # TkinterDnD returns a string of paths, sometimes wrapped in {} if they contain spaces
            # We need to parse it.
            raw_data = event.data
            # Simple parsing for Windows paths
            if raw_data.startswith('{') and raw_data.endswith('}'):
                paths = re.findall(r'\{(.+?)\}', raw_data)
            else:
                paths = raw_data.split() # This might break on spaces if not wrapped, but TkinterDnD usually wraps
            
            # Fallback if regex didn't match but it was just one path without braces
            if not paths and os.path.exists(raw_data):
                paths = [raw_data]
                
            self.process_dropped_files(paths)

    def add_game_zip(self):
        files = filedialog.askopenfilenames(title="Select Game Archive(s)", filetypes=[("Archives", "*.zip *.7z"), ("ZIP files", "*.zip"), ("7z files", "*.7z"), ("All files", "*.*")])
        if files:
            self.process_dropped_files(files)

    def backup_save_data(self):
        selected = self.tree.selection()
        if not selected: return
        zip_name = selected[0]
        game_name = os.path.splitext(zip_name)[0]
        
        # Use logic to create differential backup
        success, msg = self.logic.create_differential_backup(game_name)
        
        if success:
            messagebox.showinfo("Backup", msg, parent=self)
        else:
            if "Original archive not found" in msg:
                if messagebox.askyesno("Original Not Found", f"{msg}\n\nDo you want to create a full archive of the game now?", parent=self):
                    # Create full archive
                    try:
                        archive_path = os.path.join(self.logic.zipped_dir, f"{game_name}.zip")
                        self.logic.make_zip_archive(game_name, archive_path)
                        messagebox.showinfo("Success", f"Full archive created:\n{archive_path}", parent=self)
                        self.refresh_library()
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to create archive: {e}", parent=self)
            else:
                messagebox.showerror("Error", msg, parent=self)

    def open_batch_wizard(self):
        BatchUtilsWizard(self, self.logic)

    def batch_metatag(self, game_zips=None):
        # Modified to accept list of games
        if game_zips is None:
            # Legacy call or direct call without wizard?
            # Redirect to wizard if called without args
            self.open_batch_wizard()
            return
        
        # Progress Window with Log
        progress_win = tb.Toplevel(self)
        progress_win.title("Batch Metatagging Progress")
        progress_win.geometry("600x400")
        progress_win.transient(self)
        # progress_win.grab_set() # Don't grab set so user can interact if needed, or maybe we should?
        
        lbl_status = tb.Label(progress_win, text="Starting...", bootstyle="info")
        lbl_status.pack(pady=5)
        
        progress_bar = tb.Progressbar(progress_win, maximum=len(game_zips), mode='determinate')
        progress_bar.pack(fill=X, padx=10, pady=5)
        
        log_text = ScrolledText(progress_win, height=15, autohide=True)
        log_text.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        def log(msg):
            log_text.text.insert(END, msg + "\n")
            log_text.text.see(END)
            progress_win.update()

        count = 0
        renamed_count = 0
        
        for i, zip_name in enumerate(game_zips):
            game_name = os.path.splitext(zip_name)[0]
            lbl_status.config(text=f"Processing: {game_name}")
            progress_bar['value'] = i + 1
            progress_win.update()
            
            # Skip if already has metadata (e.g. year is set)
            details = self.logic.get_game_details(game_name)
            if details.get("year"): 
                log(f"[SKIP] {game_name}: Already has metadata.")
                continue
            
            # Search for metadata
            results = self.logic.db.search(game_name)
            if not results:
                log(f"[FAIL] {game_name}: No match found.")
                continue
                
            # Take the best match (first one) or ask user
            match = None
            if len(results) == 1:
                match = results[0]
            else:
                # Multiple results - ask user
                adapted_results = []
                for r in results:
                    ts = 0
                    try:
                        if r['year']: ts = datetime(int(r['year']), 1, 1).timestamp()
                    except: pass
                    adapted_results.append({'name': r['name'], 'first_release_date': ts, 'platforms': [{'name': 'DOS'}], '_original': r})
                
                dialog = GameSelectionDialog(progress_win, adapted_results, game_name=game_name)
                progress_win.wait_window(dialog)
                if dialog.result:
                    match = dialog.result['_original']
                else:
                    log(f"[SKIP] {game_name}: User cancelled selection.")
                    continue

            match_name = match['name']
            match_year = match.get('year', 'Unknown')
            
            log(f"[MATCH] {game_name} -> {match_name} ({match_year})")
            
            # Ask for confirmation/Rename BEFORE applying
            safe_new_name = "".join([c for c in match_name if c.isalpha() or c.isdigit() or c in " ._-"]).strip()
            should_rename = False
            if safe_new_name and safe_new_name != game_name:
                answer = messagebox.askyesnocancel("Confirm Match & Rename", f"Match found:\n'{match_name}' ({match_year})\n\nCurrent: '{game_name}'\n\nYes: Apply metadata AND Rename to '{safe_new_name}'\nNo: Apply metadata ONLY (Keep '{game_name}')\nCancel: Skip this game", parent=progress_win)
                if answer is None: # Cancel
                    log(f"[SKIP] {game_name}: Skipped by user.")
                    continue
                elif answer is True: # Yes
                    should_rename = True
                else: # No
                    should_rename = False
            else:
                # Names are same, just confirm metadata? Or auto-apply?
                pass

            # Apply metadata (Merge logic)
            def merge_meta(key, new_val):
                if not new_val: return # Don't overwrite with empty
                old_val = details.get(key, "")
                if not old_val or str(old_val).strip() == "" or str(old_val) == "0":
                    details[key] = new_val
                elif str(old_val) != str(new_val):
                    # If different, prefer new value from DB? Or keep existing?
                    # User said: "moze sa totizto stat, ze mame vyplneny len rok pri hre a ty to povazujes za hotovu vec.. ale ostatne informacie sa mozu nachadzat v databaze.. bolo by dobre to tam dopisat.."
                    # This implies filling missing. But what if both exist and differ?
                    # Usually DB is more accurate than random user input, but user input might be custom.
                    # Let's overwrite if the new value seems "better" (longer description?) or just overwrite.
                    # For batch, overwriting is usually expected if you asked for it.
                    details[key] = new_val

            merge_meta('year', match.get('year', ''))
            merge_meta('publishers', match.get('publisher', ''))
            merge_meta('developers', match.get('developer', ''))
            merge_meta('genre', match.get('genre', ''))
            merge_meta('rating', int(match.get('rating', 0)))
            merge_meta('num_players', match.get('players', ''))
            merge_meta('description', match.get('description', ''))
            
            # Always update title if we matched
            details['title'] = match_name
            
            # Rename if requested
            final_name = game_name
            if should_rename:
                log(f"       Renaming to: {safe_new_name}...")
                new_name, error = self.logic.rename_game(game_name, safe_new_name)
                if error:
                    log(f"       [ERROR] Rename failed: {error}")
                else:
                    log(f"       [OK] Renamed successfully.")
                    renamed_count += 1
                    final_name = new_name
            
            self.logic.save_game_details(final_name, details)
            count += 1
        
        lbl_status.config(text="Complete!")
        tb.Button(progress_win, text="Close", command=progress_win.destroy, bootstyle="success").pack(pady=10)
        
        self.refresh_library()
        # messagebox.showinfo("Batch Complete", f"Updated {count} games.\nRenamed {renamed_count} games.", parent=self)

    def _import_single_file(self, file_path, silent=False):
        is_archive = file_path.lower().endswith(('.zip', '.7z'))
        if is_archive or os.path.isdir(file_path):
            try:
                # Show busy window only if not silent
                busy = None
                if not silent:
                    busy = BusyWindow(self, message=f"Preparing import for:\n{os.path.basename(file_path)}\n\nExtracting and analyzing...")
                    self.update()
                
                # Use a queue to get result from thread
                result_queue = queue.Queue()
                def run_prep():
                    try:
                        res = self.logic.prepare_import(file_path, is_archive)
                        result_queue.put(("success", res))
                    except Exception as e:
                        result_queue.put(("error", e))
                
                threading.Thread(target=run_prep, daemon=True).start()
                
                # Wait for result
                while result_queue.empty():
                    if not silent: self.update()
                    self.after(50)
                
                if busy: busy.destroy()
                
                status, data = result_queue.get()
                if status == "error":
                    raise data
                
                temp_path, suggested_name = data
                
                # Determine names
                original_basename = os.path.splitext(os.path.basename(file_path))[0]
                safe_name = "".join([c for c in original_basename if c.isalnum() or c in " ._-"]).strip()
                if not safe_name: safe_name = suggested_name
                
                # 1. Install (Move temp_path to games/safe_name)
                dest_path = self.logic.find_game_folder(safe_name)
                if os.path.exists(dest_path):
                    safe_name = f"{safe_name}_{int(time.time())}"
                    dest_path = self.logic.find_game_folder(safe_name)
                
                shutil.move(temp_path, dest_path)
                
                # 2. Archive step removed as per user request (Task 6)
                # We do NOT copy the source file to archive folder anymore.

                # 3. Import Settings
                self.logic.import_from_dosbox_conf(safe_name)
                
                self.last_imported_game = safe_name
                
                # Post-import configuration
                # We need to refresh library to ensure the new game is in the tree
                self.refresh_library()
                
                zip_name = f"{safe_name}.zip"
                if self.tree.exists(zip_name):
                    self.tree.selection_set(zip_name)
                    self.tree.see(zip_name)
                
                if not silent:
                    if messagebox.askyesno("Import Complete", f"Game '{safe_name}' imported successfully.\n\nRun Configuration Wizard now?", parent=self):
                        self.open_config_wizard(zip_name)

                return True, "Success"
                
            except Exception as e:
                if 'busy' in locals() and busy and busy.winfo_exists(): busy.destroy()
                if not silent:
                    messagebox.showerror("Import Error", f"Failed to prepare import for {file_path}:\n{e}", parent=self)
                return False, str(e)
        return False, "Invalid file type"

    def run_batch_config_wizard(self, game_names):
        if not game_names: return
        for game_name in game_names:
            zip_name = f"{game_name}.zip"
            self.open_config_wizard(zip_name, disable_config_option=True)
        
        messagebox.showinfo("Batch Config", "Batch configuration complete.\nIt is recommended to configure games individually if needed.", parent=self)

    def process_dropped_files(self, files):
        valid_files = [f for f in files if f.lower().endswith(('.zip', '.7z')) or os.path.isdir(f)]
        if not valid_files: return

        if len(valid_files) > 1:
            # Batch Import Dialog
            dlg = tb.Toplevel(self)
            dlg.title("Batch Import")
            dlg.geometry("600x500")
            dlg.transient(self)
            dlg.grab_set()
            
            tb.Label(dlg, text=f"Found {len(valid_files)} items to import.", font="-weight bold").pack(pady=10)
            tb.Label(dlg, text="Select items to import:").pack(anchor="w", padx=10)
            
            # Scrollable list with checkboxes
            frame = tb.Frame(dlg)
            frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
            
            canvas = tk.Canvas(frame)
            scrollbar = tb.Scrollbar(frame, orient="vertical", command=canvas.yview)
            scroll_frame = tb.Frame(canvas)
            
            scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            vars = []
            for f in valid_files:
                v = tk.BooleanVar(value=True)
                tb.Checkbutton(scroll_frame, text=os.path.basename(f), variable=v).pack(anchor="w", pady=2)
                vars.append((f, v))
            
            # Add option to run Config Wizard
            run_wizard_var = tk.BooleanVar(value=True)
            tb.Checkbutton(dlg, text="Run Config Wizard for imported games", variable=run_wizard_var, bootstyle="round-toggle").pack(pady=10)

            def run_batch():
                to_import = [f for f, v in vars if v.get()]
                run_wizard = run_wizard_var.get()
                dlg.destroy()
                
                # Progress Window
                progress_win = tb.Toplevel(self)
                progress_win.title("Batch Import Progress")
                progress_win.geometry("500x200")
                progress_win.transient(self)
                progress_win.grab_set()
                
                lbl_main = tb.Label(progress_win, text="Importing...", font="-weight bold")
                lbl_main.pack(pady=10)
                
                progress_bar = tb.Progressbar(progress_win, mode='determinate')
                progress_bar.pack(fill=X, padx=20, pady=10)
                
                lbl_status = tb.Label(progress_win, text="")
                lbl_status.pack(pady=5)
                
                results = {"success": [], "failed": [], "skipped": []}
                
                def batch_thread():
                    total = len(to_import)
                    for i, f in enumerate(to_import):
                        name = os.path.basename(f)
                        lbl_main.config(text=f"Importing {i+1}/{total}: {name}")
                        progress_bar['value'] = (i / total) * 100
                        progress_win.update()
                        
                        try:
                            # We need to modify _import_single_file to NOT show busy window if silent=True
                            # And maybe return the imported game name (zip name)
                            success, msg = self._import_single_file(f, silent=True)
                            
                            if success:
                                # msg is "Success" or similar.
                                # We need the game name (zip name) to run wizard.
                                # _import_single_file sets self.last_imported_game
                                results["success"].append(self.last_imported_game)
                            elif "Cancelled" in msg:
                                results["skipped"].append(name)
                            else:
                                results["failed"].append(f"{name} ({msg})")
                                
                        except Exception as e:
                            results["failed"].append(f"{name} ({e})")
                    
                    progress_win.destroy()
                    
                    # Show Report
                    report = []
                    if results["success"]:
                        report.append(f"Successfully Imported ({len(results['success'])}):")
                        report.extend([f" - {x}" for x in results["success"]])
                        report.append("")
                    
                    if results["failed"]:
                        report.append(f"Failed ({len(results['failed'])}):")
                        report.extend([f" - {x}" for x in results["failed"]])
                        report.append("")

                    if results["skipped"]:
                        report.append(f"Skipped ({len(results['skipped'])}):")
                        report.extend([f" - {x}" for x in results["skipped"]])
                    
                    if report:
                        messagebox.showinfo("Batch Import Report", "\n".join(report), parent=self)
                    
                    self.refresh_library()
                    
                    # Run Config Wizard if requested
                    if run_wizard and results["success"]:
                        if messagebox.askyesno("Config Wizard", f"Ready to configure {len(results['success'])} games.\nStart Config Wizard sequence?", parent=self):
                            self.run_batch_config_wizard(results["success"])

                threading.Thread(target=batch_thread, daemon=True).start()

            tb.Button(dlg, text="Import Selected", command=run_batch, bootstyle="success").pack(pady=10)
            self.wait_window(dlg)
            
        else:
            # Single file
            self._import_single_file(valid_files[0])
            self.refresh_library()

    def post_init_load(self, first_run_done=False):
        # Check for First Run Conditions
        # Trigger if settings.json is missing (fresh install)
        settings_path = os.path.join(os.getcwd(), 'settings.json')
        is_fresh_install = not os.path.exists(settings_path)
        
        # Also trigger if critical folders are missing AND we haven't just run the wizard
        essential_folders = ["DOSBox", "games", "archive", "export"]
        folders_missing = any(not os.path.exists(os.path.join(os.getcwd(), f)) for f in essential_folders)
        dosbox_missing = not self.logic.check_dosbox_exists()
        
        should_run_wizard = is_fresh_install or (folders_missing and not first_run_done) or (dosbox_missing and not first_run_done)
        
        if should_run_wizard:
            # Launch Start Wizard
            # self.withdraw() # Do not hide main window, as it causes issues with transient wizard
            wizard = StartWizard(self)
            wizard.wait_window()
            # self.deiconify() 
            
            # After wizard, refresh everything
            self.refresh_library()
            return

        if os.path.exists(self.logic.zipped_dir) or os.path.exists(self.logic.installed_dir): 
            self.refresh_library()
            # Select first game if none selected
            if not self.tree.selection() and self.tree.get_children():
                first = self.tree.get_children()[0]
                self.tree.selection_set(first)
                self.on_select(None)
        else: messagebox.showinfo("Welcome", "Game directories not found. Please configure them in Settings.")

    def init_ui(self):
        main_container = tb.Frame(self); main_container.pack(fill=BOTH, expand=True)
        self.detail_panel = DetailPanel(main_container, self)
        self.library_panel = LibraryPanel(main_container, self)
        self.tree = self.library_panel.tree
        link_color = self.style.colors.get('primary') or 'blue'; text_widget = self.detail_panel.info_text
        text_widget.text.tag_configure('link', foreground=link_color, underline=True); text_widget.text.tag_configure('header', font="-weight bold")
        text_widget.text.tag_bind('link', '<Button-1>', self._on_text_link_click); text_widget.text.tag_bind('link', '<Enter>', lambda e, w=text_widget.text: w.config(cursor="hand2")); text_widget.text.tag_bind('link', '<Leave>', lambda e, w=text_widget.text: w.config(cursor=""))
        self.detail_panel.lbl_img.bind("<Button-1>", self.on_image_click); self.detail_panel.lbl_img.bind("<Button-3>", self.show_image_context_menu)
        self.toggle_fullscreen(initial_load=True); self.toggle_auto_exit(initial_load=True)
        self.detail_panel.btn_toggle_desc.config(text="Details ON", bootstyle="success")
        if self.playlist_visible:
            self.library_panel.pack(side=LEFT, fill=BOTH, expand=True, padx=(10, 10), pady=(0, 10))
            self.detail_panel.btn_list.config(text="List ON", bootstyle="success")
        else:
            self.detail_panel.btn_list.config(text="List OFF", bootstyle="secondary")
        self.tree.bind("<<TreeviewSelect>>", self.on_select); self.tree.bind("<Double-1>", self.on_double_click); self.tree.bind("<Button-3>", self.show_tree_context)

    def _on_text_link_click(self, event):
        widget = event.widget; index = widget.index(f"@{event.x},{event.y}"); tag_ranges = widget.tag_ranges('link')
        for start, end in zip(tag_ranges[0::2], tag_ranges[1::2]):
            if widget.compare(index, '>=', start) and widget.compare(index, '<', end):
                path_or_url = widget.get(start, end)
                try:
                    if path_or_url.startswith(("http:", "https:", "www.")): webbrowser.open(path_or_url if path_or_url.startswith(("http:", "https:")) else "http://" + path_or_url)
                    elif os.path.exists(path_or_url): os.startfile(os.path.abspath(path_or_url))
                except Exception as e: messagebox.showerror("Error", f"Could not open path or URL:\n{path_or_url}\n\n{e}", parent=self)
                break

    def on_select(self, event=None):
        if not (sel := self.tree.selection()): self.clear_preview(); return
        zip_name = sel[0]; name = os.path.splitext(zip_name)[0]
        is_installed = 'installed' in self.tree.item(zip_name, 'tags'); details = self.logic.get_game_details(name)
        self.detail_panel.update_details(details, is_installed)
        
        # Optimize size calculation by running in thread
        self.detail_panel.lbl_size.config(text="Calculating...")
        def calc_size():
            # Check for zip or 7z
            z_sz = 0
            z_type = ""
            zip_path = os.path.join(self.logic.zipped_dir, f"{name}.zip")
            seven_path = os.path.join(self.logic.zipped_dir, f"{name}.7z")
            
            if os.path.exists(zip_path):
                z_sz = get_file_size(zip_path)
                z_type = "ZIP"
            elif os.path.exists(seven_path):
                z_sz = get_file_size(seven_path)
                z_type = "7z"
                
            h_sz = get_folder_size(os.path.join(self.logic.installed_dir, name)) if is_installed and self.logic.installed_dir else 0
            
            if self.tree.exists(zip_name) and self.tree.selection() and self.tree.selection()[0] == zip_name:
                z_label = f"Archive: {format_size(z_sz)}" if z_type else "Archive: N/A"
                self.detail_panel.lbl_size.config(text=f"{z_label} | HDD: {format_size(h_sz)}")
        threading.Thread(target=calc_size, daemon=True).start()

        self.current_images = self.logic.get_game_images(name); self.current_img_index = 0; self.after(100, self.load_and_display_image)

    def clear_preview(self): self.detail_panel.clear_details(); self.current_images = []

    def on_watch_video(self):
        if not (zip_name := self._get_selected_zip()): return
        details = self.logic.get_game_details(os.path.splitext(zip_name)[0])
        if not (video_links := details.get("video_links", [])): return
        if len(video_links) == 1 and video_links[0].get("url"): webbrowser.open_new_tab(video_links[0].get("url"))
        else:
            menu = tb.Menu(self, tearoff=0); [menu.add_command(label=video.get("title", "Untitled Video"), command=lambda u=url: webbrowser.open_new_tab(u)) for video in video_links if (url := video.get("url"))]
            if menu.index('end') is not None: menu.post(self.detail_panel.btn_watch_video.winfo_rootx(), self.detail_panel.btn_watch_video.winfo_rooty() + self.detail_panel.btn_watch_video.winfo_height())

    def set_rating_from_click(self, rating):
        if item_id := self._get_selected_zip(): self.set_rating(item_id, rating)

    def set_num_players_from_click(self, count):
        if item_id := self._get_selected_zip(): self.set_num_players(item_id, str(count))

    def cycle_num_players(self):
        if not (item_id := self._get_selected_zip()): return
        details = self.logic.get_game_details(os.path.splitext(item_id)[0]); current_val = details.get("num_players", "")
        cycle = ["1", "2", "3", "4", "4+"]; next_index = (cycle.index(current_val) + 1) % len(cycle) if current_val in cycle else 0; self.set_num_players(item_id, cycle[next_index])

    def toggle_description(self):
        self.description_visible = not self.description_visible
        if self.description_visible:
            self.detail_panel.footer_frame.pack_forget()
            self.detail_panel.tabs.pack_forget()
            
            # Pack footer (side=BOTTOM) - it will stack above lbl_size
            self.detail_panel.footer_frame.pack(side=BOTTOM, fill=X, pady=5, padx=10)
            
            # Pack tabs (fill=BOTH, expand=True) - takes remaining space
            self.detail_panel.tabs.pack(fill=BOTH, expand=True, pady=5, padx=10)
            
            self.detail_panel.btn_toggle_desc.config(text="Details ON", bootstyle="success")
            self.geometry(f"{self.winfo_width()}x{self.FULL_HEIGHT}")
        else:
            self.detail_panel.tabs.pack_forget()
            self.detail_panel.btn_toggle_desc.config(text="Details OFF", bootstyle="secondary")
            self.geometry(f"{self.winfo_width()}x{self.COMPACT_HEIGHT}")

    def toggle_list(self):
        self.playlist_visible = not self.playlist_visible
        if self.playlist_visible:
            self.library_panel.pack(side=LEFT, fill=BOTH, expand=True, padx=(10, 10), pady=(0, 10)); self.detail_panel.btn_list.config(text="List ON", bootstyle="success"); self.resizable(True, self.resizable()[1])
            self.geometry(f"{self.DETAIL_PANEL_WIDTH + self.last_library_width}x{self.winfo_height()}"); self.minsize(self.DETAIL_PANEL_WIDTH + self.WINDOW_PADDING_X + 200, self.minsize()[1])
        else:
            if self.state() == 'zoomed': self.state('normal')
            self.last_library_width = self.library_panel.winfo_width(); self.library_panel.pack_forget(); self.detail_panel.btn_list.config(text="List OFF", bootstyle="secondary")
            self.geometry(f"{self.LIST_OFF_WIDTH}x{self.winfo_height()}"); self.resizable(False, self.resizable()[1]); self.minsize(self.LIST_OFF_WIDTH, self.minsize()[1])
        
        # Ensure window is not topmost after toggling list
        self.update_idletasks()
        self.attributes('-topmost', 0)
        self.lift()

    def toggle_fullscreen(self, initial_load=False):
        if not initial_load: is_on = not self.force_fullscreen_var.get(); self.force_fullscreen_var.set(is_on); self.settings.set("force_fullscreen", is_on)
        else: is_on = self.force_fullscreen_var.get()
        self.detail_panel.btn_fullscreen.config(text="Fullscreen ON" if is_on else "Fullscreen OFF", bootstyle="success" if is_on else "secondary-outline")
        self.update_idletasks()

    def toggle_auto_exit(self, initial_load=False):
        if not initial_load: is_on = not self.auto_exit_var.get(); self.auto_exit_var.set(is_on); self.settings.set("auto_exit", is_on)
        else: is_on = self.auto_exit_var.get()
        self.detail_panel.btn_auto_exit.config(text="Auto-close ON" if is_on else "Auto-close OFF", bootstyle="success" if is_on else "secondary-outline")
        self.update_idletasks()
    def toggle_favorite_button(self):
        if zip_name := self._get_selected_zip(): self.logic.toggle_favorite(os.path.splitext(zip_name)[0]); self.refresh_library()

    def launch_with_dosbox(self, zip_name, dosbox_path):
        try:
            # We need to pass this to logic.launch_game.
            # I will update logic.launch_game to accept dosbox_path_override
            thread = self.logic.launch_game(zip_name, dosbox_path_override=dosbox_path, force_fullscreen=self.force_fullscreen_var.get(), auto_exit=self.parent_app.auto_exit_var.get() if hasattr(self, 'parent_app') else self.auto_exit_var.get())
            self._monitor_game_thread(thread, zip_name)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def on_play(self):
        if zip_name := self._get_selected_zip():
            # Check if edit window is open for this game and has unsaved changes
            if self.win_edit and self.win_edit.winfo_exists() and self.win_edit.zip_name == zip_name:
                if self.win_edit.has_unsaved_changes:
                    if messagebox.askyesno("Unsaved Changes", "Configuration window has unsaved changes. Save them before playing?", parent=self):
                        self.win_edit._save(close=False)
                    else:
                        return

            try: 
                if self.settings.get("minimize_on_launch", False):
                    self.iconify()
                thread = self.logic.launch_game(zip_name, force_fullscreen=self.force_fullscreen_var.get(), auto_exit=self.auto_exit_var.get())
                self._monitor_game_thread(thread, zip_name)
            except Exception as e: 
                self.deiconify()
                messagebox.showerror("Error", str(e), parent=self) if "Main executable not set" not in str(e) else (messagebox.showinfo("Setup Required", "Main executable not set. Opening configuration window.", parent=self), self.open_edit_window(switch_to_executables=True))

    def _monitor_game_thread(self, thread, zip_name):
        def check_thread():
            if thread.is_alive():
                self.after(1000, check_thread)
            else:
                print(f"DEBUG: Game thread finished for {zip_name}. Restoring window.")
                self.deiconify()
                if os.name == 'nt':
                    try: self.state('normal') # Restore to normal state (not maximized/zoomed)
                    except: pass
                self.lift() # Ensure it comes to front
                game_name = os.path.splitext(zip_name)[0]
                # Refresh images (screenshots)
                self.current_images = self.logic.get_game_images(game_name)
                self.current_img_index = min(self.current_img_index, len(self.current_images) - 1) if self.current_images else 0
                self.load_and_display_image()
                
                # Refresh library to show updated stats (Play Time, Last Played)
                # We pass save_id to keep selection on the current game
                self.refresh_library(renamed_zip=zip_name)
                
        self.after(1000, check_thread)

    def launch_game(self, item_id):
        # Helper for gamepad or other direct calls
        if 'installed' in self.tree.item(item_id, 'tags'):
            self.on_play()
        else:
            self.on_install()

    def _autosize_columns_on_first_run(self):
        if self.first_load_complete: return
        self.first_load_complete = True; default_font = font.nametofont("TkDefaultFont")
        for col_id in self.tree['columns']:
            header_text = self.tree.heading(col_id, 'text'); max_width = default_font.measure(header_text) + 20
            for item_id in self.tree.get_children():
                if cell_value := self.tree.set(item_id, col_id):
                    if (cell_width := default_font.measure(str(cell_value)) + 10) > max_width: max_width = cell_width
            self.tree.column(col_id, width=max_width, stretch=col_id in ["name", "developers", "publishers"])

    def refresh_library(self, renamed_zip=None, detect_new=False):
        # Check if tree exists to avoid TclError on shutdown/restart
        try:
            if not self.tree.winfo_exists(): return
        except Exception: return

        search = self.search_var.get().lower().strip(); fav_only = self.fav_only_var.get(); save_id = renamed_zip or (self.tree.selection()[0] if self.tree.selection() else None); self.tree.delete(*self.tree.get_children()); data_rows = []
        game_zips, installed_basenames = self.logic.get_game_list()
        
        # Helper for relative time
        def get_relative_time(date_str):
            if not date_str: return ""
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                delta = datetime.now() - dt
                if delta.days == 0: return "Today"
                if delta.days == 1: return "Yesterday"
                return f"{delta.days} days ago"
            except: return date_str

        def format_play_time(seconds):
            if not seconds: return ""
            m, s = divmod(int(seconds), 60)
            h, m = divmod(m, 60)
            if h > 0: return f"{h}h {m}m"
            if m > 0: return f"{m}m"
            return f"{s}s"

        for zip_name in game_zips:
            name_no_zip = os.path.splitext(zip_name)[0]; details = self.logic.get_game_details(name_no_zip)
            if (search and search not in name_no_zip.lower() and search not in details.get('title','').lower()) or (fav_only and not details.get("favorite", False)): continue
            is_inst = name_no_zip in installed_basenames; r = details.get("rating", 0)
            
            # Size calc for sorting
            z_sz = 0
            archive_type = ""
            if self.logic.zipped_dir:
                zp = os.path.join(self.logic.zipped_dir, f"{name_no_zip}.zip")
                sp = os.path.join(self.logic.zipped_dir, f"{name_no_zip}.7z")
                if os.path.exists(zp): 
                    z_sz = get_file_size(zp)
                    archive_type = "ZIP"
                elif os.path.exists(sp): 
                    z_sz = get_file_size(sp)
                    archive_type = "7z"
            
            h_sz = get_folder_size(os.path.join(self.logic.installed_dir, name_no_zip)) if is_inst and self.logic.installed_dir else 0
            
            # Icons Logic: Show both if both exist
            zip_exists = (z_sz > 0)
            
            # Determine icon string for #0 column
            icon_str = ""
            if is_inst and zip_exists:
                icon_str = "📂📦" # Both
            elif is_inst:
                icon_str = "📂" # HDD only
            elif zip_exists:
                icon_str = "📦" # Archive only
            
            disp_name = f"{details.get('title', name_no_zip)}"
            if name_no_zip in self.newly_imported:
                disp_name += " [NEW]"
            disp_name += " ★" if details.get("favorite", False) else ""
            
            cs_text = f"{details['critics_score']}%" if details.get('critics_score', 0) > 0 else ""; play_count = details.get("play_count", 0)
            installed_date = get_relative_time(details.get("installed_date", ""))
            play_time_sec = details.get("play_time", 0)
            play_time_str = format_play_time(play_time_sec)
            
            # Optimization: Only calculate expensive fields if needed or if list is small
            # For now, we keep it but maybe we can cache some of this?
            # The logic.get_game_details is fast (cached in memory), but file system checks are slow.
            
            # New Columns Logic - OPTIMIZED
            # Only check file system if installed
            docs_count = 0
            has_setup = "No"
            has_cds = "No"
            
            if is_inst:
                # Use cached details if possible, but we need real-time status sometimes.
                # Let's trust details for setup/role if available
                exes = details.get("executables", {})
                if any(info.get("role") in [constants.ROLE_SETUP, constants.ROLE_INSTALL] for info in exes.values()):
                    has_setup = "Yes"
                
                # For docs and CDs, we might need to check FS, but maybe we can skip if we are in a hurry?
                # Or cache this in details?
                # For now, let's keep it but be aware it slows down large lists.
                game_folder = self.logic.find_game_folder(name_no_zip)
                
                # Docs - Check only if folder exists
                docs_dir = os.path.join(game_folder, "docs")
                if os.path.isdir(docs_dir):
                     # Just check if not empty instead of counting all files?
                     # docs_count = len(os.listdir(docs_dir)) # Still slow if many files
                     try:
                        with os.scandir(docs_dir) as it:
                            if any(it): docs_count = "Yes" # Just show Yes/No or count? User wants count.
                            # Okay, let's count but limit
                            # docs_count = len([f for f in os.listdir(docs_dir) if os.path.isfile(os.path.join(docs_dir, f))])
                            pass
                     except: pass
                     # Reverting to original count for now, but maybe we can optimize later.
                     if os.path.exists(docs_dir):
                        docs_count = len([f for f in os.listdir(docs_dir) if os.path.isfile(os.path.join(docs_dir, f))])

                # CDs
                cd_dir = os.path.join(game_folder, "cd")
                if os.path.isdir(cd_dir):
                     if any(f.lower().endswith(('.iso', '.cue', '.img', '.bin')) for f in os.listdir(cd_dir)):
                        has_cds = "Yes"

            zip_display = ""
            if z_sz > 0:
                zip_display = format_size(z_sz)

            data_rows.append({
                "id": zip_name, "name": disp_name, "genre": details.get("genre", ""), "year": details.get("year", ""), 
                "developers": details.get("developers", ""), "publishers": details.get("publishers", ""), 
                "rating": "★" * r if r else "", "critics_score": cs_text, "num_players": details.get("num_players", ""), 
                "play_count": play_count if play_count > 0 else "", "last_played": details.get("last_played", ""), 
                "play_time": play_time_str,
                "installed": installed_date, "archive": zip_display, "hdd": format_size(h_sz), 
                "docs": docs_count if docs_count > 0 else "", "setup": has_setup, "cds": has_cds,
                "tag": 'installed' if is_inst else 'zipped', 
                "icon": icon_str,
                "_sort_rating": r, "_sort_zip": z_sz, "_sort_hdd": h_sz, "_sort_critics": details.get("critics_score", 0), 
                "_sort_plays": play_count, "_sort_name": details.get('title', name_no_zip).lower(), "_sort_installed": details.get("installed_date", ""),
                "_sort_play_time": play_time_sec
            })
        
        sort_key_map = {"name": "_sort_name", "rating": "_sort_rating", "archive": "_sort_zip", "hdd": "_sort_hdd", "critics_score": "_sort_critics", "play_count": "_sort_plays", "installed": "_sort_installed", "play_time": "_sort_play_time"}; sort_col_key = sort_key_map.get(self.sort_col, self.sort_col)
        data_rows.sort(key=lambda item: (str(item.get(sort_col_key) or "")).lower() if isinstance(item.get(sort_col_key), str) else (item.get(sort_col_key) or 0), reverse=self.sort_desc)
        
        visible_columns = self.library_panel.columns
        for i, row in enumerate(data_rows):
            tags = (row["tag"], 'even' if i % 2 == 0 else 'odd')
            # Insert with text=row["icon"] for the #0 column
            self.tree.insert("", "end", iid=row["id"], text=row["icon"], values=[row.get(col_id) for col_id in visible_columns], tags=tags)
        
        # Update Grid View (Must be done AFTER tree population because populate_grid reads from tree)
        if hasattr(self.library_panel, 'populate_grid'):
            # Optimization: Only populate grid if it's visible
            if self.library_panel.view_mode == "grid" and self.library_panel.grid_frame.winfo_ismapped():
                self.library_panel.populate_grid()

        # self._autosize_columns_on_first_run() # Disabled to prevent shrinking columns
        if save_id and self.tree.exists(save_id): self.tree.selection_set(save_id); self.tree.see(save_id)
        elif self.tree.get_children(): 
            # Select first item if nothing was selected before (or saved selection is gone)
            first_item = self.tree.get_children()[0]
            self.tree.selection_set(first_item)
            self.tree.see(first_item)
        else: self.clear_preview()
        if self.tree.selection(): self.on_select()
    
    def show_tree_context(self, event, item_id=None):
        if item_id is None:
            # If called from Treeview event
            try:
                item_id = self.tree.identify_row(event.y)
            except:
                pass
        
        if not item_id: return
        
        self.tree.selection_set(item_id); name = os.path.splitext(item_id)[0]; menu = tb.Menu(self, tearoff=0)
        menu.add_command(label="Config Wizard...", command=self.open_config_wizard)
        menu.add_command(label="Rename Game...", command=self.on_rename_game)
        menu.add_command(label="Backup Save Data", command=self.backup_save_data)
        menu.add_separator()
        details = self.logic.get_game_details(name); is_inst = 'installed' in self.tree.item(item_id, 'tags'); zip_exists = os.path.exists(os.path.join(self.logic.zipped_dir, item_id))
        if is_inst:
            menu.add_command(label="▶ Play Game", command=self.on_play, font='-weight bold')
            
            # Start with... submenu
            dosbox_installs = self.settings.get("dosbox_installations", [])
            if len(dosbox_installs) > 1:
                start_with_menu = tb.Menu(menu, tearoff=0)
                for inst in dosbox_installs:
                    inst_name = inst.get("name", "Unknown")
                    # We need to pass the path to launch_game via a temporary override or similar.
                    # Or we can add a 'custom_dosbox_path' arg to launch_game.
                    # Logic.launch_game uses details['custom_dosbox_path'] or default.
                    # We can modify logic to accept an override arg.
                    # But logic.launch_game signature is: launch_game(self, zip_name, specific_exe=None, force_fullscreen=False, auto_exit=False, dos_prompt_only=False)
                    # I need to update logic.launch_game to accept dosbox_override.
                    # For now, I will assume I can update logic.py or use a trick.
                    # Let's update logic.py first? No, I can't easily switch context.
                    # I'll update logic.py in a moment.
                    start_with_menu.add_command(label=inst_name, command=lambda p=inst.get("path"): self.launch_with_dosbox(item_id, p))
                menu.add_cascade(label="Start with...", menu=start_with_menu)

            if setup_exe := next((exe for exe, info in details.get("executables", {}).items() if info.get("role") in [constants.ROLE_SETUP, constants.ROLE_INSTALL]), None): menu.add_command(label="Run Setup / Install", command=lambda e=setup_exe: self.run_specific_exe(e))
            if custom_exes := {info.get("title", exe): exe for exe, info in details.get("executables", {}).items() if info.get("role") == constants.ROLE_CUSTOM and info.get("title")}:
                custom_menu = tb.Menu(menu, tearoff=0); [custom_menu.add_command(label=title, command=lambda e=exe_path: self.run_specific_exe(e)) for title, exe_path in sorted(custom_exes.items())]; menu.add_cascade(label="Custom / Addons", menu=custom_menu)
            if all_executables := self.logic.get_all_executables(name):
                run_specific_menu = tb.Menu(menu, tearoff=0); [run_specific_menu.add_command(label=truncate_text(exe, 40), command=lambda e=exe: self.run_specific_exe(e)) for exe in all_executables]; menu.add_cascade(label="Run Specific EXE", menu=run_specific_menu)
            menu.add_command(label="Open DOS Prompt", command=self.open_dos_prompt); menu.add_separator(); menu.add_command(label="Open Game Directory", command=self.open_game_directory); menu.add_command(label="Standardize Game Folder...", command=self.on_standardize_game)
            
            # Export / Backup Menu
            export_menu = tb.Menu(menu, tearoff=0)
            export_menu.add_command(label="Export to ZIP", command=self.on_export_zip)
            export_menu.add_command(label="Export to 7z", command=self.on_export_7z)
            
            standalone_menu = tb.Menu(export_menu, tearoff=0)
            standalone_menu.add_command(label="FLAT", command=lambda: self.on_make_standalone(flat=True))
            standalone_menu.add_command(label="DIR", command=lambda: self.on_make_standalone(flat=False))
            export_menu.add_cascade(label="Make Standalone Game", menu=standalone_menu)
            
            menu.add_cascade(label="Export...", menu=export_menu)
            menu.add_command(label="Archive Game", command=self.on_archive_game)
            menu.add_separator()
        menu.add_command(label="💔 Unfavorite" if details.get("favorite", False) else "★ Favorite", command=lambda: self.toggle_fav_from_context(name))
        players_menu = tb.Menu(menu, tearoff=0); menu.add_cascade(label="Number of Players", menu=players_menu); [players_menu.add_command(label=p, command=lambda num=p: self.set_num_players(item_id, num)) for p in ["1", "2", "3", "4", "4+"]]
        rate_menu = tb.Menu(menu, tearoff=0); menu.add_cascade(label="User Rating", menu=rate_menu); [rate_menu.add_command(label="★" * i, command=lambda r=i: self.set_rating(item_id, r)) for i in range(1, 6)]
        menu.add_separator(); menu.add_command(label="✎ Configuration", command=self.open_edit_window, state="normal" if is_inst else "disabled"); menu.add_separator()
        menu.add_command(label="Install Game", command=self.on_install, state="normal" if not is_inst and zip_exists else "disabled"); menu.add_command(label="Uninstall Game", command=self.on_uninstall, state="normal" if is_inst else "disabled")
        if zip_exists: menu.add_command(label="Delete Archive", command=self.on_delete_zip)
        menu.post(event.x_root, event.y_root)

    def on_rename_game(self):
        if not (zip_name := self._get_selected_zip()): return
        game_name = os.path.splitext(zip_name)[0]
        
        new_name = simpledialog.askstring("Rename Game", "Enter new name:", initialvalue=game_name, parent=self)
        if not new_name or new_name == game_name: return
        
        self.logger.log(f"Renaming game: {game_name} -> {new_name}", category="rename")
        
        # Handle case-only rename
        if new_name.lower() == game_name.lower():
             temp_name = f"{game_name}_TEMP_{int(datetime.now().timestamp())}"
             _, err = self.logic.rename_game(game_name, temp_name)
             if err:
                 messagebox.showerror("Rename Error", f"Intermediate rename failed: {err}", parent=self)
                 self.logger.log(f"Rename failed (intermediate): {err}", level="error", category="rename")
                 return
             game_name = temp_name # Update current state to temp
             # Now rename temp to new_name
             renamed_name, error = self.logic.rename_game(game_name, new_name)
        else:
             renamed_name, error = self.logic.rename_game(game_name, new_name)
             
        if error:
            messagebox.showerror("Rename Error", error, parent=self)
            self.logger.log(f"Rename failed: {error}", level="error", category="rename")
        else:
            self.logger.log(f"Rename successful: {renamed_name}", category="rename")
            self.refresh_library(renamed_zip=f"{renamed_name}.zip")

    def _run_long_operation(self, operation, *args, **kwargs):
        success_message = kwargs.pop('success_message', "Operation successful."); busy_win = BusyWindow(self); q = queue.Queue()
        def run_op():
            try: q.put(("success", operation(*args, **kwargs)))
            except Exception as e: q.put(("error", e))
        threading.Thread(target=run_op, daemon=True).start()
        def check_queue():
            try:
                msg_type, data = q.get_nowait(); busy_win.destroy()
                if msg_type == "error": messagebox.showerror("Error", str(data), parent=self)
                else:
                    result, error_msg = data if isinstance(data, tuple) else (data, None)
                    if error_msg: messagebox.showerror("Error", error_msg, parent=self)
                    else: messagebox.showinfo("Success", success_message.format(result=result), parent=self)
                    self.refresh_library(renamed_zip=f"{result}.zip" if result and not error_msg else None)
            except queue.Empty: self.after(100, check_queue)
        self.after(100, check_queue)

    def _handle_overwrite(self, initial_path):
        current_path = initial_path
        while os.path.exists(current_path):
            if (answer := messagebox.askyesnocancel("Confirm Overwrite", f"The file '{os.path.basename(current_path)}' already exists. Overwrite it?", parent=self)) is True: return current_path
            elif answer is False:
                if new_name := simpledialog.askstring("New File Name", "Enter a new file name (without extension):", parent=self, initialvalue=os.path.splitext(os.path.basename(current_path))[0]): current_path = os.path.join(os.path.dirname(current_path), f"{new_name}.zip")
                else: return None
            else: return None
        return current_path

    def on_archive_game(self):
        if not (zip_name := self._get_selected_zip()): return
        game_name = os.path.splitext(zip_name)[0]
        
        # Target path in zipped_dir
        # Default to 7z if available, else zip
        ext = ".7z" if self.logic.HAS_7ZIP else ".zip"
        archive_path = os.path.join(self.logic.zipped_dir, f"{game_name}{ext}")
        
        if os.path.exists(archive_path):
            if not messagebox.askyesno("Archive Exists", f"Archive '{os.path.basename(archive_path)}' already exists.\nDo you want to replace it?", parent=self):
                return
        
        # Progress Window
        progress_win = tb.Toplevel(self)
        progress_win.title("Archiving Game...")
        progress_win.geometry("400x150")
        progress_win.transient(self)
        progress_win.grab_set()
        
        tb.Label(progress_win, text=f"Archiving '{game_name}'...", bootstyle="info").pack(pady=10)
        progress_bar = tb.Progressbar(progress_win, mode='determinate')
        progress_bar.pack(fill=X, padx=20, pady=10)
        lbl_status = tb.Label(progress_win, text="Starting...")
        lbl_status.pack(pady=5)
        
        def update_progress(current, total, message=""):
            if total > 0:
                pct = (current / total) * 100
                progress_bar['value'] = pct
            if message:
                lbl_status.config(text=message)
            progress_win.update()

        def run_op():
            try:
                # Use make_7z_archive or make_zip_archive
                if ext == ".7z":
                    self.logic.make_7z_archive(game_name, archive_path, progress_callback=update_progress)
                else:
                    self.logic.make_zip_archive(game_name, archive_path, progress_callback=update_progress)
                    
                progress_win.destroy()
                messagebox.showinfo("Archive Complete", f"Game archived to:\n{archive_path}", parent=self)
                self.refresh_library(renamed_zip=f"{game_name}.zip")
            except Exception as e:
                progress_win.destroy()
                messagebox.showerror("Error", str(e), parent=self)

        threading.Thread(target=run_op, daemon=True).start()

    def on_export_zip(self):
        if not (zip_name := self._get_selected_zip()): return
        game_name = os.path.splitext(zip_name)[0]
        # Export goes to export_dir
        target_path = os.path.join(self.logic.export_dir, f"{game_name}.zip")
        self._handle_archive_creation(game_name, target_path, self.logic.make_zip_archive, "Export (ZIP)")

    def on_export_7z(self):
        if not (zip_name := self._get_selected_zip()): return
        game_name = os.path.splitext(zip_name)[0]
        # Export goes to export_dir
        target_path = os.path.join(self.logic.export_dir, f"{game_name}.7z")
        self._handle_archive_creation(game_name, target_path, self.logic.make_7z_archive, "Export (7z)")

    # Legacy aliases if needed, or just remove
    def on_make_zip(self): self.on_export_zip()
    def on_make_7z(self): self.on_export_7z()

    def _handle_archive_creation(self, game_name, target_path, method, type_name):
        # Ensure export dir exists if exporting
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        if os.path.exists(target_path):
            dialog = tb.Toplevel(self); dialog.title("File Exists"); dialog.geometry("400x250"); dialog.transient(self)
            tb.Label(dialog, text=f"The file '{os.path.basename(target_path)}' already exists.\nWhat do you want to do?", wraplength=350).pack(pady=20)
            self._zip_action = "cancel"
            def set_action(action): self._zip_action = action; dialog.destroy()
            tb.Button(dialog, text="Overwrite (Replace)", command=lambda: set_action("overwrite"), bootstyle="danger").pack(fill=X, padx=20, pady=5)
            tb.Button(dialog, text=f"Rename New File", command=lambda: set_action("rename"), bootstyle="info").pack(fill=X, padx=20, pady=5)
            tb.Button(dialog, text="Cancel", command=lambda: set_action("cancel"), bootstyle="secondary").pack(fill=X, padx=20, pady=5)
            self.wait_window(dialog)
            if self._zip_action == "cancel": return
            elif self._zip_action == "rename":
                ext = os.path.splitext(target_path)[1]
                dir_path = os.path.dirname(target_path)
                if new_name := simpledialog.askstring("New File Name", "Enter a new file name (without extension):", parent=self, initialvalue=f"{game_name}_new"): target_path = os.path.join(dir_path, f"{new_name}{ext}")
                else: return

        # Progress Window
        progress_win = tb.Toplevel(self)
        progress_win.title(f"Creating {type_name}...")
        progress_win.geometry("400x150")
        progress_win.transient(self)
        progress_win.grab_set()
        
        tb.Label(progress_win, text=f"Archiving '{game_name}'...", bootstyle="info").pack(pady=10)
        progress_bar = tb.Progressbar(progress_win, mode='determinate')
        progress_bar.pack(fill=X, padx=20, pady=10)
        lbl_status = tb.Label(progress_win, text="Starting...")
        lbl_status.pack(pady=5)
        
        def update_progress(current, total):
            if total > 0:
                pct = (current / total) * 100
                progress_bar['value'] = pct
                lbl_status.config(text=f"Processed {current}/{total} files ({int(pct)}%)")
            progress_win.update()

        # Run in thread
        def run_op():
            try:
                # Check if method accepts progress_callback
                import inspect
                sig = inspect.signature(method)
                if 'progress_callback' in sig.parameters:
                    method(game_name, target_path, progress_callback=update_progress)
                else:
                    method(game_name, target_path)
                
                progress_win.destroy()
                messagebox.showinfo("Success", f"Game '{game_name}' has been processed into:\n{os.path.basename(target_path)}", parent=self)
                self.refresh_library(renamed_zip=f"{game_name}.zip") # Refresh to show new archive size if applicable
            except Exception as e:
                progress_win.destroy()
                messagebox.showerror("Error", str(e), parent=self)

        threading.Thread(target=run_op, daemon=True).start()

    def on_make_standalone(self, flat):
        if not (zip_name := self._get_selected_zip()): return
        game_name = os.path.splitext(zip_name)[0]; details = self.logic.get_game_details(game_name); msdos_name = "GAME"
        if (exe_paths := details.get("executables")) and (first_exe_path := next(iter(exe_paths), None)):
            path_parts = first_exe_path.replace("\\", "/").split('/')
            if len(path_parts) > 2 and path_parts[0] == 'drives' and path_parts[1] == 'c': msdos_name = path_parts[2]
        if not (output_path := self._handle_overwrite(os.path.join(self.logic.export_dir, f"{game_name}_standalone.zip"))): return
        self._run_long_operation(self.logic.make_standalone_archive, game_name, msdos_name, output_path, flat_structure=flat, success_message="Standalone game created successfully.")
        
    def on_standardize_game(self):
        if not (zip_name := self._get_selected_zip()): return
        game_name = os.path.splitext(zip_name)[0]
        if not (self.win_standardize and self.win_standardize.winfo_exists()): self.win_standardize = StandardizeWindow(self, self.logic, game_name)
        self.win_standardize.lift()

    def run_specific_exe(self, exe_file):
        if zip_name := self._get_selected_zip():
            self.logger.log(f"Launching specific exe: {exe_file} for {zip_name}", category="launch")
            try: 
                # Check minimize setting
                if self.settings.get("minimize_on_launch", False):
                    try: self.iconify()
                    except: pass
                
                # Ensure app is not topmost
                self.attributes("-topmost", False)
                thread = self.logic.launch_game(zip_name, specific_exe=exe_file, force_fullscreen=self.force_fullscreen_var.get(), auto_exit=self.auto_exit_var.get())
                
                def check_thread():
                    if thread.is_alive():
                        self.after(1000, check_thread)
                    else:
                        if self.settings.get("minimize_on_launch", False):
                            self.deiconify()
                        self.lift() # Bring back to front
                        game_name = os.path.splitext(zip_name)[0]
                        self.current_images = self.logic.get_game_images(game_name)
                        self.current_img_index = min(self.current_img_index, len(self.current_images) - 1) if self.current_images else 0
                        self.load_and_display_image()
                
                self.after(1000, check_thread)
                
            except Exception as e: 
                # self.deiconify()
                self.lift()
                messagebox.showerror("Error", str(e), parent=self)
                self.logger.log(f"Launch failed: {e}", level="error", category="launch")

    def open_dos_prompt(self):
        if zip_name := self._get_selected_zip():
            self.logger.log(f"Opening DOS prompt for {zip_name}", category="launch")
            try: 
                # Check minimize setting
                if self.settings.get("minimize_on_launch", False):
                    try: self.iconify()
                    except: pass
                    
                self.attributes("-topmost", False)
                thread = self.logic.launch_game(zip_name, dos_prompt_only=True, force_fullscreen=self.force_fullscreen_var.get(), auto_exit=False)
                
                def check_thread():
                    if thread.is_alive():
                        self.after(1000, check_thread)
                    else:
                        if self.settings.get("minimize_on_launch", False):
                            self.deiconify()
                        self.lift()
                        game_name = os.path.splitext(zip_name)[0]
                        self.current_images = self.logic.get_game_images(game_name)
                        self.current_img_index = min(self.current_img_index, len(self.current_images) - 1) if self.current_images else 0
                        self.load_and_display_image()
                
                self.after(1000, check_thread)
                
            except Exception as e: 
                # self.deiconify()
                self.lift()
                messagebox.showerror("Error", str(e), parent=self)
                self.logger.log(f"DOS prompt failed: {e}", level="error", category="launch")

    def open_game_directory(self):
        if not (zip_name := self._get_selected_zip()): return
        game_folder = self.logic.find_game_folder(os.path.splitext(zip_name)[0])
        if os.path.isdir(game_folder): 
            # Ensure app is not topmost
            self.attributes("-topmost", False)
            os.startfile(game_folder)
        else: messagebox.showerror("Error", "Game directory not found.", parent=self)
        
    def load_and_display_image(self):
        dp = self.detail_panel
        
        # Filter out missing files from current_images
        if self.current_images:
            self.current_images = [p for p in self.current_images if os.path.exists(p)]
            
        if not self.current_images: 
            dp.lbl_img.config(image='', text="No Image")
            dp.lbl_img.image = None
            dp.lbl_img_info.config(text="")
            return
            
        if self.current_img_index >= len(self.current_images): self.current_img_index = 0
        path = self.current_images[self.current_img_index]
        
        # Double check existence (redundant but safe)
        if not os.path.exists(path):
             # Should not happen due to filter above, but if it does, recurse
             self.load_and_display_image()
             return

        if path.lower().endswith(('.mp4', '.avi', '.mkv')): dp.lbl_img.config(image='', text=f"▶ Play Video\n(requires VLC)"); dp.lbl_img.image = None; dp.lbl_img_info.config(text=f"Video {self.current_img_index + 1} of {len(self.current_images)}" if len(self.current_images) > 1 else ""); return
        if not HAS_PILLOW: dp.lbl_img.config(image='', text="Pillow library not found"); dp.lbl_img.image = None; return
        try:
            width, height = dp.lbl_img.winfo_width(), dp.lbl_img.winfo_height()
            if width <= 1 or height <= 1: self.after(100, self.load_and_display_image); return
            with Image.open(path) as img:
                if img := self.logic.resize_image(img, (width, height)): photo_img = ImageTk.PhotoImage(img); dp.lbl_img.image = photo_img; dp.lbl_img.config(image=photo_img); dp.lbl_img_info.config(text=f"Image {self.current_img_index + 1} of {len(self.current_images)}" if len(self.current_images) > 1 else "")
                else: raise Exception("Resize failed")
        except Exception as e: dp.lbl_img.config(image='', text="Image Error"); dp.lbl_img.image = None; print(f"Image Error: {e}")
    
    def on_image_click(self, event=None):
        if not self.current_images: return
        path = self.current_images[self.current_img_index]
        if path.lower().endswith(('.mp4', '.avi', '.mkv')):
            if self.vlc_path:
                try: subprocess.Popen([self.vlc_path, path], creationflags=0x08000000 if os.name == 'nt' else 0)
                except Exception as e: messagebox.showerror("VLC Error", f"Could not start VLC:\n{e}", parent=self)
            else: messagebox.showwarning("VLC Not Found", "VLC Media Player is not installed or couldn't be found in standard locations.", parent=self)
        else: self.next_image()

    def next_image(self, event=None):
        if len(self.current_images) > 1: self.current_img_index = (self.current_img_index + 1) % len(self.current_images); self.load_and_display_image()
    def on_double_click(self, event=None):
        if (zip_name := self._get_selected_zip()): 
            if 'installed' in self.tree.item(zip_name, 'tags'):
                self.on_play()
            else:
                # Ask for confirmation before install
                game_name = os.path.splitext(zip_name)[0]
                if messagebox.askyesno("Install Game", f"About to install '{game_name}'.\n\nDo you want to continue?", parent=self):
                    self.on_install()
    def _move_selection(self, direction):
        if not (selected_id := self._get_selected_zip()) or not (all_ids := self.tree.get_children()): return
        try: current_index = all_ids.index(selected_id); new_index = (current_index + direction) % len(all_ids); self.tree.selection_set(all_ids[new_index]); self.tree.see(all_ids[new_index])
        except ValueError: pass
    def select_prev(self, event=None): self._move_selection(-1)
    def select_next(self, event=None): self._move_selection(1)
    def _get_selected_zip(self): return self.tree.selection()[0] if self.tree.selection() else None
    
    def on_install(self):
        if not (zip_name := self._get_selected_zip()): return
        old_name = os.path.splitext(zip_name)[0]
        
        # Use exact archive name as folder name (as requested)
        new_folder_name = old_name.strip()
        if not new_folder_name: new_folder_name = "GAME"
        
        # Check if we have a real archive
        source_path = None
        if os.path.exists(os.path.join(self.logic.zipped_dir, f"{old_name}.zip")):
            source_path = os.path.join(self.logic.zipped_dir, f"{old_name}.zip")
        elif os.path.exists(os.path.join(self.logic.zipped_dir, f"{old_name}.7z")):
            source_path = os.path.join(self.logic.zipped_dir, f"{old_name}.7z")
            
        if not source_path:
             messagebox.showerror("Error", "Archive file not found.", parent=self)
             return

        # Progress Window
        progress_win = tb.Toplevel(self)
        progress_win.title("Installing...")
        progress_win.geometry("400x150")
        progress_win.transient(self)
        progress_win.grab_set()
        
        tb.Label(progress_win, text=f"Installing '{old_name}'...", bootstyle="info").pack(pady=10)
        progress_bar = tb.Progressbar(progress_win, mode='determinate')
        progress_bar.pack(fill=X, padx=20, pady=10)
        lbl_status = tb.Label(progress_win, text="Starting...")
        lbl_status.pack(pady=5)
        
        def update_progress(current, total):
            if total > 0:
                pct = (current / total) * 100
                progress_bar['value'] = pct
                lbl_status.config(text=f"Extracted {current}/{total} files ({int(pct)}%)")
            progress_win.update()

        def run_op():
            try:
                # We need to modify logic.install_game to accept progress_callback
                # Or we can wrap it if logic supports it.
                # I will update logic.install_game to support it.
                self.logic.install_game(zip_name, new_folder_name, source_path=source_path, progress_callback=update_progress)
                
                progress_win.destroy()
                messagebox.showinfo("Success", f"Game '{old_name}' installed successfully.", parent=self)
                self.refresh_library(renamed_zip=zip_name)
            except Exception as e:
                progress_win.destroy()
                messagebox.showerror("Error", str(e), parent=self)

        # Check if archive exists
        archive_exists = False
        if os.path.exists(os.path.join(self.logic.zipped_dir, f"{game_name}.zip")): archive_exists = True
        elif os.path.exists(os.path.join(self.logic.zipped_dir, f"{game_name}.7z")): archive_exists = True
        
    def on_uninstall(self):
        if not (zip_name := self._get_selected_zip()): return
        game_name = os.path.splitext(zip_name)[0]
        
        # Check if archive exists
        archive_exists = False
        if os.path.exists(os.path.join(self.logic.zipped_dir, f"{game_name}.zip")): archive_exists = True
        elif os.path.exists(os.path.join(self.logic.zipped_dir, f"{game_name}.7z")): archive_exists = True
        
        msg = "This will permanently delete the game's installed files."
        if not archive_exists:
            msg += "\n\nWARNING: Archive not found! Metadata and screenshots will also be deleted!"
            
        if messagebox.askyesno(f"Confirm Uninstall: {game_name}", msg, parent=self): 
            self.logic.uninstall_game(zip_name)
            if not archive_exists:
                # Delete metadata folder
                meta_dir = os.path.join(self.logic.base_dir, "database", "games_datainfo", game_name)
                if os.path.exists(meta_dir):
                    shutil.rmtree(meta_dir, ignore_errors=True)
            self.refresh_library()

    def on_delete_zip(self):
        if not (zip_name := self._get_selected_zip()): return
        # zip_name might be .zip or .7z or virtual .zip
        # We need to find the actual file
        name = os.path.splitext(zip_name)[0]
        target = None
        if os.path.exists(os.path.join(self.logic.zipped_dir, f"{name}.zip")):
            target = os.path.join(self.logic.zipped_dir, f"{name}.zip")
        elif os.path.exists(os.path.join(self.logic.zipped_dir, f"{name}.7z")):
            target = os.path.join(self.logic.zipped_dir, f"{name}.7z")
            
        if not target:
            messagebox.showerror("Error", "Archive file not found.", parent=self)
            return

        # Check if game is installed
        is_installed = 'installed' in self.tree.item(zip_name, 'tags')
        
        msg = f"This will permanently delete the archive file '{os.path.basename(target)}'. This cannot be undone."
        if not is_installed:
            msg += "\n\nWARNING: Game is not installed! Metadata and screenshots will also be deleted!"

        if messagebox.askyesno(f"Confirm Delete: {os.path.basename(target)}", msg, parent=self):
            try: 
                os.remove(target)
                if not is_installed:
                    # Delete metadata folder
                    meta_dir = os.path.join(self.logic.base_dir, "database", "games_datainfo", name)
                    if os.path.exists(meta_dir):
                        shutil.rmtree(meta_dir, ignore_errors=True)
                self.refresh_library()
            except Exception as e: messagebox.showerror("Error", f"Failed to delete archive file: {e}", parent=self)

    def open_settings(self):
        if not (self.win_settings and self.win_settings.winfo_exists()): self.win_settings = SettingsWindow(self)
        self.win_settings.lift()

    def open_edit_window(self, switch_to_executables=False):
        if not (zip_name := self._get_selected_zip()): return
        if 'installed' not in self.tree.item(zip_name, 'tags'): messagebox.showinfo("Not Installed", "Configuration is only available for installed games.", parent=self); return
        if not (self.win_edit and self.win_edit.winfo_exists()) or self.win_edit.name != os.path.splitext(zip_name)[0]:
            if self.win_edit: self.win_edit.destroy()
            self.win_edit = EditWindow(self, zip_name)
            # self.win_edit.grab_set() # Removed modality as requested
        self.win_edit.lift()
        if switch_to_executables and hasattr(self.win_edit, 'tab_executables'):
             self.win_edit.tabs.select(self.win_edit.tab_executables)

    def open_config_wizard(self, zip_name=None, disable_config_option=False):
        if not zip_name:
            if not (zip_name := self._get_selected_zip()): return
        if 'installed' not in self.tree.item(zip_name, 'tags'):
             if messagebox.askyesno("Not Installed", "Game is not installed. Install it now to proceed with the Wizard?", parent=self):
                 self.on_install()
                 return
             else:
                 return
        
        self.logger.log(f"Opening Config Wizard for {zip_name}", category="wizard")
        wizard = ConfigWizard(self, zip_name, disable_config_option=disable_config_option)
        self.wait_window(wizard)
        
        # Only open edit window if wizard signaled it (via should_open_config on parent)
        # The wizard sets self.should_open_config = True on the parent (self) if checkbox is checked
        if getattr(self, 'should_open_config', False):
            self.open_edit_window()
            # Reset flag
            self.should_open_config = False

    def sort_tree(self, col): self.sort_desc = not self.sort_desc if self.sort_col == col else False; self.sort_col = col; self.refresh_library()
    def save_notes(self):
        if sel := self._get_selected_zip(): details = self.logic.get_game_details(os.path.splitext(sel)[0]); details["notes"] = self.detail_panel.txt_notes.text.get(1.0, tk.END).strip(); self.logic.save_game_details(os.path.splitext(sel)[0], details)
    def toggle_fav_from_context(self, name): self.logic.toggle_favorite(name); self.refresh_library()
    def set_rating(self, item_id, rating): name = os.path.splitext(item_id)[0]; details = self.logic.get_game_details(name); details["rating"] = rating; self.logic.save_game_details(name, details); self.refresh_library()
    def set_num_players(self, item_id, num_players): name = os.path.splitext(item_id)[0]; details = self.logic.get_game_details(name); details["num_players"] = num_players; self.logic.save_game_details(name, details); self.refresh_library()
    
    def show_image_context_menu(self, event):
        if not self.current_images: return
        menu = tb.Menu(self, tearoff=0); menu.add_command(label="Delete Image", command=self.delete_current_image); menu.add_command(label="Open Screenshots Folder", command=self.open_screenshots_folder); menu.post(event.x_root, event.y_root)

    def delete_current_image(self):
        if not self.current_images: return
        img_path = self.current_images[self.current_img_index]
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently delete this image?\n\n{os.path.basename(img_path)}", parent=self):
            try:
                os.remove(img_path); game_name = os.path.splitext(self._get_selected_zip())[0]; self.current_images = self.logic.get_game_images(game_name)
                self.current_img_index = min(self.current_img_index, len(self.current_images) - 1) if self.current_images else 0
                self.load_and_display_image()
            except Exception as e: messagebox.showerror("Error", f"Could not delete image: {e}", parent=self)

    def open_screenshots_folder(self):
        if not (zip_name := self._get_selected_zip()): return
        game_name = os.path.splitext(zip_name)[0]; screens_dir = os.path.join(self.logic.base_dir, "database", "games_datainfo", game_name, "screenshots")
        if os.path.isdir(screens_dir): os.startfile(screens_dir)
        else: messagebox.showinfo("No Folder", "This game does not have a screenshots folder yet.", parent=self)
