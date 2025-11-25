import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *

class LibraryPanel(tb.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = parent
        self._init_ui()

    def _init_ui(self):
        self.grid(row=0, column=1, sticky="nsew", padx=(0, 15), pady=15)
        
        tb.Label(self, text="Game Library", font=("Segoe UI", 14, "bold"), bootstyle="primary").pack(fill=tk.X)
        
        f_search = tb.Frame(self)
        f_search.pack(fill=tk.X, pady=10)
        tb.Label(f_search, text="🔍").pack(side=tk.LEFT, padx=5)
        tb.Entry(f_search, textvariable=self.app.search_var, bootstyle="dark").pack(side=tk.LEFT, fill=tk.X, expand=True)
        tb.Checkbutton(f_search, text="★ Only", variable=self.app.fav_only_var, command=self.app.refresh_library, bootstyle="danger-round-toggle").pack(side=tk.LEFT, padx=10)

        f_bot = tb.Frame(self)
        f_bot.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        tb.Button(f_bot, text="⚙ Settings", command=self.app.open_settings, bootstyle="secondary").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tb.Button(f_bot, text="↻ Refresh", command=self.app.refresh_library, bootstyle="secondary").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        f_tree_container = tb.Frame(self)
        f_tree_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cols = ("name", "genre", "year", "company", "rating", "zip", "hdd")
        self.tree = tb.Treeview(f_tree_container, columns=cols, show="headings", selectmode="browse", bootstyle="dark")
        
        for col in cols:
            self.tree.heading(col, text=col.title(), command=lambda c=col: self.app.sort_tree(c))
        
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
        self.tree.bind("<<TreeviewSelect>>", self.app.on_select)
        self.tree.bind("<Double-1>", lambda e: self.app.on_double_click())
        self.tree.bind("<Button-3>", self.app.show_tree_context)