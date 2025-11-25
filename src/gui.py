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

if HAS_PILLOW:
    from PIL import Image, ImageTk, ImageGrab

class DOSManagerApp(tb.Window):
    def __init__(self):
        # 1. Načítanie nastavení
        self.tmp_settings = SettingsManager()
        
        # 2. Inicializácia témy
        theme = self.tmp_settings.get("theme")
        if not theme: theme = "darkly"
        
        super().__init__(themename=theme)
        self.title("DOS Game Manager")
        self.geometry("1350x950")
        
        # 3. Načítanie externých tém
        self.load_custom_themes()

        self.settings = self.tmp_settings
        self.logic = GameLogic(self.settings)
        
        # Singleton Windows references
        self.win_settings = None
        self.win_edit = None
        
        self.playlist_visible = True
        
        self.current_images = []
        self.current_img_index = 0

        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search_change)
        
        self.fav_only_var = tk.BooleanVar(value=False)
        self.sort_col = "name"
        self.sort_desc = False

        self.init_ui()
        self.minsize(600, 768)

        if os.path.exists(self.settings.get("root_dir")):
            self.refresh_library()
        else:
            messagebox.showinfo("Welcome", "Please configure Settings (DOSBox EXE & Folders).")

    def load_custom_themes(self):
        """Načíta .json témy z priečinka 'themes' v koreňovom adresári."""
        themes_dir = os.path.join(BASE_DIR, "themes")
        if os.path.exists(themes_dir):
            for f in os.listdir(themes_dir):
                if f.endswith(".json"):
                    try:
                        full_path = os.path.join(themes_dir, f)
                        self.style.load_user_themes(full_path)
                        print(f"Loaded custom theme: {f}")
                    except Exception as e:
                        print(f"Failed to load theme {f}: {e}")

    def init_ui(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self.build_left_panel()
        self.build_right_panel()

    def build_left_panel(self):
        self.frame_left = tb.Frame(self)
        self.frame_left.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.frame_left.rowconfigure(5, weight=1) 

        # IMAGE
        f_img = tk.Frame(self.frame_left, bg="black", bd=2, relief=tk.SUNKEN, width=512, height=384)
        f_img.pack(pady=(0, 5)); f_img.pack_propagate(False)
        self.lbl_img = tk.Label(f_img, text="No Image", bg="black", fg="gray")
        self.lbl_img.pack(expand=True, fill=tk.BOTH)
        self.lbl_img.bind("<Button-1>", self.next_image)
        self.lbl_img.bind("<Button-3>", self.show_img_context)
        
        self.lbl_img_info = tb.Label(self.frame_left, text="", font=("Segoe UI", 8), bootstyle="secondary")
        self.lbl_img_info.pack(pady=(0, 10))

        # TITLE & META
        f_meta = tb.Frame(self.frame_left, width=512, height=60)
        f_meta.pack(pady=5); f_meta.pack_propagate(False)
        self.lbl_title = tb.Label(f_meta, text="Select Game", font=("Segoe UI", 18, "bold"), bootstyle="inverse-dark")
        self.lbl_title.pack(pady=(0, 2))
        f_det = tb.Frame(f_meta)
        f_det.pack()
        self.lbl_year = tb.Label(f_det, text="", bootstyle="secondary"); self.lbl_year.pack(side=tk.LEFT, padx=10)
        self.lbl_comp = tb.Label(f_det, text="", bootstyle="secondary"); self.lbl_comp.pack(side=tk.LEFT)

        # CONTROLS
        f_ctrl = tb.Frame(self.frame_left)
        f_ctrl.pack(pady=15)
        tb.Button(f_ctrl, text="⏮", command=self.select_prev, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=5)
        self.btn_play = tb.Button(f_ctrl, text="▶ PLAY", command=self.on_play, bootstyle="success", width=10, state=tk.DISABLED)
        self.btn_play.pack(side=tk.LEFT, padx=5)
        self.btn_install = tb.Button(f_ctrl, text="📥 Install", command=self.on_install, bootstyle="primary", width=10)
        self.btn_install.pack(side=tk.LEFT, padx=5)
        self.btn_uninstall = tb.Button(f_ctrl, text="🗑", command=self.on_uninstall, bootstyle="danger-outline", state=tk.DISABLED, width=3)
        self.btn_uninstall.pack(side=tk.LEFT, padx=5)
        tb.Button(f_ctrl, text="⏭", command=self.select_next, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=5)

        # TOOLS
        f_tools = tb.Frame(self.frame_left)
        f_tools.pack(pady=5)
        self.btn_edit = tb.Button(f_tools, text="✎ Configuration", command=self.open_edit_window, bootstyle="warning", width=15, state=tk.DISABLED)
        self.btn_edit.pack(side=tk.LEFT, padx=5)
        self.btn_list = tb.Button(f_tools, text="☰ List", command=self.toggle_list, bootstyle="secondary-outline", width=6)
        self.btn_list.pack(side=tk.LEFT, padx=5)
        self.btn_backup = tb.Button(f_tools, text="💾 Backup Save", command=self.backup_save, bootstyle="info-outline", width=15, state=tk.DISABLED)
        self.btn_backup.pack(side=tk.LEFT, padx=5)

        # Stats
        self.f_stats = tb.Frame(self.frame_left, width=512)
        self.f_stats.pack(fill=tk.X, pady=(15, 5))
        self.lbl_rating = tb.Label(self.f_stats, text="", font=("Segoe UI", 16), bootstyle="warning")
        self.lbl_rating.pack(side=tk.LEFT, padx=10)
        self.lbl_size = tb.Label(self.f_stats, text="", bootstyle="secondary")
        self.lbl_size.pack(side=tk.RIGHT, padx=10)

        # TABS: INFO / NOTES / SHORTCUTS
        self.tabs_info = tb.Notebook(self.frame_left)
        self.tabs_info.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Tab 1: Desc
        self.tab_desc = tb.Frame(self.tabs_info)
        self.tabs_info.add(self.tab_desc, text="Info")
        scr_desc = tb.Scrollbar(self.tab_desc, orient="vertical")
        self.txt_desc = tk.Text(self.tab_desc, bg="#2b2b2b", fg="#ddd", wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10, yscrollcommand=scr_desc.set)
        scr_desc.config(command=self.txt_desc.yview)
        scr_desc.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_desc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Tab 2: Notes
        self.tab_notes = tb.Frame(self.tabs_info)
        self.tabs_info.add(self.tab_notes, text="Notes")
        scr_notes = tb.Scrollbar(self.tab_notes, orient="vertical")
        self.txt_notes = tk.Text(self.tab_notes, bg="#333333", fg="#fff", wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10, yscrollcommand=scr_notes.set)
        scr_notes.config(command=self.txt_notes.yview)
        scr_notes.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_notes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.txt_notes.bind("<KeyRelease>", self.save_notes)
        
        # Tab 3: Shortcuts
        self.tab_sheet = tb.Frame(self.tabs_info)
        self.tabs_info.add(self.tab_sheet, text="Shortcuts")
        self.lbl_sheet = tk.Label(self.tab_sheet, text="", justify=tk.LEFT, font=("Consolas", 9), anchor="nw", bg="#222", fg="#0f0")
        self.lbl_sheet.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def build_right_panel(self):
        self.frame_right = tb.Frame(self)
        self.frame_right.grid(row=0, column=1, sticky="nsew", padx=(0, 15), pady=15)
        
        tb.Label(self.frame_right, text="Game Library", font=("Segoe UI", 14, "bold"), bootstyle="primary").pack(fill=tk.X)
        
        f_search = tb.Frame(self.frame_right)
        f_search.pack(fill=tk.X, pady=10)
        tb.Label(f_search, text="🔍").pack(side=tk.LEFT, padx=5)
        tb.Entry(f_search, textvariable=self.search_var, bootstyle="dark").pack(side=tk.LEFT, fill=tk.X, expand=True)
        tb.Checkbutton(f_search, text=f"{HEART_SYMBOL} Only", variable=self.fav_only_var, command=self.refresh_library, bootstyle="danger-round-toggle").pack(side=tk.LEFT, padx=10)

        f_bot = tb.Frame(self.frame_right)
        f_bot.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        tb.Button(f_bot, text="⚙ Settings", command=self.open_settings, bootstyle="secondary").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tb.Button(f_bot, text="↻ Refresh", command=self.refresh_library, bootstyle="secondary").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        f_tree_container = tb.Frame(self.frame_right)
        f_tree_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cols = ("name", "genre", "year", "company", "rating", "zip", "hdd")
        self.tree = tb.Treeview(f_tree_container, columns=cols, show="headings", selectmode="browse", bootstyle="dark")
        
        for col in cols:
            self.tree.heading(col, text=col.title(), command=lambda c=col: self.sort_tree(c))
        
        self.tree.column("name", width=220)
        self.tree.column("genre", width=100)
        self.tree.column("year", width=60, anchor="center")
        self.tree.column("company", width=120)
        self.tree.column("rating", width=90, anchor="center")
        self.tree.column("zip", width=70, anchor="center")
        self.tree.column("hdd", width=70, anchor="center")
        
        sc_y = tb.Scrollbar(f_tree_container, orient="vertical", command=self.tree.yview)
        sc_x = tb.Scrollbar(f_tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)
        sc_y.pack(side=tk.RIGHT, fill=tk.Y)
        sc_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.tag_configure('installed', foreground='#00bc8c')
        self.tree.tag_configure('zipped', foreground='#adb5bd')
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.show_tree_context)
        self.bind('<Control-v>', self.paste_screenshot)

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
            
            prefix = ICON_READY if is_inst else ICON_WAITING
            disp = f"{prefix} {name_no_zip}"
            if is_fav: disp += f" {HEART_SYMBOL}"
            
            tag = 'installed' if is_inst else 'zipped'
            row = (disp, g, y, c, STAR_SYMBOL*r, format_size(z_sz), format_size(h_sz), zip_name, tag, r, z_sz, h_sz)
            data_rows.append(row)
            
        def sort_key(item):
            if self.sort_col == "name": 
                raw_name = item[7]
                clean_name = os.path.splitext(raw_name)[0]
                return clean_name.lower()
            if self.sort_col == "year": return item[2]
            if self.sort_col == "genre": return item[1].lower()
            if self.sort_col == "company": return item[3].lower()
            if self.sort_col == "rating": return item[9]
            if self.sort_col == "zip": return item[10]
            if self.sort_col == "hdd": return item[11]
            return os.path.splitext(item[7])[0].lower()

        data_rows.sort(key=sort_key, reverse=self.sort_desc)

        for row in data_rows:
            self.tree.insert("", "end", iid=row[7], values=row[0:7], tags=(row[8],))
            
        if save_id: 
            try: self.tree.selection_set(save_id); self.tree.see(save_id); self.on_select(None)
            except: pass
        elif data_rows:
            fid = data_rows[0][7]
            self.tree.selection_set(fid); self.on_select(None)
        else: self.clear_preview()

    def on_search_change(self, *args): self.refresh_library()

    def on_select(self, event):
        sel = self.tree.selection()
        if not sel: self.clear_preview(); return
        zip_name = sel[0]
        name = os.path.splitext(zip_name)[0]
        tags = self.tree.item(zip_name, 'tags')
        is_installed = 'installed' in tags
        
        self.btn_edit.configure(state=tk.NORMAL)
        if is_installed:
            self.btn_install.configure(state=tk.DISABLED, bootstyle="secondary")
            self.btn_play.configure(state=tk.NORMAL, bootstyle="success")
            self.btn_uninstall.configure(state=tk.NORMAL, bootstyle="danger-outline")
            self.btn_backup.configure(state=tk.NORMAL, bootstyle="info-outline")
            isos = self.logic.get_mounted_isos(name)
            iso_txt = "\n".join([f"• D:\\ {iso}" for iso in isos]) if isos else "None"
            sheet_text = f"GAME: {name}\n\n[ DOSBox Shortcuts ]\nCtrl+F12  : Speed Up\nCtrl+F11  : Slow Down\nCtrl+F4   : Swap CD/Refresh\nAlt+Enter : Fullscreen\nCtrl+F5   : Screenshot\nCtrl+F10  : Unlock Mouse\n\n[ Mounted ISOs ]\n{iso_txt}"
            self.lbl_sheet.config(text=sheet_text)
        else:
            self.btn_install.configure(state=tk.NORMAL, bootstyle="primary")
            self.btn_play.configure(state=tk.DISABLED, bootstyle="secondary")
            self.btn_uninstall.configure(state=tk.DISABLED, bootstyle="secondary")
            self.btn_backup.configure(state=tk.DISABLED, bootstyle="secondary")
            self.lbl_sheet.config(text="Install game to see details.")

        title_text = truncate_text(name.replace("_"," ").title(), 30)
        if self.logic.is_favorite(name): title_text += f" {HEART_SYMBOL}"
        self.lbl_title.config(text=title_text)
        
        y = self.logic.load_meta(name, ".year")
        c = self.logic.load_meta(name, ".company")
        g = self.logic.load_meta(name, ".genre")
        txt_meta = ""
        if g: txt_meta += f"[{g}] "
        if y: txt_meta += f"Year: {y} "
        if c: txt_meta += f"| Dev: {truncate_text(c, 20)}"
        self.lbl_year.config(text=txt_meta)
        self.lbl_comp.config(text="") 

        r = self.logic.load_rating(name)
        self.lbl_rating.config(text=STAR_SYMBOL * r)
        
        desc = self.logic.load_meta(name, ".txt")
        self.txt_desc.config(state=tk.NORMAL); self.txt_desc.delete(1.0, tk.END)
        self.txt_desc.insert(tk.END, desc if desc else "No description."); self.txt_desc.config(state=tk.DISABLED)

        notes = self.logic.load_meta(name, ".notes")
        self.txt_notes.delete(1.0, tk.END)
        self.txt_notes.insert(tk.END, notes)

        z_sz = get_file_size(os.path.join(self.logic.zipped_dir, zip_name))
        h_sz = 0
        if is_installed: h_sz = get_folder_size(os.path.join(self.logic.installed_dir, name))
        self.lbl_size.config(text=f"Zip: {format_size(z_sz)} | HDD: {format_size(h_sz)}")

        self.current_images = self.logic.get_game_images(name)
        self.current_img_index = 0
        self.update_image_display()

    def save_notes(self, event=None):
        sel = self.tree.selection()
        if not sel: return
        name = os.path.splitext(sel[0])[0]
        text = self.txt_notes.get(1.0, tk.END).strip()
        self.logic.save_meta(name, ".notes", text)

    def backup_save(self):
        sel = self.tree.selection()
        if not sel: return
        ok, msg = self.logic.backup_game_saves(sel[0])
        if ok: messagebox.showinfo("Backup Successful", msg)
        else: messagebox.showerror("Backup Failed", msg)

    def update_image_display(self):
        if not HAS_PILLOW or not self.current_images:
            self.lbl_img.config(image='', text="No Image")
            self.lbl_img.image = None
            self.lbl_img_info.config(text="")
            return
        if self.current_img_index >= len(self.current_images):
            self.current_img_index = 0
        path = self.current_images[self.current_img_index]
        try:
            img = Image.open(path).resize((512, 384), Image.Resampling.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            self.lbl_img.config(image=ph, text=""); self.lbl_img.image = ph
            if len(self.current_images) > 1:
                self.lbl_img_info.config(text=f"Image {self.current_img_index + 1} of {len(self.current_images)}")
            else:
                self.lbl_img_info.config(text="")
        except: 
            self.lbl_img.config(image='', text="Error")

    def next_image(self, event=None):
        if len(self.current_images) > 1:
            self.current_img_index = (self.current_img_index + 1) % len(self.current_images)
            self.update_image_display()

    def clear_preview(self):
        self.lbl_title.config(text="Select Game"); self.lbl_img.config(image='', text="No Image")
        self.btn_play.config(state=tk.DISABLED); self.btn_install.config(state=tk.DISABLED)
        self.lbl_size.config(text="")
        self.lbl_img_info.config(text="")
        self.current_images = []

    def on_play(self):
        sel = self.tree.selection()
        if sel:
            try: self.logic.launch_game(sel[0])
            except Exception as e: messagebox.showerror("Error", str(e))
    def on_install(self):
        sel = self.tree.selection()
        if sel:
            try: 
                self.logic.install_game(sel[0])
                self.refresh_library()
            except Exception as e: messagebox.showerror("Error", str(e))
    def on_uninstall(self):
        sel = self.tree.selection()
        if sel and messagebox.askyesno("Confirm", "Uninstall game?"):
            self.logic.uninstall_game(sel[0])
            self.refresh_library()
    def on_double_click(self, event):
        sel = self.tree.selection()
        if not sel: return
        tags = self.tree.item(sel[0], 'tags')
        if 'installed' in tags: self.on_play()
        else: 
            self.on_install()
            if 'installed' in self.tree.item(sel[0], 'tags'): self.on_play()
    def select_prev(self):
        sel = self.tree.selection()
        if not sel: return
        items = self.tree.get_children()
        idx = (items.index(sel[0]) - 1) % len(items)
        self.tree.selection_set(items[idx]); self.tree.see(items[idx])
    def select_next(self):
        sel = self.tree.selection()
        if not sel: return
        items = self.tree.get_children()
        idx = (items.index(sel[0]) + 1) % len(items)
        self.tree.selection_set(items[idx]); self.tree.see(items[idx])
        
    def toggle_list(self):
        h = self.winfo_height()
        if self.playlist_visible:
            self.frame_right.grid_remove()
            self.update_idletasks()
            self.minsize(550, 600)
            self.geometry(f"555x{h}")
            self.columnconfigure(0, weight=1)
            self.columnconfigure(1, weight=0)
            self.btn_list.configure(bootstyle="secondary")
        else:
            self.geometry(f"1350x{h}")
            self.columnconfigure(0, weight=0)
            self.columnconfigure(1, weight=1)
            self.frame_right.grid()
            self.minsize(600, 768)
            self.btn_list.configure(bootstyle="secondary-outline")
        self.playlist_visible = not self.playlist_visible

    def restart_program(self):
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def open_settings(self):
        if self.win_settings and self.win_settings.winfo_exists():
            self.win_settings.lift()
            return
        self.win_settings = SettingsWindow(self)

    def open_edit_window(self):
        sel = self.tree.selection()
        if not sel: return
        
        if self.win_edit and self.win_edit.winfo_exists():
            self.win_edit.lift()
            return
        
        zip_name = sel[0]
        self.win_edit = EditWindow(self, zip_name)


    def show_tree_context(self, event):
        item = self.tree.identify_row(event.y)
        if not item: return
        self.tree.selection_set(item)
        tags = self.tree.item(item, 'tags')
        is_inst = 'installed' in tags
        name = os.path.splitext(item)[0]
        
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="✎ Configuration", command=self.open_edit_window)
        
        is_fav = self.logic.is_favorite(name)
        fav_label = f"💔 Remove from Favorites" if is_fav else f"{HEART_SYMBOL} Add to Favorites"
        menu.add_command(label=fav_label, command=lambda: self.toggle_fav_from_context(name))
        menu.add_separator()

        if is_inst:
            exe_map = self.logic.load_exe_map(name)
            for exe, info in exe_map.items():
                if info.get("role") == ROLE_MAIN:
                    menu.add_command(label="▶ Play Game", command=self.on_play)
                    break
            
            for exe, info in exe_map.items():
                if info.get("role") == ROLE_SETUP:
                     menu.add_command(label="⚙ Setup Game", command=lambda x=exe: self.logic.launch_game(item, x))

            custom_items = []
            for exe, info in exe_map.items():
                if info.get("role") == ROLE_CUSTOM:
                    title = info.get("title", "Custom")
                    if not title: title = os.path.basename(exe)
                    custom_items.append((title, exe))
            
            if custom_items:
                sub_custom = tk.Menu(menu, tearoff=0)
                for title, exe in custom_items:
                    sub_custom.add_command(label=title, command=lambda x=exe: self.logic.launch_game(item, x))
                menu.add_cascade(label="📂 Other / Addons / Utils", menu=sub_custom)

            menu.add_separator()
            menu.add_command(label="💾 Backup Save", command=self.backup_save)
            menu.add_separator()
            menu.add_command(label="📝 Edit Config (Notepad)", command=lambda: self.logic.open_config_in_notepad(item))
            menu.add_command(label="✨ Standardize Structure", command=lambda: self.open_organize_dialog(item))
            menu.add_command(label="💻 Run DOSBox (CMD)", command=lambda: self.logic.launch_dosbox_prompt(item))
            
            sub_all = tk.Menu(menu, tearoff=0)
            all_exes = self.logic.scan_game_executables(item)
            for exe in all_exes:
                sub_all.add_command(label=exe, command=lambda x=exe: self.logic.launch_game(item, x))
            menu.add_cascade(label="🚀 Run Specific EXE", menu=sub_all)

            menu.add_separator()
            menu.add_command(label="Uninstall", command=self.on_uninstall)
        else:
            menu.add_command(label="Install", command=self.on_install)
        
        menu.add_separator()
        rate_menu = tk.Menu(menu, tearoff=0)
        for i in range(1, 6):
            rate_menu.add_command(label=f"{i} Stars", command=lambda x=i: self.set_rating(item, x))
        menu.add_cascade(label="Rate", menu=rate_menu)
        menu.post(event.x_root, event.y_root)

    def toggle_fav_from_context(self, name):
        self.logic.toggle_favorite(name)
        self.refresh_library()
    def set_rating(self, item, r):
        name = os.path.splitext(item)[0]
        self.logic.save_meta(name, ".rating", r)
        self.refresh_library()
    def show_img_context(self, event):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Paste (Ctrl+V)", command=self.paste_screenshot)
        menu.add_command(label="Delete Current Image", command=self.del_screenshot)
        menu.post(event.x_root, event.y_root)
    def paste_screenshot(self, event=None):
        if not HAS_PILLOW: return
        sel = self.tree.selection()
        if not sel: return
        name = os.path.splitext(sel[0])[0]
        try:
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                target_dir = self.logic.get_screens_dir(name)
                new_name = self.logic.get_next_screenshot_name(name)
                img.save(os.path.join(target_dir, new_name))
                self.on_select(None)
        except: pass
    def del_screenshot(self):
        if not self.current_images: return
        if not messagebox.askyesno("Confirm", "Delete this screenshot?"): return
        try:
            current_path = self.current_images[self.current_img_index]
            os.remove(current_path)
            self.on_select(None)
        except: pass
    def open_organize_dialog(self, zip_name):
        current_name = os.path.splitext(zip_name)[0]
        new_full_name = simpledialog.askstring("Standardize Structure - Step 1/2", 
            "Enter Full Game Name (Main Folder):\nThis will rename the game in the list.",
            initialvalue=current_name)
        if not new_full_name: return 
        new_full_name = new_full_name.strip()
        dos_name = None
        temp_folder_check = self.logic.find_game_folder(zip_name)
        items_in_root = [f for f in os.listdir(temp_folder_check) if f not in ['cd', 'docs', 'drives', 'dosbox.conf', 'capture', 'screens']]
        if len(items_in_root) == 1 and os.path.isdir(os.path.join(temp_folder_check, items_in_root[0])):
            candidate = items_in_root[0]
            if len(candidate) <= 8 and " " not in candidate: dos_name = candidate.upper()
        if not dos_name:
            default_dos = re.sub(r'[^a-zA-Z0-9]', '', new_full_name)[:8].upper()
            dos_name = simpledialog.askstring("Standardize Structure - Step 2/2", 
                f"Enter 8-char MS-DOS name for inner folder:\n(Files will be moved to drives/c/DOSNAME)",
                initialvalue=default_dos)
        if dos_name:
            dos_name = re.sub(r'[^a-zA-Z0-9]', '', dos_name)[:8].upper()
            new_zip = self.logic.organize_game_structure(zip_name, new_full_name, dos_name)
            if new_zip:
                self.refresh_library()
                if new_zip in self.tree.get_children(): self.tree.selection_set(new_zip); self.tree.see(new_zip)
                messagebox.showinfo("Success", f"Game organized.\nMain Folder: {new_full_name}\nDOS Path: C:\\{dos_name}")
            else: messagebox.showerror("Error", "Failed to organize game folder.")