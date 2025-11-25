import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *

class DetailPanel(tb.Frame):
    def __init__(self, parent, app_logic, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = parent
        self.logic = app_logic
        self._init_ui()

    def _init_ui(self):
        self.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.rowconfigure(5, weight=1) 

        # IMAGE
        f_img = tk.Frame(self, bg="black", bd=2, relief=tk.SUNKEN, width=512, height=384)
        f_img.pack(pady=(0, 5)); f_img.pack_propagate(False)
        self.lbl_img = tk.Label(f_img, text="No Image", bg="black", fg="gray")
        self.lbl_img.pack(expand=True, fill=tk.BOTH)
        self.lbl_img.bind("<Button-1>", lambda e: self.app.next_image())
        self.lbl_img.bind("<Button-3>", lambda e: self.app.show_img_context(e))
        
        self.lbl_img_info = tb.Label(self, text="", font=("Segoe UI", 8), bootstyle="secondary")
        self.lbl_img_info.pack(pady=(0, 10))

        # TITLE & META
        f_meta = tb.Frame(self, width=512, height=60)
        f_meta.pack(pady=5); f_meta.pack_propagate(False)
        self.lbl_title = tb.Label(f_meta, text="Select Game", font=("Segoe UI", 18, "bold"), bootstyle="inverse-dark")
        self.lbl_title.pack(pady=(0, 2))
        f_det = tb.Frame(f_meta)
        f_det.pack()
        self.lbl_year = tb.Label(f_det, text="", bootstyle="secondary"); self.lbl_year.pack(side=tk.LEFT, padx=10)
        self.lbl_comp = tb.Label(f_det, text="", bootstyle="secondary"); self.lbl_comp.pack(side=tk.LEFT)

        # CONTROLS
        f_ctrl = tb.Frame(self)
        f_ctrl.pack(pady=15)
        tb.Button(f_ctrl, text="⏮", command=self.app.select_prev, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=5)
        self.btn_play = tb.Button(f_ctrl, text="▶ PLAY", command=self.app.on_play, bootstyle="success", width=10, state=tk.DISABLED)
        self.btn_play.pack(side=tk.LEFT, padx=5)
        self.btn_install = tb.Button(f_ctrl, text="📥 Install", command=self.app.on_install, bootstyle="primary", width=10)
        self.btn_install.pack(side=tk.LEFT, padx=5)
        self.btn_uninstall = tb.Button(f_ctrl, text="🗑", command=self.app.on_uninstall, bootstyle="danger-outline", state=tk.DISABLED, width=3)
        self.btn_uninstall.pack(side=tk.LEFT, padx=5)
        tb.Button(f_ctrl, text="⏭", command=self.app.select_next, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=5)

        # TOOLS
        f_tools = tb.Frame(self)
        f_tools.pack(pady=5)
        self.btn_edit = tb.Button(f_tools, text="✎ Configuration", command=self.app.open_edit_window, bootstyle="warning", width=15, state=tk.DISABLED)
        self.btn_edit.pack(side=tk.LEFT, padx=5)
        self.btn_list = tb.Button(f_tools, text="☰ List", command=self.app.toggle_list, bootstyle="secondary-outline", width=6)
        self.btn_list.pack(side=tk.LEFT, padx=5)
        self.btn_backup = tb.Button(f_tools, text="💾 Backup Save", command=self.app.backup_save, bootstyle="info-outline", width=15, state=tk.DISABLED)
        self.btn_backup.pack(side=tk.LEFT, padx=5)

        # Stats
        f_stats = tb.Frame(self, width=512)
        f_stats.pack(fill=tk.X, pady=(15, 5))
        self.lbl_rating = tb.Label(f_stats, text="", font=("Segoe UI", 16), bootstyle="warning")
        self.lbl_rating.pack(side=tk.LEFT, padx=10)
        self.lbl_size = tb.Label(f_stats, text="", bootstyle="secondary")
        self.lbl_size.pack(side=tk.RIGHT, padx=10)

        # TABS: INFO / NOTES / SHORTCUTS
        self.tabs_info = tb.Notebook(self)
        self.tabs_info.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Tab 1: Desc
        tab_desc = tb.Frame(self.tabs_info)
        self.tabs_info.add(tab_desc, text="Info")
        scr_desc = tb.Scrollbar(tab_desc, orient="vertical")
        self.txt_desc = tk.Text(tab_desc, bg="#2b2b2b", fg="#ddd", wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10, yscrollcommand=scr_desc.set)
        scr_desc.config(command=self.txt_desc.yview)
        scr_desc.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_desc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Tab 2: Notes
        tab_notes = tb.Frame(self.tabs_info)
        self.tabs_info.add(tab_notes, text="Notes")
        scr_notes = tb.Scrollbar(tab_notes, orient="vertical")
        self.txt_notes = tk.Text(tab_notes, bg="#333333", fg="#fff", wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10, yscrollcommand=scr_notes.set)
        scr_notes.config(command=self.txt_notes.yview)
        scr_notes.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_notes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.txt_notes.bind("<KeyRelease>", lambda e: self.app.save_notes())
        
        # Tab 3: Shortcuts
        tab_sheet = tb.Frame(self.tabs_info)
        self.tabs_info.add(tab_sheet, text="Shortcuts")
        self.lbl_sheet = tk.Label(tab_sheet, text="", justify=tk.LEFT, font=("Consolas", 9), anchor="nw", bg="#222", fg="#0f0")
        self.lbl_sheet.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)