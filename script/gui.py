import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import os
import sys
import webbrowser
import json
import subprocess
import importlib.util
import re

# Imports from our modules
from constants import *
from utils import format_size, truncate_text, get_folder_size, get_file_size
from settings import SettingsManager
from logic import GameLogic, HAS_PILLOW
from windows.settings_window import SettingsWindow
from windows.edit_window import EditWindow
from components.detail_panel import DetailPanel
from components.library_panel import LibraryPanel


if HAS_PILLOW:
    from PIL import Image, ImageTk, ImageGrab

class DOSManagerApp(tb.Window):
    def __init__(self):
        # 1. Load settings and initialize theme
        self.settings = SettingsManager()
        theme = self.settings.get("theme")
        if not theme:
            theme = "darkly"
            
        super().__init__(themename=theme)
        self.title("DOS Game Manager")
        self.geometry("1350x950")
        
        self.load_custom_themes()

        # 2. Initialize logic and state variables
        self.logic = GameLogic(self.settings)
        self.win_settings = None
        self.win_edit = None
        self.playlist_visible = True
        self.current_images = []
        self.current_img_index = 0
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.refresh_library())
        self.fav_only_var = tk.BooleanVar(value=False)
        self.sort_col = "name"
        self.sort_desc = False

        # 3. Initialize UI
        self.init_ui()
        self.minsize(600, 768)
        self.bind('<Control-v>', self.paste_screenshot)

        # 4. Initial library load
        if os.path.exists(self.settings.get("root_dir")):
            self.refresh_library()
        else:
            messagebox.showinfo("Welcome", "Please configure Settings (DOSBox EXE & Folders).")

    def load_custom_themes(self):
        themes_dir = os.path.join(BASE_DIR, "themes")
        if not os.path.exists(themes_dir): return
        for f in os.listdir(themes_dir):
            if f.endswith(".json"):
                try:
                    full_path = os.path.join(themes_dir, f)
                    self.style.load_user_themes(full_path)
                except Exception as e:
                    print(f"Failed to load theme {f}: {e}")

    def init_ui(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        
        # Create panels from components
        self.detail_panel = DetailPanel(self, self.logic)
        self.library_panel = LibraryPanel(self)
        self.tree = self.library_panel.tree # Make tree accessible for other methods

    def sort_tree(self, col):
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col = col
            self.sort_desc = False
        self.refresh_library()

    def refresh_library(self):
        search = self.search_var.get().lower().strip()
        fav_only = self.fav_only_var.get()
        selected = self.tree.selection()
        save_id = selected[0] if selected else None
        
        for i in self.tree.get_children(): self.tree.delete(i)
        
        game_list, installed_set = self.logic.get_game_list()
        data_rows = []

        for zip_name in game_list:
            name_no_zip = os.path.splitext(zip_name)[0]
            if search and search not in name_no_zip.lower(): continue
            
            is_fav = self.logic.is_favorite(name_no_zip)
            if fav_only and not is_fav: continue
            
            is_inst = zip_name in installed_set
            
            g = self.logic.load_meta(name_no_zip, ".genre")
            y = self.logic.load_meta(name_no_zip, ".year")
            c = self.logic.load_meta(name_no_zip, ".company")
            r = self.logic.load_rating(name_no_zip)
            z_sz = get_file_size(os.path.join(self.logic.zipped_dir, zip_name))
            h_sz = get_folder_size(os.path.join(self.logic.installed_dir, name_no_zip)) if is_inst else 0
            
            prefix = "✓" if is_inst else "…"
            disp = f"{prefix} {name_no_zip}"
            if is_fav: disp += f" ★"
            
            tag = 'installed' if is_inst else 'zipped'
            rating_stars = "★" * r if r else ""
            row_data = {
                "disp_name": disp, "genre": g, "year": y, "company": c,
                "rating_str": rating_stars, "zip_str": format_size(z_sz), "hdd_str": format_size(h_sz),
                "id": zip_name, "tag": tag, "rating_val": r, "zip_val": z_sz, "hdd_val": h_sz
            }
            data_rows.append(row_data)
            
        # Sorting
        sort_map = { "name": "id", "genre": "genre", "company": "company", "year": "year",
                     "rating": "rating_val", "zip": "zip_val", "hdd": "hdd_val" }
        sort_key_name = sort_map.get(self.sort_col, "id")
        
        data_rows.sort(key=lambda item: (item[sort_key_name] or "").lower() if isinstance(item[sort_key_name], str) else (item[sort_key_name] or 0), 
                       reverse=self.sort_desc)

        # Inserting into tree
        for row in data_rows:
            values = (row["disp_name"], row["genre"], row["year"], row["company"], row["rating_str"], row["zip_str"], row["hdd_str"])
            self.tree.insert("", "end", iid=row["id"], values=values, tags=(row["tag"],))
            
        # Reselect item
        if save_id and self.tree.exists(save_id):
            self.tree.selection_set(save_id)
            self.tree.see(save_id)
            self.on_select(None)
        elif data_rows:
            first_id = data_rows[0]["id"]
            if self.tree.exists(first_id):
                self.tree.selection_set(first_id)
                self.on_select(None)
        else:
            self.clear_preview()

    def on_select(self, event=None):
        sel = self.tree.selection()
        if not sel: self.clear_preview(); return
        zip_name = sel[0]
        name = os.path.splitext(zip_name)[0]
        tags = self.tree.item(zip_name, 'tags')
        is_installed = 'installed' in tags
        
        # Update detail panel widgets
        dp = self.detail_panel
        dp.btn_edit.configure(state=tk.NORMAL)
        if is_installed:
            dp.btn_install.configure(state=tk.DISABLED, bootstyle="secondary")
            dp.btn_play.configure(state=tk.NORMAL, bootstyle="success")
            dp.btn_uninstall.configure(state=tk.NORMAL, bootstyle="danger-outline")
            dp.btn_backup.configure(state=tk.NORMAL, bootstyle="info-outline")
            isos = self.logic.get_mounted_isos(name)
            iso_txt = "\n".join([f"• D:\\ {iso}" for iso in isos]) if isos else "None"
            sheet_text = f"GAME: {name}\n\n[ DOSBox Shortcuts ]\nCtrl+F12  : Speed Up\nCtrl+F11  : Slow Down\nCtrl+F4   : Swap CD/Refresh\nAlt+Enter : Fullscreen\nCtrl+F5   : Screenshot\nCtrl+F10  : Unlock Mouse\n\n[ Mounted ISOs ]\n{iso_txt}"
            dp.lbl_sheet.config(text=sheet_text)
        else:
            dp.btn_install.configure(state=tk.NORMAL, bootstyle="primary")
            dp.btn_play.configure(state=tk.DISABLED, bootstyle="secondary")
            dp.btn_uninstall.configure(state=tk.DISABLED, bootstyle="secondary")
            dp.btn_backup.configure(state=tk.DISABLED, bootstyle="secondary")
            dp.lbl_sheet.config(text="Install game to see details.")

        title_text = truncate_text(name.replace("_"," ").title(), 30)
        if self.logic.is_favorite(name): title_text += f" ★"
        dp.lbl_title.config(text=title_text)
        
        y = self.logic.load_meta(name, ".year")
        c = self.logic.load_meta(name, ".company")
        g = self.logic.load_meta(name, ".genre")
        txt_meta = f"[{g}] " if g else ""
        txt_meta += f"Year: {y} " if y else ""
        txt_meta += f"| Dev: {truncate_text(c, 20)}" if c else ""
        dp.lbl_year.config(text=txt_meta)
        dp.lbl_comp.config(text="") 

        r = self.logic.load_rating(name)
        dp.lbl_rating.config(text="★" * r if r else "")
        
        desc = self.logic.load_meta(name, ".txt")
        dp.txt_desc.config(state=tk.NORMAL)
        dp.txt_desc.delete(1.0, tk.END)
        dp.txt_desc.insert(tk.END, desc or "No description.")
        dp.txt_desc.config(state=tk.DISABLED)

        notes = self.logic.load_meta(name, ".notes")
        dp.txt_notes.delete(1.0, tk.END)
        dp.txt_notes.insert(tk.END, notes or "")

        z_sz = get_file_size(os.path.join(self.logic.zipped_dir, zip_name))
        h_sz = get_folder_size(os.path.join(self.logic.installed_dir, name)) if is_installed else 0
        dp.lbl_size.config(text=f"Zip: {format_size(z_sz)} | HDD: {format_size(h_sz)}")

        self.current_images = self.logic.get_game_images(name)
        self.current_img_index = 0
        self.update_image_display()

    def save_notes(self):
        sel = self.tree.selection()
        if not sel: return
        name = os.path.splitext(sel[0])[0]
        text = self.detail_panel.txt_notes.get(1.0, tk.END).strip()
        self.logic.save_meta(name, ".notes", text)

    def backup_save(self):
        sel = self.tree.selection()
        if not sel: return
        ok, msg = self.logic.backup_game_saves(sel[0])
        if ok: messagebox.showinfo("Backup Successful", msg)
        else: messagebox.showerror("Backup Failed", msg)

    def update_image_display(self):
        dp = self.detail_panel
        if not HAS_PILLOW or not self.current_images:
            dp.lbl_img.config(image='', text="No Image")
            dp.lbl_img.image = None
            dp.lbl_img_info.config(text="")
            return
        
        if self.current_img_index >= len(self.current_images):
            self.current_img_index = 0
        
        path = self.current_images[self.current_img_index]
        try:
            img = Image.open(path).resize((512, 384), Image.Resampling.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            dp.lbl_img.config(image=ph, text=""); dp.lbl_img.image = ph
            
            info_text = f"Image {self.current_img_index + 1} of {len(self.current_images)}" if len(self.current_images) > 1 else ""
            dp.lbl_img_info.config(text=info_text)
        except Exception as e: 
            dp.lbl_img.config(image='', text="Error Displaying Image")
            print(f"Error updating image: {e}")

    def next_image(self):
        if len(self.current_images) > 1:
            self.current_img_index = (self.current_img_index + 1) % len(self.current_images)
            self.update_image_display()

    def clear_preview(self):
        dp = self.detail_panel
        dp.lbl_title.config(text="Select Game")
        dp.lbl_img.config(image='', text="No Image")
        dp.btn_play.config(state=tk.DISABLED)
        dp.btn_install.config(state=tk.DISABLED)
        dp.lbl_size.config(text="")
        dp.lbl_img_info.config(text="")
        dp.txt_desc.config(state=tk.NORMAL); dp.txt_desc.delete(1.0, tk.END); dp.txt_desc.config(state=tk.DISABLED)
        dp.txt_notes.delete(1.0, tk.END)
        dp.lbl_sheet.config(text="")
        self.current_images = []

    def _get_selected_zip(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def on_play(self):
        zip_name = self._get_selected_zip()
        if zip_name:
            try: self.logic.launch_game(zip_name)
            except Exception as e: messagebox.showerror("Error", str(e))
            
    def on_install(self):
        zip_name = self._get_selected_zip()
        if zip_name:
            try: 
                self.logic.install_game(zip_name)
                self.refresh_library()
            except Exception as e: messagebox.showerror("Error", str(e))

    def on_uninstall(self):
        zip_name = self._get_selected_zip()
        if zip_name and messagebox.askyesno("Confirm", "Uninstall game?"):
            self.logic.uninstall_game(zip_name)
            self.refresh_library()

    def on_double_click(self):
        zip_name = self._get_selected_zip()
        if not zip_name: return
        tags = self.tree.item(zip_name, 'tags')
        if 'installed' in tags:
            self.on_play()
        else: 
            self.on_install()
    
    def _move_selection(self, direction):
        zip_name = self._get_selected_zip()
        if not zip_name: return
        items = self.tree.get_children()
        if not items: return
        idx = items.index(zip_name)
        new_idx = (idx + direction) % len(items)
        new_item = items[new_idx]
        self.tree.selection_set(new_item)
        self.tree.see(new_item)

    def select_prev(self): self._move_selection(-1)
    def select_next(self): self._move_selection(1)
        
    def toggle_list(self):
        h = self.winfo_height()
        panel = self.library_panel
        if self.playlist_visible:
            panel.grid_remove()
            self.update_idletasks()
            self.minsize(550, 600)
            self.geometry(f"555x{h}")
            self.columnconfigure(0, weight=1)
            self.columnconfigure(1, weight=0)
            self.detail_panel.btn_list.configure(bootstyle="secondary")
        else:
            self.geometry(f"1350x{h}")
            self.columnconfigure(0, weight=0)
            self.columnconfigure(1, weight=1)
            panel.grid()
            self.minsize(600, 768)
            self.detail_panel.btn_list.configure(bootstyle="secondary-outline")
        self.playlist_visible = not self.playlist_visible

    def restart_program(self):
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def open_settings(self):
        if self.win_settings and self.win_settings.winfo_exists():
            self.win_settings.lift()
        else:
            self.win_settings = SettingsWindow(self)

    def open_edit_window(self):
        zip_name = self._get_selected_zip()
        if not zip_name: return
        
        if self.win_edit and self.win_edit.winfo_exists():
            self.win_edit.lift()
        else:
            self.win_edit = EditWindow(self, zip_name)

    def show_tree_context(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id: return
        self.tree.selection_set(item_id)
        
        is_inst = 'installed' in self.tree.item(item_id, 'tags')
        name = os.path.splitext(item_id)[0]
        
        menu = tb.Menu(self, tearoff=0)
        menu.add_command(label="✎ Configuration", command=self.open_edit_window)
        
        is_fav = self.logic.is_favorite(name)
        fav_label = f"💔 Unfavorite" if is_fav else f"★ Favorite"
        menu.add_command(label=fav_label, command=lambda n=name: self.toggle_fav_from_context(n))
        menu.add_separator()

        if is_inst:
            exe_map = self.logic.load_exe_map(name)
            # Main 'Play' command
            main_exe = next((exe for exe, info in exe_map.items() if info.get("role") == ROLE_MAIN), None)
            if main_exe:
                 menu.add_command(label="▶ Play Game", command=self.on_play)

            # Setup command
            setup_exe = next((exe for exe, info in exe_map.items() if info.get("role") == ROLE_SETUP), None)
            if setup_exe:
                 menu.add_command(label="⚙ Setup Game", command=lambda i=item_id, x=setup_exe: self.logic.launch_game(i, x))
            
            # Custom commands submenu
            custom_items = [(info.get("title", os.path.basename(exe)), exe) for exe, info in exe_map.items() if info.get("role") == ROLE_CUSTOM]
            if custom_items:
                sub_custom = tb.Menu(menu, tearoff=0)
                for title, exe in custom_items:
                    sub_custom.add_command(label=title, command=lambda i=item_id, x=exe: self.logic.launch_game(i, x))
                menu.add_cascade(label="📂 Other / Addons", menu=sub_custom)

            menu.add_separator()
            menu.add_command(label="💾 Backup Save", command=self.backup_save)
            menu.add_separator()
            menu.add_command(label="📝 Edit Config (Notepad)", command=lambda i=item_id: self.logic.open_config_in_notepad(i))
            menu.add_command(label="✨ Standardize Structure", command=lambda i=item_id: self.open_organize_dialog(i))
            menu.add_command(label="💻 Run DOSBox (CMD)", command=lambda i=item_id: self.logic.launch_dosbox_prompt(i))
            
            # Run specific EXE submenu
            all_exes = self.logic.scan_game_executables(item_id)
            if all_exes:
                sub_all = tb.Menu(menu, tearoff=0)
                for exe in all_exes:
                    sub_all.add_command(label=exe, command=lambda i=item_id, x=exe: self.logic.launch_game(i, x))
                menu.add_cascade(label="🚀 Run Specific EXE", menu=sub_all)

            menu.add_separator()
            menu.add_command(label="Uninstall", command=self.on_uninstall)
        else:
            menu.add_command(label="Install", command=self.on_install)
        
        menu.add_separator()
        rate_menu = tb.Menu(menu, tearoff=0)
        for i in range(1, 6):
            rate_menu.add_command(label=f"{'★' * i}", command=lambda r=i: self.set_rating(item_id, r))
        menu.add_cascade(label="Rate", menu=rate_menu)
        menu.post(event.x_root, event.y_root)

    def toggle_fav_from_context(self, name):
        self.logic.toggle_favorite(name)
        self.refresh_library()

    def set_rating(self, item_id, rating):
        name = os.path.splitext(item_id)[0]
        self.logic.save_meta(name, ".rating", rating)
        self.refresh_library()

    def show_img_context(self, event):
        menu = tb.Menu(self, tearoff=0)
        menu.add_command(label="Paste (Ctrl+V)", command=self.paste_screenshot)
        menu.add_command(label="Delete Current Image", command=self.del_screenshot)
        menu.post(event.x_root, event.y_root)

    def paste_screenshot(self, event=None):
        if not HAS_PILLOW: return
        zip_name = self._get_selected_zip()
        if not zip_name: return
        name = os.path.splitext(zip_name)[0]
        try:
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                new_path = self.logic.save_screenshot_from_clipboard(name, img)
                self.on_select(None) # Refresh details
        except Exception as e:
            print(f"Paste screenshot failed: {e}")

    def del_screenshot(self):
        if not self.current_images: return
        if not messagebox.askyesno("Confirm", "Delete this screenshot?"): return
        try:
            current_path = self.current_images[self.current_img_index]
            os.remove(current_path)
            self.on_select(None) # Refresh details
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete image: {e}")

    def open_organize_dialog(self, zip_name):
        current_name = os.path.splitext(zip_name)[0]
        new_full_name = simpledialog.askstring("Standardize Structure - Step 1/2", 
            "Enter Full Game Name (Main Folder):\nThis will rename the game in the list.",
            initialvalue=current_name)
        if not new_full_name: return 
        new_full_name = new_full_name.strip()
        
        # Logic to suggest a DOS-compatible name
        dos_name_suggestion = re.sub(r'[^a-zA-Z0-9]', '', new_full_name)[:8].upper()
        dos_name = simpledialog.askstring("Standardize Structure - Step 2/2", 
            f"Enter 8-char MS-DOS name for inner folder:\n(Files will be moved to drives/c/DOSNAME)",
            initialvalue=dos_name_suggestion)
        if not dos_name: return

        dos_name = re.sub(r'[^a-zA-Z0-9]', '', dos_name)[:8].upper()
        try:
            new_zip = self.logic.organize_game_structure(zip_name, new_full_name, dos_name)
            self.refresh_library()
            if self.tree.exists(new_zip):
                self.tree.selection_set(new_zip)
                self.tree.see(new_zip)
            messagebox.showinfo("Success", f"Game organized.\nMain Folder: {new_full_name}\nDOS Path: C:\\{dos_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to organize game folder: {e}")