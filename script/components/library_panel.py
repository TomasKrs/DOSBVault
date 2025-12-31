import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import os
import random
try:
    from PIL import Image, ImageTk
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

class ImagePreviewTooltip(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.label = tk.Label(self, bg="black", bd=1, relief="solid")
        self.label.pack()
        self.current_image_path = None

    def show(self, image_paths, x, y):
        if not HAS_PILLOW: return
        
        # Check setting
        if not self.master.app.settings.get("hover_preview", True):
            return
        
        # Ensure image_paths is a list
        if isinstance(image_paths, str):
            self.image_paths = [image_paths]
        else:
            self.image_paths = image_paths
            
        if not self.image_paths: return
        
        self.current_idx = 0
        self._display_image(self.image_paths[0])

        # Position tooltip
        self.geometry(f"+{x+20}+{y+20}")
        self.deiconify()
        
        # Start cycling if multiple
        self._stop_cycling()
        if len(self.image_paths) > 1 and self.master.app.settings.get("slideshow_enabled", True):
            interval = self.master.app.settings.get("slideshow_interval", 3)
            self.timer = self.after(int(interval * 1000), self._cycle)

    def _display_image(self, path):
        if self.current_image_path != path:
            try:
                img = Image.open(path)
                # Resize to thumbnail based on setting
                size_str = self.master.app.settings.get("thumbnail_size", "Medium")
                size_map = {"Small": (200, 200), "Medium": (350, 350), "Large": (500, 500)}
                size = size_map.get(size_str, (350, 350))
                
                img.thumbnail(size)
                self.photo = ImageTk.PhotoImage(img)
                self.label.config(image=self.photo)
                self.current_image_path = path
            except Exception:
                return

    def _cycle(self):
        self.current_idx = (self.current_idx + 1) % len(self.image_paths)
        self._display_image(self.image_paths[self.current_idx])
        
        interval = self.master.app.settings.get("slideshow_interval", 3)
        self.timer = self.after(int(interval * 1000), self._cycle)

    def _stop_cycling(self):
        if hasattr(self, 'timer') and self.timer:
            self.after_cancel(self.timer)
            self.timer = None

    def hide(self):
        self._stop_cycling()
        self.withdraw()

class LibraryPanel(tb.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.columns = ["name", "genre", "year", "developers", "publishers", "rating", "critics_score", "num_players", "play_count", "play_time", "last_played", "installed", "docs", "setup", "cds", "archive", "hdd"]
        self.preview_tooltip = None
        self.last_hovered_item = None
        self.view_mode = self.app.settings.get("view_mode", "list")
        self.grid_images = {} # Cache for grid images
        self._setup_widgets()

    def _setup_widgets(self):
        # --- Search and Filter ---
        search_frame = tb.Frame(self); search_frame.pack(fill=X, pady=5)
        search_frame.columnconfigure(0, weight=1)
        tb.Entry(search_frame, textvariable=self.app.search_var).grid(row=0, column=0, sticky='ew')
        tb.Checkbutton(search_frame, variable=self.app.fav_only_var, text="★ Only", bootstyle="toolbutton,warning", command=self.app.refresh_library).grid(row=0, column=1, padx=5)
        
        # View Toggle Button
        icon = "☰" if self.view_mode == "grid" else "⊞"
        self.btn_view = tb.Button(search_frame, text=icon, bootstyle="secondary-outline", command=self.toggle_view, width=3)
        self.btn_view.grid(row=0, column=2, padx=5)
        
        # Settings and Refresh buttons
        tb.Button(search_frame, text="⚙ Settings", bootstyle="link", command=self.app.open_settings).grid(row=0, column=3, padx=5)
        # Optimization: Refresh without full detection by default, unless user explicitly asks or on startup
        tb.Button(search_frame, text="⟳", bootstyle="toolbutton", command=lambda: self.app.refresh_library(detect_new=True)).grid(row=0, column=4, padx=5)
        tb.Button(search_frame, text="Import Archives", bootstyle="success-outline", command=self.app.add_game_zip).grid(row=0, column=5, padx=5)
        tb.Button(search_frame, text="Batch Utils", bootstyle="info-outline", command=self.app.open_batch_wizard).grid(row=0, column=6, padx=5)

        # Container for Views
        self.view_container = tb.Frame(self)
        self.view_container.pack(fill=BOTH, expand=True)
        
        # --- List View (Treeview) ---
        self.tree_frame = tb.Frame(self.view_container)
        # self.tree_frame.pack(fill=BOTH, expand=True) # Packed conditionally below
        
        # Configure style for grid lines if possible, though standard ttk themes vary.
        # We can try to force a border or background.
        style = tb.Style()
        
        # Initial configuration from settings
        self.apply_appearance_settings()
        
        # Use a container frame for Grid layout to ensure scrollbars are visible
        # tree_container = tb.Frame(self) # Replaced by self.tree_frame
        self.tree_frame.columnconfigure(0, weight=1)
        self.tree_frame.rowconfigure(0, weight=1)

        # Use "tree headings" to show the #0 column for icons
        self.tree = tb.Treeview(self.tree_frame, columns=self.columns, show="tree headings", selectmode="browse", bootstyle="primary", style="GameList.Treeview")
        self.tree.grid(row=0, column=0, sticky='nsew')

        # --- Scrollbars ---
        v_scroll = tb.Scrollbar(self.tree_frame, orient=VERTICAL, command=self.tree.yview, bootstyle="round")
        v_scroll.grid(row=0, column=1, sticky='ns')
        
        h_scroll = tb.Scrollbar(self.tree_frame, orient=HORIZONTAL, command=self.tree.xview, bootstyle="round")
        h_scroll.grid(row=1, column=0, sticky='ew')
        
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        # Bind Motion for Image Preview
        if HAS_PILLOW:
            self.preview_tooltip = ImagePreviewTooltip(self)
            self.tree.bind("<Motion>", self._on_motion)
            self.tree.bind("<Leave>", lambda e: self.preview_tooltip.hide())
        
        # Configure striped rows - High Contrast Light Mode
        # User requested "readable" and "not dark".
        # We force a light theme for the list rows specifically.
        self.tree.tag_configure('odd', background='#ffffff', foreground='black') 
        self.tree.tag_configure('even', background='#f0f0f0', foreground='black') 
        
        # --- Column Headers and Sorting ---
        # Configure #0 column for Icons
        self.tree.column("#0", width=60, stretch=False, anchor="w") # Left align icons too as requested
        self.tree.heading("#0", text="Status", anchor="w")

        for col_id in self.columns:
            self.tree.heading(col_id, text=col_id.replace("_", " ").title(), command=lambda c=col_id: self.app.sort_tree(c), anchor="w")
            # Set stretch=False for most columns to prevent auto-resizing
            self.tree.column(col_id, width=100, stretch=False, minwidth=50, anchor="w")
        
        # Allow Name to stretch? User said "stale sa to prisposobuje". 
        # If we want fixed columns, we set stretch=False for all.
        # But we need at least one to fill the space? 
        # If we set all to False, there will be empty space at the end.
        # I will set Name to stretch=False but give it a large width.
        self.tree.column("name", width=300, stretch=False, minwidth=150, anchor="w")
        self.tree.column("developers", width=150, stretch=False, anchor="w")
        self.tree.column("publishers", width=150, stretch=False, anchor="w")
        self.tree.column("last_played", width=120, stretch=False, anchor="w")
        self.tree.column("play_time", width=80, anchor="w", stretch=False)
        self.tree.column("installed", width=100, stretch=False, anchor="w")
        self.tree.column("docs", width=50, anchor="w", stretch=False)
        self.tree.column("setup", width=50, anchor="w", stretch=False)
        self.tree.column("cds", width=50, anchor="w", stretch=False)
        
        self.apply_user_column_settings()
        
        # --- Grid View ---
        self.grid_frame = tb.Frame(self.view_container)
        self.grid_canvas = tk.Canvas(self.grid_frame, highlightthickness=0)
        self.grid_scrollbar = tb.Scrollbar(self.grid_frame, orient="vertical", command=self.grid_canvas.yview, bootstyle="round")
        self.grid_scrollable_frame = tb.Frame(self.grid_canvas)
        
        self.grid_scrollable_frame.bind("<Configure>", lambda e: self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all")))
        self.grid_canvas.create_window((0, 0), window=self.grid_scrollable_frame, anchor="nw")
        self.grid_canvas.configure(yscrollcommand=self.grid_scrollbar.set)
        
        self.grid_canvas.pack(side="left", fill="both", expand=True)
        self.grid_scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel for grid
        def _on_mousewheel(event):
            self.grid_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.grid_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Bind resize to update columns
        self.grid_canvas.bind("<Configure>", self._on_grid_resize)
        
        # Initial View State
        if self.view_mode == "grid":
            self.grid_frame.pack(fill=BOTH, expand=True)
        else:
            self.tree_frame.pack(fill=BOTH, expand=True)
        
        # Image Cycling
        self.image_cycle_timer = None
        self.current_image_indices = {} # {game_name: index}

    def _on_grid_resize(self, event):
        if self.view_mode == "grid":
            self.populate_grid()

    def toggle_view(self):
        if self.view_mode == "list":
            self.view_mode = "grid"
            self.btn_view.config(text="☰")
            self.tree_frame.pack_forget()
            self.grid_frame.pack(fill=BOTH, expand=True)
            self.populate_grid()
            self._start_image_cycling()
        else:
            self.view_mode = "list"
            self.btn_view.config(text="⊞")
            self.grid_frame.pack_forget()
            self.tree_frame.pack(fill=BOTH, expand=True)
            self._stop_image_cycling()
        
        self.app.settings.set("view_mode", self.view_mode)

    def on_library_refreshed(self):
        if self.view_mode == "grid":
            self.populate_grid()
        elif self.view_mode == "list":
             # Ensure list is visible if mode is list (e.g. on startup)
             self.grid_frame.pack_forget()
             self.tree_frame.pack(fill=BOTH, expand=True)
        
        # Handle initial state if grid
        if self.view_mode == "grid" and not self.grid_frame.winfo_ismapped():
             self.tree_frame.pack_forget()
             self.grid_frame.pack(fill=BOTH, expand=True)
             self._start_image_cycling()

    def _start_image_cycling(self):
        if self.image_cycle_timer: return
        self._cycle_images()
        
    def _stop_image_cycling(self):
        if self.image_cycle_timer:
            self.after_cancel(self.image_cycle_timer)
            self.image_cycle_timer = None

    def _cycle_images(self):
        if self.view_mode != "grid": return
        if not self.app.settings.get("slideshow_enabled", True): return
        
        # Iterate over visible items
        if hasattr(self, 'grid_item_widgets'):
            current_time = self.app.winfo_toplevel().tk.call('clock', 'milliseconds')
            
            for game_name, widgets in self.grid_item_widgets.items():
                images = widgets['images']
                if len(images) > 1:
                    # Check if it's time to update this specific item
                    next_update = widgets.get('next_update', 0)
                    if current_time >= next_update:
                        # Update image
                        idx = self.current_image_indices.get(game_name, 0)
                        idx = (idx + 1) % len(images)
                        self.current_image_indices[game_name] = idx
                        
                        next_img_path = images[idx]
                        photo = self._get_cached_photo(next_img_path)
                        if photo:
                            widgets['lbl_img'].configure(image=photo)
                        
                        # Set next random update time based on setting
                        interval = self.app.settings.get("slideshow_interval", 3) * 1000
                        widgets['next_update'] = current_time + interval + random.randint(0, 1000)
        
        # Check frequently (e.g. every 500ms) to catch items whose time has come
        self.image_cycle_timer = self.after(500, self._cycle_images)

    def _get_cached_photo(self, path):
        if path in self.grid_images: return self.grid_images[path]
        try:
            pil_img = Image.open(path)
            
            # Dynamic size
            size_str = self.app.settings.get("thumbnail_size", "Medium")
            size_map = {"Small": (100, 100), "Medium": (150, 150), "Large": (250, 250)}
            size = size_map.get(size_str, (150, 150))
            
            pil_img.thumbnail(size)
            photo = ImageTk.PhotoImage(pil_img)
            self.grid_images[path] = photo
            return photo
        except: return None

    def populate_grid(self):
        if not HAS_PILLOW: return
        
        # Clear
        for widget in self.grid_scrollable_frame.winfo_children(): widget.destroy()
        self.grid_item_widgets = {}
        self.grid_images = {} # Clear cache to force resize
        
        items = self.tree.get_children()
        if not items: return
        
        # Calculate columns based on width
        width = self.grid_canvas.winfo_width()
        if width < 200: width = 800 # Default if not mapped yet
        
        size_str = self.app.settings.get("thumbnail_size", "Medium")
        width_map = {"Small": 130, "Medium": 180, "Large": 280}
        item_width = width_map.get(size_str, 180)
        
        COLUMNS = max(1, width // item_width)
        
        row = 0
        col = 0
        
        for item_id in items:
            zip_name = item_id
            game_name = os.path.splitext(zip_name)[0]
            
            # Frame for item
            f_item = tb.Frame(self.grid_scrollable_frame, padding=5, bootstyle="light")
            f_item.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            # Image
            images = self.app.logic.get_game_images(game_name)
            image_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')
            valid_images = [img for img in images if img.lower().endswith(image_exts)]
            
            photo = None
            current_idx = self.current_image_indices.get(game_name, 0)
            if valid_images:
                if current_idx >= len(valid_images): current_idx = 0
                first_image = valid_images[current_idx]
                photo = self._get_cached_photo(first_image)
            
            if not photo:
                # Placeholder
                lbl_img = tb.Label(f_item, text="No Image", width=20, anchor="center", bootstyle="secondary")
                lbl_img.pack(pady=(0, 5))
                self.grid_item_widgets[game_name] = {'lbl_img': lbl_img, 'images': [], 'next_update': 0}
            else:
                lbl_img = tb.Label(f_item, image=photo)
                lbl_img.pack(pady=(0, 5))
                # Initialize next_update with random offset so they don't all start at once
                import random
                next_up = self.app.winfo_toplevel().tk.call('clock', 'milliseconds') + random.randint(0, 3000)
                self.grid_item_widgets[game_name] = {'lbl_img': lbl_img, 'images': valid_images, 'next_update': next_up}
                
            # Title
            title = self.tree.item(item_id, "values")[0]
            lbl_title = tb.Label(f_item, text=title, wraplength=150, justify="center", font=("Segoe UI", 9, "bold"))
            lbl_title.pack()
            
            # Bind click
            for w in (f_item, lbl_img, lbl_title):
                w.bind("<Button-1>", lambda e, i=item_id: self._on_grid_click(i))
                w.bind("<Double-Button-1>", lambda e, i=item_id: self._on_grid_double_click(i))
                w.bind("<Button-3>", lambda e, i=item_id: self._on_grid_right_click(e, i))
            
            col += 1
            if col >= COLUMNS:
                col = 0
                row += 1

    def _on_grid_click(self, item_id):
        self.tree.selection_set(item_id)
        self.app.on_select(None) # Trigger detail panel update

    def _on_grid_right_click(self, event, item_id):
        self.tree.selection_set(item_id)
        self.app.on_select(None)
        self.app.show_tree_context(event, item_id=item_id)

    def _on_grid_double_click(self, item_id):
        self.tree.selection_set(item_id)
        self.app.launch_game(item_id)

    def apply_appearance_settings(self):
        row_height = self.app.settings.get("row_height", 45)
        font_size = self.app.settings.get("font_size", 11)
        style = tb.Style()
        # Configure specific style for Game List to avoid affecting other Treeviews (like in Settings)
        style.configure("GameList.Treeview", rowheight=row_height, font=('Segoe UI', font_size), borderwidth=1, relief="solid") 
        style.configure("GameList.Treeview.Heading", font=('Segoe UI', font_size, 'bold'))

    def apply_user_column_settings(self):
        hidden_columns = self.app.settings.get('hidden_columns', [])
        display_columns = [col for col in self.columns if col not in hidden_columns]
        self.tree["displaycolumns"] = display_columns

    def _on_motion(self, event):
        item_id = self.tree.identify_row(event.y)
        column_id = self.tree.identify_column(event.x)
        
        # Only show preview if hovering over the Name column (#1) or Icon column (#0)
        # Treeview columns are #0, #1, #2... identify_column returns #1, #2 etc.
        # Name is the first data column, so it's #1. Icon is #0.
        if item_id and (column_id == "#1" or column_id == "#0"):
            if item_id != self.last_hovered_item:
                self.last_hovered_item = item_id
                
                # Get game name from item (iid is zip_name)
                zip_name = item_id
                game_name = os.path.splitext(zip_name)[0]
                
                # Find first image
                images = self.app.logic.get_game_images(game_name)
                # Filter for images only
                image_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')
                valid_images = [img for img in images if img.lower().endswith(image_exts)]
                
                if valid_images:
                    self.preview_tooltip.show(valid_images, event.x_root, event.y_root)
                else:
                    self.preview_tooltip.hide()
        else:
            if self.last_hovered_item:
                self.preview_tooltip.hide()
                self.last_hovered_item = None