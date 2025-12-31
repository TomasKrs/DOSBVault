import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
from ttkbootstrap.tooltip import ToolTip
import re
import os
from ..utils import truncate_text, format_size
from .. import constants

class DetailPanel(tb.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, width=550) # Set fixed width
        self.app = app
        self.pack(side=LEFT, fill=Y, padx=(10, 0), pady=(0, 10))
        self.pack_propagate(False) # Prevent resizing based on content
        self._setup_widgets()

    def _setup_widgets(self):
        # --- Top controls ---
        control_frame = tb.Frame(self); control_frame.pack(fill=X, pady=5, padx=10)
        self.btn_fullscreen = tb.Button(control_frame, text="Fullscreen OFF", bootstyle="secondary-outline", command=self.app.toggle_fullscreen); self.btn_fullscreen.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        self.btn_auto_exit = tb.Button(control_frame, text="Auto-close OFF", bootstyle="secondary-outline", command=self.app.toggle_auto_exit); self.btn_auto_exit.pack(side=LEFT, fill=X, expand=True, padx=5)
        self.btn_fav = tb.Button(control_frame, text="♡", width=3, bootstyle="secondary-outline", command=self.app.toggle_favorite_button); self.btn_fav.pack(side=LEFT, padx=5)
        self.btn_toggle_desc = tb.Button(control_frame, text="Details ON", bootstyle="success", command=self.app.toggle_description); self.btn_toggle_desc.pack(side=LEFT, padx=5)
        self.btn_list = tb.Button(control_frame, text="List ON", bootstyle="success", command=self.app.toggle_list); self.btn_list.pack(side=LEFT, padx=(5,0))

        # --- Image Panel ---
        img_container = tb.Frame(self, height=384) # Set fixed height for image area
        img_container.pack(fill=X, pady=5, padx=10)
        img_container.pack_propagate(False)
        self.lbl_img = tb.Label(img_container, text="Select Game", anchor=CENTER, bootstyle="secondary", relief=SOLID, borderwidth=1); self.lbl_img.pack(fill=BOTH, expand=True)
        self.lbl_img_info = tb.Label(self, text="", anchor=E); self.lbl_img_info.pack(fill=X, padx=10)

        # --- Title and Info with STABLE ARROWS ---
        title_frame_outer = tb.Frame(self); title_frame_outer.pack(fill=X, pady=2, padx=10)
        
        # Left arrow, packed to the left
        tb.Button(title_frame_outer, text="<", command=self.app.select_prev, bootstyle="secondary", width=2).pack(side=LEFT, padx=(0, 10))
        
        # Right arrow, packed to the right
        tb.Button(title_frame_outer, text=">", command=self.app.select_next, bootstyle="secondary", width=2).pack(side=RIGHT, padx=(10, 0))

        # Inner frame for all text content, expands to fill the middle
        title_frame_inner = tb.Frame(title_frame_outer); title_frame_inner.pack(side=LEFT, fill=X, expand=True)
        
        self.lbl_title = tb.Label(title_frame_inner, text="Select Game", font="-size 14 -weight bold", anchor='w'); self.lbl_title.pack(fill=X)
        self.title_tooltip = ToolTip(self.lbl_title, "")
        
        self.lbl_year = tb.Label(title_frame_inner, text="", bootstyle="secondary", anchor='w'); self.lbl_year.pack(fill=X)
        
        rating_frame = tb.Frame(title_frame_inner); rating_frame.pack(fill=X)
        self.lbl_rating = tb.Label(rating_frame, text="☆☆☆☆☆", font="-size 12", bootstyle="warning"); self.lbl_rating.pack(side=LEFT)
        self.lbl_rating.bind("<Button-1>", self.on_rating_click)
        self.lbl_critics_score = tb.Label(rating_frame, text="", bootstyle="secondary"); self.lbl_critics_score.pack(side=LEFT, padx=5)
        
        # Player Icons Frame
        self.frm_players = tb.Frame(rating_frame); self.frm_players.pack(side=RIGHT, padx=5)
        self.player_icons = []
        for i in range(5):
            lbl = tb.Label(self.frm_players, text="🧍", font="-size 14", bootstyle="secondary")
            lbl.pack(side=LEFT)
            lbl.bind("<Button-1>", lambda e, count=i+1: self.on_player_icon_click(count))
            self.player_icons.append(lbl)
        
        # --- Action Buttons ---
        action_frame = tb.Frame(self); action_frame.pack(fill=X, pady=10, padx=10)
        
        self.btn_play = tb.Menubutton(action_frame, text="▶ Play", bootstyle="success", state=DISABLED, direction="below")
        self.btn_play.pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        self.play_menu = tb.Menu(self.btn_play, tearoff=0)
        self.btn_play.configure(menu=self.play_menu)
        
        self.btn_edit = tb.Button(action_frame, text="✎ Configuration", bootstyle="primary", state=DISABLED, command=self.app.open_edit_window); self.btn_edit.pack(side=LEFT, fill=X, expand=True)

        self.btn_watch_video = tb.Button(self, text="▶️ Watch Video", bootstyle="info-outline", state=DISABLED, command=self.app.on_watch_video)
        self.btn_watch_video.pack(fill=X, pady=5, padx=10)

        # --- Footer ---
        # Pack size label first so it stays at the very bottom
        self.lbl_size = tb.Label(self, text="", bootstyle="secondary", anchor='e'); self.lbl_size.pack(side=BOTTOM, fill=X, pady=2, padx=10)
        
        self.footer_frame = tb.Frame(self); self.footer_frame.pack(side=BOTTOM, fill=X, pady=5, padx=10)
        self.btn_install = tb.Button(self.footer_frame, text="Install", bootstyle="success", state=DISABLED, command=self.app.on_install)
        self.btn_uninstall = tb.Button(self.footer_frame, text="Uninstall", bootstyle="danger", state=DISABLED, command=self.app.on_uninstall)
        self.btn_install.pack(side=LEFT, expand=True, fill=X, padx=(0,5))
        self.btn_uninstall.pack(side=LEFT, expand=True, fill=X)

        # --- Tabs ---
        self.tabs = tb.Notebook(self, bootstyle="primary"); self.tabs.pack(fill=X, expand=False, pady=5, padx=10)
        
        self.txt_desc = ScrolledText(self.tabs, wrap=WORD, autohide=True, height=12); self.tabs.add(self.txt_desc, text="Description")
        
        self.txt_notes = ScrolledText(self.tabs, wrap=WORD, autohide=True, bootstyle="info", height=12); self.tabs.add(self.txt_notes, text="My Notes")
        
        # Docs Tab
        self.docs_frame = tb.Frame(self.tabs); self.tabs.add(self.docs_frame, text="Docs")
        self.docs_list = tb.Treeview(self.docs_frame, columns=("size",), show="tree headings", bootstyle="primary")
        self.docs_list.heading("#0", text="Filename", anchor=W); self.docs_list.heading("size", text="Size", anchor=W)
        self.docs_list.column("#0", stretch=True); self.docs_list.column("size", width=80, stretch=False)
        self.docs_list.pack(fill=BOTH, expand=True, side=LEFT)
        self.docs_scroll = tb.Scrollbar(self.docs_frame, orient="vertical", command=self.docs_list.yview); self.docs_scroll.pack(side=RIGHT, fill=Y)
        self.docs_list.configure(yscrollcommand=self.docs_scroll.set)
        self.docs_list.bind("<Double-1>", self.on_doc_double_click)

        self.computer_text = ScrolledText(self.tabs, wrap=NONE, height=12, autohide=True, font=("Consolas", 9)); self.tabs.add(self.computer_text, text="Computer")
        self.info_text = ScrolledText(self.tabs, wrap=NONE, height=12, autohide=True, font=("Consolas", 9)); self.tabs.add(self.info_text, text="Info")
        self.dosbox_info_text = ScrolledText(self.tabs, wrap=NONE, height=12, autohide=True, bootstyle="secondary", font=("Consolas", 9)); self.tabs.add(self.dosbox_info_text, text="DOSBox Keys")

        self.txt_notes.text.bind("<FocusOut>", lambda e: self.app.save_notes())

    def update_details(self, details, is_installed):
        self.current_details = details
        is_fav = details.get("favorite", False); video_links = details.get("video_links", [])
        self.btn_edit.configure(state=tk.NORMAL if is_installed else tk.DISABLED); self.btn_fav.config(text="♥" if is_fav else "♡", bootstyle="danger" if is_fav else "secondary-outline"); self.btn_watch_video.configure(state=tk.NORMAL if video_links else tk.DISABLED)
        
        self.btn_install.pack_forget(); self.btn_uninstall.pack_forget()
        if is_installed:
            self.btn_uninstall.pack(side=LEFT, expand=True, fill=X)
            self.btn_uninstall.configure(state=tk.NORMAL)
            self.btn_play.configure(state=tk.NORMAL)
            
            # Update Play Menu
            self.play_menu.delete(0, END)
            self.play_menu.add_command(label="Main Game", command=self.app.on_play, font='-weight bold')
            
            # Find setup exe
            setup_exe = next((exe for exe, info in details.get("executables", {}).items() if info.get("role") in [constants.ROLE_SETUP, constants.ROLE_INSTALL]), None)
            if setup_exe:
                self.play_menu.add_command(label="Run Setup", command=lambda: self.app.run_specific_exe(setup_exe))
            
            # Add "Other..." submenu
            other_menu = tb.Menu(self.play_menu, tearoff=0)
            zip_name = self.app._get_selected_zip()
            if zip_name:
                game_name = os.path.splitext(zip_name)[0]
                found_exes = self.app.logic.get_all_executables(game_name)
                if found_exes:
                    exe_info = details.get("executables", {})
                    added_count = 0
                    for exe in found_exes:
                        # Skip if role is IGNORE (if such role exists) or if it's Main/Setup which are already in main menu?
                        # User said: "nedavaju ostatne polozky, ktore maju nastavene ignore.. da sa tam len ta, ktora sa urci do Other"
                        # Checking constants.py, there is no explicit IGNORE role, but there is ROLE_CUSTOM ("Custom...").
                        # Maybe user means ROLE_CUSTOM is the one that should go to "Other".
                        # Or maybe "Unassigned" ones should go there too?
                        # "da sa tam len ta, ktora sa urci do Other" -> Only those explicitly set to "Other" (Custom?).
                        
                        role = exe_info.get(exe, {}).get("role", constants.ROLE_UNASSIGNED)
                        
                        # If user implies "Custom/Addons" is the "Other" category:
                        if role == constants.ROLE_CUSTOM:
                            label_text = exe
                            if exe in exe_info and exe_info[exe].get("title"):
                                label_text = exe_info[exe].get("title")
                            other_menu.add_command(label=label_text, command=lambda x=exe: self.app.run_specific_exe(x))
                            added_count += 1
                            
                    if added_count > 0:
                        self.play_menu.add_cascade(label="Other...", menu=other_menu)

            self.play_menu.add_separator()
            self.play_menu.add_command(label="DOSBox Prompt", command=self.app.open_dos_prompt)
            
        else:
            self.btn_install.pack(side=LEFT, expand=True, fill=X, padx=(0,5))
            self.btn_install.configure(state=tk.NORMAL)
            self.btn_play.configure(state=tk.DISABLED)

        full_title = details.get("title", "").replace("_"," ").title(); self.lbl_title.config(text=truncate_text(full_title, 40)); self.title_tooltip.text = full_title
        g = details.get("genre", ""); y = details.get("year", ""); dev = details.get("developers", ""); pub = details.get("publishers", "")
        self.lbl_year.config(text=f"[{g}] {y} | Dev: {truncate_text(dev,20)} | Pub: {truncate_text(pub,20)}")
        r = details.get("rating", 0); self.lbl_rating.config(text="★" * r + "☆" * (5 - r)); 
        
        p_str = details.get("num_players", ""); p_num = 0
        if p_str and (numbers := re.findall(r'\d+', p_str)):
            try: p_num = int(numbers[0])
            except (ValueError, IndexError): pass
        self.update_player_icons(p_num)
        
        cs = details.get("critics_score", 0); self.lbl_critics_score.config(text=f"({cs}%)" if cs > 0 else "")
        self.txt_desc.text.config(state=tk.NORMAL); self.txt_desc.delete(1.0, tk.END); self.txt_desc.insert(tk.END, details.get("description") or "No description."); self.txt_desc.text.config(state=tk.DISABLED)
        self.txt_notes.text.delete(1.0, tk.END); self.txt_notes.insert(tk.END, details.get("notes") or "")
        self.update_info_panel(details)
        self.update_computer_panel(details)
        self.update_docs_tab(details)

    def update_player_icons(self, count):
        for i, lbl in enumerate(self.player_icons):
            if i < count:
                lbl.config(bootstyle="default") # Active color
            else:
                lbl.config(bootstyle="secondary") # Ghost/Inactive color

    def on_player_icon_click(self, count):
        self.app.set_num_players_from_click(count)
        self.update_player_icons(count)

    def update_info_panel(self, details):
        game_name = details.get("title", ""); game_folder = self.app.logic.find_game_folder(game_name)
        self.info_text.text.config(state=tk.NORMAL); self.info_text.delete(1.0, tk.END)
        if custom_fields := details.get("custom_fields", {}):
            self.info_text.insert(tk.END, "[ CUSTOM INFO ]\n", ('header',))
            for key, value in custom_fields.items():
                is_link = value.startswith(("http:", "https:", "www.")) or ":\\" in value or value.startswith(".\\")
                self.info_text.insert(tk.END, f"{key}: "); self.info_text.insert(tk.END, value, ('link',) if is_link else ()); self.info_text.insert(tk.END, "\n")
            self.info_text.insert(tk.END, "\n")
        self.info_text.insert(tk.END, "[ PATHS ]\n", ('header',))
        def add_info_line(label, path): self.info_text.insert(tk.END, f"{label}: "); self.info_text.insert(tk.END, path if path and os.path.exists(path) else "N/A", ('link',) if path and os.path.exists(path) else ('secondary',)); self.info_text.insert(tk.END, "\n")
        add_info_line("Game Path", game_folder); add_info_line("Info File", self.app.logic._get_game_json_path(game_name)); add_info_line("Screenshots", os.path.join(self.app.logic.base_dir, "database", "games_datainfo", game_name, "screenshots")); self.info_text.insert(tk.END, "\n")
        self.info_text.insert(tk.END, "[ MOUNTED DRIVES ]\n", ('header',)); self.info_text.insert(tk.END, "C: -> .\\drives\\c\\\n" if game_folder and os.path.exists(os.path.join(game_folder, "drives", "c")) else "C: -> (Game's main folder)\n")
        if isos := self.app.logic.get_mounted_isos(game_name): self.info_text.insert(tk.END, f"D: -> {len(isos)} image(s) mounted\n")
        else: self.info_text.insert(tk.END, "D: -> (No ISOs mounted)\n")
        self.info_text.text.config(state=tk.DISABLED)
        dosbox_info_content = "[ KEYBOARD SHORTCUTS ]\n" + (constants.DOSBOX_CONTROLS if hasattr(constants, 'DOSBOX_CONTROLS') else "")
        self.dosbox_info_text.text.config(tabs=('120', '150'), state=tk.NORMAL); self.dosbox_info_text.delete(1.0, tk.END); self.dosbox_info_text.insert(tk.END, dosbox_info_content); self.dosbox_info_text.text.config(state=tk.DISABLED)

    def update_computer_panel(self, details):
        def get_cpu_name(cycles_str):
            if str(cycles_str).lower() == "auto": return "Automatic (based on game)"
            try: cycles = int(cycles_str)
            except (ValueError, TypeError): return "Auto"
            if cycles <= 0: return "Unknown"
            closest_cpu = "Custom"; min_diff = float('inf')
            if hasattr(constants, 'CPU_CYCLES_MAP'):
                for val, cpu_name in constants.CPU_CYCLES_MAP.items():
                    if (diff := abs(cycles - val)) < min_diff: min_diff = diff; closest_cpu = f"Approx. {cpu_name}"
            return closest_cpu
        def get_monitor_display(res_str): return "Automatic (Desktop)" if res_str in ["default", "desktop"] else res_str
        
        # Merge user overrides into ds for display purposes
        ds = details.get("dosbox_settings", {}).copy()
        if user_overrides := details.get("user_overrides", {}):
            for section, keys in user_overrides.items():
                if section not in ds: ds[section] = {}
                ds[section].update(keys)
        
        # Determine if Staging
        is_staging = False
        custom_path = details.get("custom_dosbox_path", "")
        if "staging" in custom_path.lower(): is_staging = True
        elif not custom_path and "staging" in self.app.logic.default_dosbox_exe.lower(): is_staging = True
        
        cpu_settings = ds.get('cpu', {}); cpu_cycles = cpu_settings.get('cpu_cycles', 'auto')
        
        # Staging Logic for Cycles
        if is_staging:
            has_dos4gw = self.app.logic.game_has_dos4gw(self.game_name)
            if has_dos4gw:
                # If DOS4GW is present, Staging uses cpu_cycles_protected
                cpu_cycles = cpu_settings.get('cpu_cycles_protected', 'auto')
            else:
                # Otherwise it uses cpu_cycles
                cpu_cycles = cpu_settings.get('cpu_cycles', 'auto')
        else:
            # Standard/X behavior
            if cpu_settings.get('use_protected_cycles', False): cpu_cycles = cpu_settings.get('cpu_cycles_protected', 'auto')
            
        sb_conf = ds.get('sblaster', {})
        sb_type = sb_conf.get('sbtype', 'sb16').upper(); midi_device = ds.get('midi', {}).get('mididevice', 'auto'); sound_card = f"{sb_type}" + (f" + {midi_device.upper()}" if midi_device not in ['auto', 'none'] else "")
        sb_details = f"Addr:{sb_conf.get('sbbase', '220')} IRQ:{sb_conf.get('irq', '7')} DMA:{sb_conf.get('dma', '1')}/{sb_conf.get('hdma', '5')}"
        
        render_conf = ds.get('render', {})
        machine = ds.get('dosbox', {}).get('machine', 'svga_s3').upper()
        scaler = render_conf.get('scaler', 'none').upper()
        aspect = "ON" if str(render_conf.get('aspect', 'false')).lower() == 'true' else "OFF"
        
        # Extra info from user overrides or advanced settings
        core = cpu_settings.get('core', 'auto').upper()
        cputype = cpu_settings.get('cputype', 'auto').upper()
        
        computer_art = ["    +-----------------------+ ", "   /|                      /| ", "  / |   DOS Game Manager   / | ", " /  |     Vintage PC     /  | ", "+-----------------------+   | ", "|   +-------------------+   | ", "|   |                   |   | ", "|   |                   |   | ", "|   +-------------------+   | ", "|                       |  /  ", "|_______________________| /   ", " \\_____________________\\/    "]
        panel = self.computer_text; panel.text.config(state=tk.NORMAL); panel.delete(1.0, tk.END); [panel.insert(tk.END, line + '\n') for line in computer_art]
        panel.insert(tk.END, "\n--- VIRTUAL HARDWARE ---\n"); 
        
        panel.insert(tk.END, f"Processor:    {core} ({cputype})\n")
        panel.insert(tk.END, f"Memory (RAM): {ds.get('dosbox', {}).get('memsize', '16')} MB\n")
        panel.insert(tk.END, f"Graphics:     {machine}\n"); panel.insert(tk.END, f"              (Scaler: {scaler}, Aspect: {aspect})\n")
        panel.insert(tk.END, f"Monitor:      {get_monitor_display(ds.get('sdl', {}).get('windowresolution', 'default'))}\n")
        panel.insert(tk.END, f"Sound Card:   {sound_card}\n"); panel.insert(tk.END, f"              ({sb_details})\n")
        panel.insert(tk.END, f"CD-ROM Drive: {'Yes' if self.app.logic.get_mounted_isos(details.get('title','')) else 'No'}\n"); panel.text.config(state=tk.DISABLED)

    def clear_details(self):
        self.lbl_title.config(text="Select Game"); self.title_tooltip.text = ""
        self.lbl_year.config(text=""); self.lbl_rating.config(text="☆☆☆☆☆"); self.update_player_icons(0); self.lbl_critics_score.config(text="")
        self.lbl_img.config(image='', text="No Image"); self.lbl_img.image = None
        self.btn_play.config(state=tk.DISABLED); self.btn_edit.config(state=tk.DISABLED); self.btn_watch_video.config(state=tk.DISABLED); self.btn_fav.config(text="♡")
        self.btn_install.pack(side=LEFT, expand=True, fill=X, padx=(0,5)); self.btn_uninstall.pack_forget()
        self.btn_install.configure(state=DISABLED)
        self.lbl_size.config(text=""); self.lbl_img_info.config(text="")
        for text_widget in [self.txt_desc.text, self.info_text.text, self.dosbox_info_text.text, self.computer_text.text]: text_widget.config(state=tk.NORMAL); text_widget.delete(1.0, tk.END); text_widget.config(state=tk.DISABLED)
        self.txt_notes.text.delete(1.0, tk.END)

    def on_rating_click(self, event):
        width = self.lbl_rating.winfo_width()
        if width > 0:
            rating = int(event.x // (width/5)) + 1
            current_rating = self.lbl_rating.cget("text").count("★")
            if rating == current_rating: rating = 0
            self.app.set_rating_from_click(rating)

    def update_docs_tab(self, details):
        self.docs_list.delete(*self.docs_list.get_children())
        game_name = details.get("title", "")
        if not game_name: return
        
        game_folder = self.app.logic.find_game_folder(game_name)
        if not game_folder or not os.path.isdir(game_folder): return
        
        docs_dir = os.path.join(game_folder, "docs")
        if not os.path.isdir(docs_dir): return
        
        for f in sorted(os.listdir(docs_dir)):
            full_path = os.path.join(docs_dir, f)
            if os.path.isfile(full_path):
                size_str = format_size(os.path.getsize(full_path))
                self.docs_list.insert("", END, text=f, values=(size_str,), tags=(full_path,))

    def on_doc_double_click(self, event):
        selection = self.docs_list.selection()
        if not selection: return
        item_id = selection[0]
        tags = self.docs_list.item(item_id, "tags")
        if tags:
            file_path = tags[0]
            try: os.startfile(file_path)
            except Exception as e: print(f"Error opening file: {e}")