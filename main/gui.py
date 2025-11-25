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

# Imports from our modules
from constants import *
from utils import format_size, truncate_text, get_folder_size, get_file_size
from settings import SettingsManager
from logic import GameLogic, HAS_PILLOW

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
            sheet_text = f"GAME: {name}\n\n[ DOSBox Shortcuts ]\nCtrl+F12  : Speed Up\nCtrl+F11  : Slow Down\nCtrl+F4   : Swap CD/Refresh\nAlt+Enter : Fullscreen\nCtrl+F5   : Screenshot\nCtrl+F10  : Capture Mouse\n\n[ Mounted CDs ]\n{iso_txt}"
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
            
        top = tb.Toplevel(self); top.title("Settings"); top.geometry("600x650")
        self.win_settings = top
        
        # --- PREMENNÉ ---
        v_root = tk.StringVar(value=self.settings.get("root_dir"))
        v_zip = tk.StringVar(value=self.settings.get("zip_dir"))
        v_exe = tk.StringVar(value=self.settings.get("dosbox_exe"))
        v_conf = tk.StringVar(value=self.settings.get("global_conf"))
        v_capture = tk.StringVar(value=self.settings.get("capture_dir"))
        v_theme = tk.StringVar(value=self.settings.get("theme"))

        # --- TABS ---
        tabs = tb.Notebook(top)
        tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tab_gen = tb.Frame(tabs)
        tab_app = tb.Frame(tabs)
        tabs.add(tab_gen, text="System & Paths")
        tabs.add(tab_app, text="Appearance & Themes")
        
        # --- TAB 1: SYSTEM ---
        def browse_path(var, is_file=False):
            if is_file: p = filedialog.askopenfilename(filetypes=[("Executable/Config", "*.*")], parent=top)
            else: p = filedialog.askdirectory(parent=top)
            if p: var.set(self.settings._make_relative(p))
            
        pad = 5
        def create_row(parent, label, var, cmd=None, placeholder=None):
            f = tb.Frame(parent); f.pack(fill=tk.X, padx=10, pady=pad)
            tb.Label(f, text=label, bootstyle="inverse-dark").pack(anchor="w")
            row_inner = tb.Frame(f); row_inner.pack(fill=tk.X, expand=True)
            ent = tb.Entry(row_inner, textvariable=var)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
            if cmd: tb.Button(row_inner, text="...", command=cmd, bootstyle="outline").pack(side=tk.RIGHT, padx=(5,0))
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

        v_root.trace("w", check_portability); v_exe.trace("w", check_portability)
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
            if os.name == 'nt': os.startfile(themes_dir)
            else: subprocess.call(['xdg-open', themes_dir])
            
        tb.Button(tab_app, text="📂 Open Themes Folder", command=open_themes_folder, bootstyle="info-outline").pack(fill=tk.X, padx=10)
        
        # --- THEME CREATOR LOGIC ---
        # Skontrolujeme, ci je 'ttkcreator' dostupny
        creator_installed = importlib.util.find_spec("ttkcreator") is not None
        
        f_creator = tb.Frame(tab_app)
        f_creator.pack(fill=tk.X, padx=10, pady=20)
        tb.Label(f_creator, text="Theme Creator Tool:", bootstyle="inverse-dark").pack(anchor="w")
        
        def run_installer():
            try:
                btn_install.configure(state="disabled", text="Installing... (Please wait)")
                top.update()
                # Volanie pip install ttkcreator
                subprocess.check_call([sys.executable, "-m", "pip", "install", "ttkcreator"])
                messagebox.showinfo("Success", "Theme Creator installed successfully!\nYou may launch it now.")
                # Update UI
                btn_install.pack_forget()
                btn_launch.pack(fill=tk.X, pady=5)
            except Exception as e:
                messagebox.showerror("Error", f"Installation failed: {e}")
                btn_install.configure(state="normal", text="📥 Install Theme Creator")

        def run_creator():
            try:
                # Volanie python -m ttkcreator v novom procese
                subprocess.Popen([sys.executable, "-m", "ttkcreator"])
            except Exception as e:
                messagebox.showerror("Error", f"Failed to launch: {e}")

        btn_install = tb.Button(f_creator, text="📥 Install Theme Creator (pip install ttkcreator)", command=run_installer, bootstyle="warning-outline")
        btn_launch = tb.Button(f_creator, text="🎨 Launch Theme Creator", command=run_creator, bootstyle="success-outline")

        if creator_installed:
            btn_launch.pack(fill=tk.X, pady=5)
        else:
            btn_install.pack(fill=tk.X, pady=5)
        
        info_txt = ("\nCreate a theme using the tool above, save the .json file\n"
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
                top.destroy()
                self.restart_program()
            else:
                self.refresh_library()
                top.destroy()

        tb.Button(top, text="Save Settings & Restart if needed", command=save, bootstyle="success").pack(pady=10, fill=tk.X, padx=10)

    def open_edit_window(self):
        sel = self.tree.selection()
        if not sel: return
        
        if self.win_edit and self.win_edit.winfo_exists():
            self.win_edit.lift()
            return

        zip_name = sel[0]
        name = os.path.splitext(zip_name)[0]
        game_folder = self.logic.find_game_folder(zip_name)
        conf_path = os.path.join(game_folder, "dosbox.conf")
        
        top = tb.Toplevel(self); top.title(f"Configuration: {name}"); top.geometry("900x750")
        self.win_edit = top
        
        tabs = tb.Notebook(top)
        tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tab_general = tb.Frame(tabs)
        tab_executables = tb.Frame(tabs)
        tab_dosbox = tb.Frame(tabs)
        tab_audio = tb.Frame(tabs)
        
        tabs.add(tab_general, text="General")
        tabs.add(tab_executables, text="Executables")
        tabs.add(tab_dosbox, text="DOSBox Settings")
        tabs.add(tab_audio, text="Audio Settings")
        
        # --- TAB 1: GENERAL ---
        v_name = tk.StringVar(value=name)
        v_year = tk.StringVar(value=self.logic.load_meta(name, ".year"))
        v_comp = tk.StringVar(value=self.logic.load_meta(name, ".company"))
        v_genre = tk.StringVar(value=self.logic.load_meta(name, ".genre"))
        v_custom_dosbox = tk.StringVar(value=self.logic.load_meta(name, ".dosbox"))

        pad = 5
        def open_browser_search():
            query = f"{v_name.get()} dos game info mobygames"
            url = f"https://www.google.com/search?q={query}"
            webbrowser.open(url)
        
        f_top = tb.Frame(tab_general)
        f_top.pack(fill=tk.X, padx=10, pady=(10,0))
        tb.Label(f_top, text="Game Title:").pack(side=tk.LEFT)
        tb.Button(f_top, text="🌐 Search Info", command=open_browser_search, bootstyle="info-outline", width=12).pack(side=tk.RIGHT)
        
        tb.Entry(tab_general, textvariable=v_name).pack(fill=tk.X, padx=10, pady=pad)
        
        tb.Label(tab_general, text="Genre:").pack(anchor="w", padx=10)
        cb_genre = tb.Combobox(tab_general, values=GENRE_OPTIONS, textvariable=v_genre)
        cb_genre.pack(fill=tk.X, padx=10, pady=pad)

        tb.Label(tab_general, text="Year:").pack(anchor="w", padx=10)
        tb.Entry(tab_general, textvariable=v_year).pack(fill=tk.X, padx=10, pady=pad)
        
        tb.Label(tab_general, text="Developer/Company:").pack(anchor="w", padx=10)
        tb.Entry(tab_general, textvariable=v_comp).pack(fill=tk.X, padx=10, pady=pad)
        
        tb.Label(tab_general, text="Custom DOSBox EXE:").pack(anchor="w", padx=10)
        f_db = tb.Frame(tab_general); f_db.pack(fill=tk.X, padx=10, pady=pad)
        tb.Entry(f_db, textvariable=v_custom_dosbox).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tb.Button(f_db, text="...", command=lambda: filedialog.askopenfilename(parent=top), bootstyle="secondary-outline").pack(side=tk.RIGHT, padx=(5,0))

        tb.Label(tab_general, text="Rating:").pack(anchor="w", padx=10)
        vals = ["0 Stars"] + [f"{i} Stars" for i in range(1,6)]
        cb = tb.Combobox(tab_general, values=vals, state="readonly"); cb.pack(fill=tk.X, padx=10, pady=pad)
        cb.current(self.logic.load_rating(name))
        
        tb.Label(tab_general, text="Description:").pack(anchor="w", padx=10)
        t_desc = tk.Text(tab_general, height=8); t_desc.pack(fill=tk.BOTH, padx=10, pady=pad, expand=True)
        t_desc.insert(tk.END, self.logic.load_meta(name, ".txt"))
        
        # --- TAB 2: EXECUTABLES ---
        tb.Label(tab_executables, text="Assign roles to found executables:", bootstyle="secondary").pack(anchor="w", padx=10, pady=10)
        
        exe_frame = tb.Frame(tab_executables)
        exe_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        current_map = self.logic.load_exe_map(name)
        found_exes = self.logic.scan_game_executables(zip_name)
        exe_widgets = [] 
        
        canvas = tk.Canvas(exe_frame)
        scrollbar = tb.Scrollbar(exe_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tb.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        role_options = list(ROLE_DISPLAY.values())
        tb.Label(scrollable_frame, text="File", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=5)
        tb.Label(scrollable_frame, text="Run", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, padx=5)
        tb.Label(scrollable_frame, text="Role", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=5)
        tb.Label(scrollable_frame, text="Custom Title", font=("Segoe UI", 9, "bold")).grid(row=0, column=3, sticky="w", padx=5)

        for i, exe in enumerate(found_exes):
            r = i + 1
            tb.Label(scrollable_frame, text=truncate_text(exe, 35)).grid(row=r, column=0, sticky="w", padx=5, pady=2)
            btn_run = tb.Button(scrollable_frame, text="▶", bootstyle="success-outline", width=2,
                                command=lambda x=exe: self.logic.launch_game(zip_name, x))
            btn_run.grid(row=r, column=1, padx=5)

            info = current_map.get(exe, None)
            if info is None:
                low = exe.lower()
                if any(x in low for x in ['setup', 'install', 'config', 'setsound', 'sound']): current_role = ROLE_SETUP
                else: current_role = ROLE_UNASSIGNED
                current_title = ""
            else:
                current_role = info.get("role", ROLE_UNASSIGNED)
                current_title = info.get("title", "")
            
            disp_role = ROLE_DISPLAY.get(current_role, ROLE_DISPLAY[ROLE_UNASSIGNED])
            var_role = tk.StringVar(value=disp_role)
            var_title = tk.StringVar(value=current_title)
            
            cb_role = tb.Combobox(scrollable_frame, values=role_options, textvariable=var_role, state="readonly", width=18)
            cb_role.grid(row=r, column=2, padx=5)
            ent_title = tb.Entry(scrollable_frame, textvariable=var_title, width=20)
            ent_title.grid(row=r, column=3, padx=5)
            
            def on_role_change(event=None, v_r=var_role, e_t=ent_title):
                if v_r.get() == ROLE_DISPLAY[ROLE_CUSTOM]: e_t.configure(state="normal")
                else: e_t.configure(state="disabled")
            cb_role.bind("<<ComboboxSelected>>", on_role_change)
            on_role_change()
            exe_widgets.append((exe, var_role, var_title))

        # --- HELPER FOR OPTIONS ---
        def add_opt(parent, row, col, label, opts, val, editable=False):
            tb.Label(parent, text=label).grid(row=row, column=col, sticky="e", padx=5, pady=5)
            var = tk.StringVar(value=val)
            st = "normal" if editable else "readonly"
            if opts: cb = tb.Combobox(parent, values=opts, textvariable=var, state=st, width=15); cb.grid(row=row, column=col+1, sticky="w", padx=5, pady=5)
            else: tb.Entry(parent, textvariable=var, width=15).grid(row=row, column=col+1, sticky="w", padx=5, pady=5)
            return var
        def add_bool(parent, txt, val_str):
            v = tk.BooleanVar(value=(str(val_str).lower() == "true"))
            tb.Checkbutton(parent, text=txt, variable=v, bootstyle="round-toggle").pack(side=tk.LEFT, padx=10)
            return v

        # --- TAB 3: DOSBOX SETTINGS ---
        val_core = self.logic.read_dosbox_param(conf_path, "cpu", "core") or "auto"
        val_cputype = self.logic.read_dosbox_param(conf_path, "cpu", "cputype") or "auto"
        val_cycles = self.logic.read_dosbox_param(conf_path, "cpu", "cpu_cycles")
        if not val_cycles: val_cycles = self.logic.read_dosbox_param(conf_path, "cpu", "cycles")
        if not val_cycles: val_cycles = "3000"
        val_cycles_prot = self.logic.read_dosbox_param(conf_path, "cpu", "cpu_cycles_protected")
        if not val_cycles_prot: val_cycles_prot = "60000"

        val_memsize = self.logic.read_dosbox_param(conf_path, "dosbox", "memsize") or "16"
        val_xms = self.logic.read_dosbox_param(conf_path, "dos", "xms") or "true"
        val_ems = self.logic.read_dosbox_param(conf_path, "dos", "ems") or "true"
        val_umb = self.logic.read_dosbox_param(conf_path, "dos", "umb") or "true"
        
        extra_data = self.logic.load_extra_config(name)
        val_loadfix = extra_data.get('loadfix', False)
        val_loadfix_size = extra_data.get('loadfix_size', "64")
        val_loadhigh = extra_data.get('loadhigh', False)

        val_output = self.logic.read_dosbox_param(conf_path, "sdl", "output") or "opengl"
        val_fullscreen = self.logic.read_dosbox_param(conf_path, "sdl", "fullscreen") or "false"
        val_winres = self.logic.read_dosbox_param(conf_path, "sdl", "windowresolution") or "default"
        val_fullres = self.logic.read_dosbox_param(conf_path, "sdl", "fullresolution") or "desktop"
        val_glshader = self.logic.read_dosbox_param(conf_path, "render", "glshader") or "none"
        val_intscale = self.logic.read_dosbox_param(conf_path, "render", "integer_scaling").lower() == "true"
        
        tab_dosbox.columnconfigure(0, weight=1)
        f_cpu = tb.Labelframe(tab_dosbox, text="CPU Settings", bootstyle="primary")
        f_cpu.pack(fill=tk.X, padx=10, pady=5)
        f_cpu.columnconfigure(1, weight=1); f_cpu.columnconfigure(3, weight=1)
        
        v_core = add_opt(f_cpu, 0, 0, "Core:", CORE_OPTIONS, val_core)
        v_cputype = add_opt(f_cpu, 0, 2, "CPU Type:", CPUTYPE_OPTIONS, val_cputype)
        v_cycles = add_opt(f_cpu, 1, 0, "Cycles (Real):", CYCLES_OPTIONS, val_cycles, True)
        v_cycles_prot = add_opt(f_cpu, 1, 2, "Cycles (Prot):", CYCLES_PROT_OPTIONS, val_cycles_prot, True)

        f_mem = tb.Labelframe(tab_dosbox, text="Memory Settings", bootstyle="info")
        f_mem.pack(fill=tk.X, padx=10, pady=5)
        v_memsize = add_opt(f_mem, 0, 0, "Memory (MB):", MEMSIZE_OPTIONS, val_memsize, True)
        f_mem_bools = tb.Frame(f_mem)
        f_mem_bools.grid(row=1, column=0, columnspan=4, sticky="w", padx=10, pady=5)
        
        v_xms = add_bool(f_mem_bools, "XMS", val_xms)
        v_ems = add_bool(f_mem_bools, "EMS", val_ems)
        v_umb = add_bool(f_mem_bools, "UMB", val_umb)
        v_loadhigh = tk.BooleanVar(value=val_loadhigh)
        tb.Checkbutton(f_mem_bools, text="Loadhigh", variable=v_loadhigh, bootstyle="round-toggle").pack(side=tk.LEFT, padx=10)

        f_loadfix = tb.Frame(f_mem)
        f_loadfix.grid(row=2, column=0, columnspan=4, sticky="w", padx=10, pady=5)
        v_loadfix = tk.BooleanVar(value=val_loadfix)
        v_loadfix_size = tk.StringVar(value=val_loadfix_size)
        def toggle_lf_size(): cb_lf.configure(state="readonly" if v_loadfix.get() else "disabled")
        tb.Checkbutton(f_loadfix, text="Loadfix", variable=v_loadfix, command=toggle_lf_size, bootstyle="round-toggle").pack(side=tk.LEFT, padx=(0, 5))
        cb_lf = tb.Combobox(f_loadfix, values=LOADFIX_SIZE_OPTIONS, textvariable=v_loadfix_size, width=5, state="disabled")
        cb_lf.pack(side=tk.LEFT)
        tb.Label(f_loadfix, text="KB").pack(side=tk.LEFT, padx=2)
        toggle_lf_size()

        f_vid = tb.Labelframe(tab_dosbox, text="Render / Video Settings", bootstyle="warning")
        f_vid.pack(fill=tk.X, padx=10, pady=5)
        f_vid.columnconfigure(1, weight=1); f_vid.columnconfigure(3, weight=1)
        v_output = add_opt(f_vid, 0, 0, "Output:", OUTPUT_OPTIONS, val_output)
        v_glshader = add_opt(f_vid, 0, 2, "GL Shader:", GLSHADER_OPTIONS, val_glshader)
        v_winres = add_opt(f_vid, 1, 0, "Window Res:", WIN_RES_OPTIONS, val_winres, True)
        v_fullres = add_opt(f_vid, 1, 2, "Fullscreen Res:", FULL_RES_OPTIONS, val_fullres, True)
        f_vid_bools = tb.Frame(f_vid)
        f_vid_bools.grid(row=2, column=0, columnspan=4, sticky="w", padx=10, pady=5)
        v_fullscreen = add_bool(f_vid_bools, "Fullscreen", val_fullscreen)
        v_intscale = tk.BooleanVar(value=val_intscale)
        tb.Checkbutton(f_vid_bools, text="Integer Scaling", variable=v_intscale, bootstyle="round-toggle").pack(side=tk.LEFT, padx=10)

        # --- TAB 4: AUDIO SETTINGS ---
        val_rate = self.logic.read_dosbox_param(conf_path, "mixer", "rate") or "48000"
        val_blocksize = self.logic.read_dosbox_param(conf_path, "mixer", "blocksize") or "1024"
        val_prebuffer = self.logic.read_dosbox_param(conf_path, "mixer", "prebuffer") or "25"
        
        f_mixer = tb.Labelframe(tab_audio, text="Mixer", bootstyle="secondary")
        f_mixer.pack(fill=tk.X, padx=10, pady=5)
        v_rate = add_opt(f_mixer, 0, 0, "Rate:", ["48000", "44100", "22050"], val_rate)
        v_blocksize = add_opt(f_mixer, 0, 2, "Blocksize:", ["1024", "2048", "4096", "512"], val_blocksize)
        v_prebuffer = add_opt(f_mixer, 0, 4, "Prebuffer:", [], val_prebuffer, True)

        val_sbtype = self.logic.read_dosbox_param(conf_path, "sblaster", "sbtype") or "sb16"
        val_sbbase = self.logic.read_dosbox_param(conf_path, "sblaster", "sbbase") or "220"
        val_irq = self.logic.read_dosbox_param(conf_path, "sblaster", "irq") or "7"
        val_dma = self.logic.read_dosbox_param(conf_path, "sblaster", "dma") or "1"
        val_hdma = self.logic.read_dosbox_param(conf_path, "sblaster", "hdma") or "5"
        val_opl = self.logic.read_dosbox_param(conf_path, "sblaster", "oplmode") or "auto"

        f_sb = tb.Labelframe(tab_audio, text="Sound Blaster", bootstyle="danger")
        f_sb.pack(fill=tk.X, padx=10, pady=5)
        v_sbtype = add_opt(f_sb, 0, 0, "Type:", SB_TYPES, val_sbtype)
        v_sbbase = add_opt(f_sb, 0, 2, "Base:", ["220", "240", "260"], val_sbbase)
        v_irq = add_opt(f_sb, 1, 0, "IRQ:", ["7", "5", "3"], val_irq)
        v_dma = add_opt(f_sb, 1, 2, "DMA:", ["1", "0", "3"], val_dma)
        v_hdma = add_opt(f_sb, 2, 0, "HDMA:", ["5", "1", "7"], val_hdma)
        v_opl = add_opt(f_sb, 2, 2, "OPL Mode:", OPL_MODES, val_opl)

        val_gus = self.logic.read_dosbox_param(conf_path, "gus", "gus") or "false"
        f_gus = tb.Labelframe(tab_audio, text="Gravis UltraSound", bootstyle="info")
        f_gus.pack(fill=tk.X, padx=10, pady=5)
        v_gus = add_opt(f_gus, 0, 0, "Enable GUS:", GUS_BOOL, val_gus)
        
        val_pcspeaker = self.logic.read_dosbox_param(conf_path, "speaker", "pcspeaker") or "impulse"
        val_tandy = self.logic.read_dosbox_param(conf_path, "speaker", "tandy") or "auto"
        val_lpt = self.logic.read_dosbox_param(conf_path, "speaker", "lpt_dac") or "none"
        
        f_spk = tb.Labelframe(tab_audio, text="Speaker & Other", bootstyle="success")
        f_spk.pack(fill=tk.X, padx=10, pady=5)
        v_pcspeaker = add_opt(f_spk, 0, 0, "PC Speaker:", SPEAKER_TYPES, val_pcspeaker)
        v_tandy = add_opt(f_spk, 0, 2, "Tandy:", TANDY_TYPES, val_tandy)
        v_lpt = add_opt(f_spk, 1, 0, "LPT DAC:", LPT_DAC_TYPES, val_lpt)

        val_midi = self.logic.read_dosbox_param(conf_path, "midi", "mididevice") or "auto"
        val_mpu = self.logic.read_dosbox_param(conf_path, "midi", "mpu401") or "intelligent"
        
        f_midi = tb.Labelframe(tab_audio, text="MIDI", bootstyle="warning")
        f_midi.pack(fill=tk.X, padx=10, pady=5)
        v_midi = add_opt(f_midi, 0, 0, "Device:", MIDI_DEVICES, val_midi)
        v_mpu = add_opt(f_midi, 0, 2, "MPU-401:", ["intelligent", "uart", "none"], val_mpu)

        def save():
            new_n = v_name.get().strip()
            if new_n != name:
                if not self.logic.rename_game(name, new_n): messagebox.showerror("Error", "Rename failed"); return
            
            self.logic.save_meta(new_n, ".year", v_year.get())
            self.logic.save_meta(new_n, ".company", v_comp.get())
            self.logic.save_meta(new_n, ".genre", v_genre.get())
            self.logic.save_meta(new_n, ".rating", cb.current())
            self.logic.save_meta(new_n, ".txt", t_desc.get(1.0, tk.END).strip())
            
            cdb = v_custom_dosbox.get().strip()
            if cdb: self.logic.save_meta(new_n, ".dosbox", cdb)
            else: 
                p = os.path.join(self.logic.folder_info, f"{new_n}.dosbox")
                if os.path.exists(p): os.remove(p)

            new_map = {}
            for exe_path, v_role, v_title in exe_widgets:
                label = v_role.get()
                role_key = ROLE_KEYS.get(label, ROLE_UNASSIGNED)
                if role_key != ROLE_UNASSIGNED:
                    new_map[exe_path] = {"role": role_key, "title": v_title.get().strip()}
            self.logic.save_exe_map(new_n, new_map)
            
            extra_conf = { "loadfix": v_loadfix.get(), "loadfix_size": v_loadfix_size.get(), "loadhigh": v_loadhigh.get() }
            self.logic.save_extra_config(new_n, extra_conf)

            config_data = {
                'cpu': { 'core': v_core.get(), 'cputype': v_cputype.get(), 'cycles': v_cycles.get(), 'cycles_protected': v_cycles_prot.get() },
                'dosbox': { 'memsize': v_memsize.get() },
                'dos': { 'xms': str(v_xms.get()).lower(), 'ems': str(v_ems.get()).lower(), 'umb': str(v_umb.get()).lower() },
                'sdl': { 'output': v_output.get(), 'fullscreen': str(v_fullscreen.get()).lower(), 'windowresolution': v_winres.get(), 'fullresolution': v_fullres.get() },
                'render': { 'glshader': v_glshader.get(), 'integer_scaling': 'true' if v_intscale.get() else 'false' },
                'extra': extra_conf,
                'mixer': {'rate': v_rate.get(), 'blocksize': v_blocksize.get(), 'prebuffer': v_prebuffer.get()},
                'sblaster': {'sbtype': v_sbtype.get(), 'sbbase': v_sbbase.get(), 'irq': v_irq.get(), 'dma': v_dma.get(), 'hdma': v_hdma.get(), 'oplmode': v_opl.get()},
                'gus': {'gus': v_gus.get()},
                'speaker': {'pcspeaker': v_pcspeaker.get(), 'tandy': v_tandy.get(), 'lpt_dac': v_lpt.get()},
                'midi': {'mididevice': v_midi.get(), 'mpu401': v_mpu.get()}
            }
            self.logic.write_game_config(new_n, config_data)
            self.refresh_library()
            if new_n + ".zip" in self.tree.get_children(): self.tree.selection_set(new_n+".zip")
            top.destroy()
        
        tb.Button(top, text="Save Configuration", command=save, bootstyle="success").pack(pady=10)

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