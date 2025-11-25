import tkinter as tk
from tkinter import messagebox, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import os
import webbrowser

# Imports from our modules
from constants import *
from utils import truncate_text

class EditWindow(tb.Toplevel):
    def __init__(self, parent_app, zip_name):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.logic = parent_app.logic
        self.zip_name = zip_name
        self.name = os.path.splitext(zip_name)[0]
        
        self.title(f"Configuration: {self.name}")
        self.geometry("900x750")

        self.game_folder = self.logic.find_game_folder(self.zip_name)
        self.conf_path = os.path.join(self.game_folder, "dosbox.conf")

        self._init_ui()

    def _init_ui(self):
        tabs = tb.Notebook(self)
        tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tab_general = tb.Frame(tabs)
        tab_executables = tb.Frame(tabs)
        tab_dosbox = tb.Frame(tabs)
        tab_audio = tb.Frame(tabs)
        
        tabs.add(tab_general, text="General")
        tabs.add(tab_executables, text="Executables")
        tabs.add(tab_dosbox, text="DOSBox Settings")
        tabs.add(tab_audio, text="Audio Settings")
        
        # --- Build Tabs ---
        self._build_general_tab(tab_general)
        self._build_executables_tab(tab_executables)
        self._build_dosbox_tab(tab_dosbox)
        self._build_audio_tab(tab_audio)
        
        # --- Save Button ---
        tb.Button(self, text="Save Configuration", command=self._save, bootstyle="success").pack(pady=10)

    def _build_general_tab(self, parent):
        self.v_name = tk.StringVar(value=self.name)
        self.v_year = tk.StringVar(value=self.logic.load_meta(self.name, ".year"))
        self.v_comp = tk.StringVar(value=self.logic.load_meta(self.name, ".company"))
        self.v_genre = tk.StringVar(value=self.logic.load_meta(self.name, ".genre"))
        self.v_custom_dosbox = tk.StringVar(value=self.logic.load_meta(self.name, ".dosbox"))
        pad = 5
        
        f_top = tb.Frame(parent)
        f_top.pack(fill=tk.X, padx=10, pady=(10,0))
        tb.Label(f_top, text="Game Title:").pack(side=tk.LEFT)
        tb.Button(f_top, text="🌐 Search Info", command=self._open_browser_search, bootstyle="info-outline", width=12).pack(side=tk.RIGHT)
        
        tb.Entry(parent, textvariable=self.v_name).pack(fill=tk.X, padx=10, pady=pad)
        
        tb.Label(parent, text="Genre:").pack(anchor="w", padx=10)
        self.cb_genre = tb.Combobox(parent, values=GENRE_OPTIONS, textvariable=self.v_genre)
        self.cb_genre.pack(fill=tk.X, padx=10, pady=pad)

        tb.Label(parent, text="Year:").pack(anchor="w", padx=10)
        tb.Entry(parent, textvariable=self.v_year).pack(fill=tk.X, padx=10, pady=pad)
        
        tb.Label(parent, text="Developer/Company:").pack(anchor="w", padx=10)
        tb.Entry(parent, textvariable=self.v_comp).pack(fill=tk.X, padx=10, pady=pad)
        
        tb.Label(parent, text="Custom DOSBox EXE:").pack(anchor="w", padx=10)
        f_db = tb.Frame(parent); f_db.pack(fill=tk.X, padx=10, pady=pad)
        tb.Entry(f_db, textvariable=self.v_custom_dosbox).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tb.Button(f_db, text="...", command=lambda: filedialog.askopenfilename(parent=self), bootstyle="secondary-outline").pack(side=tk.RIGHT, padx=(5,0))

        tb.Label(parent, text="Rating:").pack(anchor="w", padx=10)
        vals = ["0 Stars"] + [f"{i} Stars" for i in range(1,6)]
        self.cb_rating = tb.Combobox(parent, values=vals, state="readonly"); self.cb_rating.pack(fill=tk.X, padx=10, pady=pad)
        self.cb_rating.current(self.logic.load_rating(self.name))
        
        tb.Label(parent, text="Description:").pack(anchor="w", padx=10)
        self.t_desc = tk.Text(parent, height=8); self.t_desc.pack(fill=tk.BOTH, padx=10, pady=pad, expand=True)
        self.t_desc.insert(tk.END, self.logic.load_meta(self.name, ".txt"))

    def _build_executables_tab(self, parent):
        tb.Label(parent, text="Assign roles to found executables:", bootstyle="secondary").pack(anchor="w", padx=10, pady=10)
        
        exe_frame = tb.Frame(parent)
        exe_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        current_map = self.logic.load_exe_map(self.name)
        found_exes = self.logic.scan_game_executables(self.zip_name)
        self.exe_widgets = [] 
        
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
                                command=lambda x=exe: self.logic.launch_game(self.zip_name, x))
            btn_run.grid(row=r, column=1, padx=5)

            info = current_map.get(exe, None)
            low = exe.lower()
            if info is None:
                current_role = ROLE_SETUP if any(x in low for x in ['setup', 'install', 'config', 'setsound', 'sound']) else ROLE_UNASSIGNED
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
                e_t.configure(state="normal" if v_r.get() == ROLE_DISPLAY[ROLE_CUSTOM] else "disabled")
            cb_role.bind("<<ComboboxSelected>>", on_role_change)
            on_role_change()
            self.exe_widgets.append((exe, var_role, var_title))

    def _build_dosbox_tab(self, parent):
        val_core = self.logic.read_dosbox_param(self.conf_path, "cpu", "core") or "auto"
        val_cputype = self.logic.read_dosbox_param(self.conf_path, "cpu", "cputype") or "auto"
        val_cycles = self.logic.read_dosbox_param(self.conf_path, "cpu", "cycles", "3000") # simplified
        val_cycles_prot = self.logic.read_dosbox_param(self.conf_path, "cpu", "cycles_protected", "60000") # simplified

        val_memsize = self.logic.read_dosbox_param(self.conf_path, "dosbox", "memsize") or "16"
        val_xms = self.logic.read_dosbox_param(self.conf_path, "dos", "xms") or "true"
        val_ems = self.logic.read_dosbox_param(self.conf_path, "dos", "ems") or "true"
        val_umb = self.logic.read_dosbox_param(self.conf_path, "dos", "umb") or "true"
        
        extra_data = self.logic.load_extra_config(self.name)
        val_loadfix = extra_data.get('loadfix', False)
        val_loadfix_size = extra_data.get('loadfix_size', "64")
        val_loadhigh = extra_data.get('loadhigh', False)

        val_output = self.logic.read_dosbox_param(self.conf_path, "sdl", "output") or "opengl"
        val_fullscreen = self.logic.read_dosbox_param(self.conf_path, "sdl", "fullscreen") or "false"
        val_winres = self.logic.read_dosbox_param(self.conf_path, "sdl", "windowresolution") or "default"
        val_fullres = self.logic.read_dosbox_param(self.conf_path, "sdl", "fullresolution") or "desktop"
        val_glshader = self.logic.read_dosbox_param(self.conf_path, "render", "glshader") or "none"
        val_intscale = self.logic.read_dosbox_param(self.conf_path, "render", "integer_scaling", "false").lower() == "true"
        
        parent.columnconfigure(0, weight=1)
        f_cpu = tb.Labelframe(parent, text="CPU Settings", bootstyle="primary")
        f_cpu.pack(fill=tk.X, padx=10, pady=5)
        f_cpu.columnconfigure(1, weight=1); f_cpu.columnconfigure(3, weight=1)
        
        self.v_core = self._add_opt(f_cpu, 0, 0, "Core:", CORE_OPTIONS, val_core)
        self.v_cputype = self._add_opt(f_cpu, 0, 2, "CPU Type:", CPUTYPE_OPTIONS, val_cputype)
        self.v_cycles = self._add_opt(f_cpu, 1, 0, "Cycles (Real):", CYCLES_OPTIONS, val_cycles, True)
        self.v_cycles_prot = self._add_opt(f_cpu, 1, 2, "Cycles (Prot):", CYCLES_PROT_OPTIONS, val_cycles_prot, True)

        f_mem = tb.Labelframe(parent, text="Memory Settings", bootstyle="info")
        f_mem.pack(fill=tk.X, padx=10, pady=5)
        self.v_memsize = self._add_opt(f_mem, 0, 0, "Memory (MB):", MEMSIZE_OPTIONS, val_memsize, True)
        f_mem_bools = tb.Frame(f_mem)
        f_mem_bools.grid(row=1, column=0, columnspan=4, sticky="w", padx=10, pady=5)
        
        self.v_xms = self._add_bool(f_mem_bools, "XMS", val_xms)
        self.v_ems = self._add_bool(f_mem_bools, "EMS", val_ems)
        self.v_umb = self._add_bool(f_mem_bools, "UMB", val_umb)
        self.v_loadhigh = tk.BooleanVar(value=val_loadhigh)
        tb.Checkbutton(f_mem_bools, text="Loadhigh", variable=self.v_loadhigh, bootstyle="round-toggle").pack(side=tk.LEFT, padx=10)

        f_loadfix = tb.Frame(f_mem)
        f_loadfix.grid(row=2, column=0, columnspan=4, sticky="w", padx=10, pady=5)
        self.v_loadfix = tk.BooleanVar(value=val_loadfix)
        self.v_loadfix_size = tk.StringVar(value=val_loadfix_size)
        cb_lf = tb.Combobox(f_loadfix, values=LOADFIX_SIZE_OPTIONS, textvariable=self.v_loadfix_size, width=5)
        def toggle_lf_size(): cb_lf.configure(state="readonly" if self.v_loadfix.get() else "disabled")
        tb.Checkbutton(f_loadfix, text="Loadfix", variable=self.v_loadfix, command=toggle_lf_size, bootstyle="round-toggle").pack(side=tk.LEFT, padx=(0, 5))
        cb_lf.pack(side=tk.LEFT)
        tb.Label(f_loadfix, text="KB").pack(side=tk.LEFT, padx=2)
        toggle_lf_size()

        f_vid = tb.Labelframe(parent, text="Render / Video Settings", bootstyle="warning")
        f_vid.pack(fill=tk.X, padx=10, pady=5)
        f_vid.columnconfigure(1, weight=1); f_vid.columnconfigure(3, weight=1)
        self.v_output = self._add_opt(f_vid, 0, 0, "Output:", OUTPUT_OPTIONS, val_output)
        self.v_glshader = self._add_opt(f_vid, 0, 2, "GL Shader:", GLSHADER_OPTIONS, val_glshader)
        self.v_winres = self._add_opt(f_vid, 1, 0, "Window Res:", WIN_RES_OPTIONS, val_winres, True)
        self.v_fullres = self._add_opt(f_vid, 1, 2, "Fullscreen Res:", FULL_RES_OPTIONS, val_fullres, True)
        f_vid_bools = tb.Frame(f_vid)
        f_vid_bools.grid(row=2, column=0, columnspan=4, sticky="w", padx=10, pady=5)
        self.v_fullscreen = self._add_bool(f_vid_bools, "Fullscreen", val_fullscreen)
        self.v_intscale = tk.BooleanVar(value=val_intscale)
        tb.Checkbutton(f_vid_bools, text="Integer Scaling", variable=self.v_intscale, bootstyle="round-toggle").pack(side=tk.LEFT, padx=10)

    def _build_audio_tab(self, parent):
        val_rate = self.logic.read_dosbox_param(self.conf_path, "mixer", "rate") or "48000"
        val_blocksize = self.logic.read_dosbox_param(self.conf_path, "mixer", "blocksize") or "1024"
        val_prebuffer = self.logic.read_dosbox_param(self.conf_path, "mixer", "prebuffer") or "25"
        
        f_mixer = tb.Labelframe(parent, text="Mixer", bootstyle="secondary")
        f_mixer.pack(fill=tk.X, padx=10, pady=5)
        self.v_rate = self._add_opt(f_mixer, 0, 0, "Rate:", ["48000", "44100", "22050"], val_rate)
        self.v_blocksize = self._add_opt(f_mixer, 0, 2, "Blocksize:", ["1024", "2048", "4096", "512"], val_blocksize)
        self.v_prebuffer = self._add_opt(f_mixer, 0, 4, "Prebuffer:", [], val_prebuffer, True)

        val_sbtype = self.logic.read_dosbox_param(self.conf_path, "sblaster", "sbtype") or "sb16"
        val_sbbase = self.logic.read_dosbox_param(self.conf_path, "sblaster", "sbbase") or "220"
        val_irq = self.logic.read_dosbox_param(self.conf_path, "sblaster", "irq") or "7"
        val_dma = self.logic.read_dosbox_param(self.conf_path, "sblaster", "dma") or "1"
        val_hdma = self.logic.read_dosbox_param(self.conf_path, "sblaster", "hdma") or "5"
        val_opl = self.logic.read_dosbox_param(self.conf_path, "sblaster", "oplmode") or "auto"

        f_sb = tb.Labelframe(parent, text="Sound Blaster", bootstyle="danger")
        f_sb.pack(fill=tk.X, padx=10, pady=5)
        self.v_sbtype = self._add_opt(f_sb, 0, 0, "Type:", SB_TYPES, val_sbtype)
        self.v_sbbase = self._add_opt(f_sb, 0, 2, "Base:", ["220", "240", "260"], val_sbbase)
        self.v_irq = self._add_opt(f_sb, 1, 0, "IRQ:", ["7", "5", "3"], val_irq)
        self.v_dma = self._add_opt(f_sb, 1, 2, "DMA:", ["1", "0", "3"], val_dma)
        self.v_hdma = self._add_opt(f_sb, 2, 0, "HDMA:", ["5", "1", "7"], val_hdma)
        self.v_opl = self._add_opt(f_sb, 2, 2, "OPL Mode:", OPL_MODES, val_opl)

        val_gus = self.logic.read_dosbox_param(self.conf_path, "gus", "gus") or "false"
        f_gus = tb.Labelframe(parent, text="Gravis UltraSound", bootstyle="info")
        f_gus.pack(fill=tk.X, padx=10, pady=5)
        self.v_gus = self._add_opt(f_gus, 0, 0, "Enable GUS:", GUS_BOOL, val_gus)
        
        val_pcspeaker = self.logic.read_dosbox_param(self.conf_path, "speaker", "pcspeaker") or "impulse"
        val_tandy = self.logic.read_dosbox_param(self.conf_path, "speaker", "tandy") or "auto"
        val_lpt = self.logic.read_dosbox_param(self.conf_path, "speaker", "lpt_dac") or "none"
        
        f_spk = tb.Labelframe(parent, text="Speaker & Other", bootstyle="success")
        f_spk.pack(fill=tk.X, padx=10, pady=5)
        self.v_pcspeaker = self._add_opt(f_spk, 0, 0, "PC Speaker:", SPEAKER_TYPES, val_pcspeaker)
        self.v_tandy = self._add_opt(f_spk, 0, 2, "Tandy:", TANDY_TYPES, val_tandy)
        self.v_lpt = self._add_opt(f_spk, 1, 0, "LPT DAC:", LPT_DAC_TYPES, val_lpt)

        val_midi = self.logic.read_dosbox_param(self.conf_path, "midi", "mididevice") or "auto"
        val_mpu = self.logic.read_dosbox_param(self.conf_path, "midi", "mpu401") or "intelligent"
        
        f_midi = tb.Labelframe(parent, text="MIDI", bootstyle="warning")
        f_midi.pack(fill=tk.X, padx=10, pady=5)
        self.v_midi = self._add_opt(f_midi, 0, 0, "Device:", MIDI_DEVICES, val_midi)
        self.v_mpu = self._add_opt(f_midi, 0, 2, "MPU-401:", ["intelligent", "uart", "none"], val_mpu)

    def _open_browser_search(self):
        query = f"{self.v_name.get()} dos game info mobygames"
        url = f"https://www.google.com/search?q={query}"
        webbrowser.open(url)

    def _add_opt(self, parent, row, col, label, opts, val, editable=False):
        tb.Label(parent, text=label).grid(row=row, column=col, sticky="e", padx=5, pady=5)
        var = tk.StringVar(value=val)
        st = "normal" if editable else "readonly"
        if opts:
            cb = tb.Combobox(parent, values=opts, textvariable=var, state=st, width=15)
            cb.grid(row=row, column=col+1, sticky="w", padx=5, pady=5)
        else:
            tb.Entry(parent, textvariable=var, width=15).grid(row=row, column=col+1, sticky="w", padx=5, pady=5)
        return var

    def _add_bool(self, parent, txt, val_str):
        v = tk.BooleanVar(value=(str(val_str).lower() == "true"))
        tb.Checkbutton(parent, text=txt, variable=v, bootstyle="round-toggle").pack(side=tk.LEFT, padx=10)
        return v

    def _save(self):
        # 1. Save general metadata
        new_name = self.v_name.get().strip()
        if new_name != self.name:
            if not self.logic.rename_game(self.name, new_name):
                messagebox.showerror("Error", "Rename failed. The new name might already exist.", parent=self)
                return
        
        self.logic.save_meta(new_name, ".year", self.v_year.get())
        self.logic.save_meta(new_name, ".company", self.v_comp.get())
        self.logic.save_meta(new_name, ".genre", self.v_genre.get())
        self.logic.save_meta(new_name, ".rating", self.cb_rating.current())
        self.logic.save_meta(new_name, ".txt", self.t_desc.get(1.0, tk.END).strip())
        
        # 2. Save custom dosbox path
        cdb = self.v_custom_dosbox.get().strip()
        if cdb:
            self.logic.save_meta(new_name, ".dosbox", cdb)
        else:
            p = os.path.join(self.logic.folder_info, f"{new_name}.dosbox")
            if os.path.exists(p): os.remove(p)

        # 3. Save executable map
        new_map = {}
        for exe_path, v_role, v_title in self.exe_widgets:
            label = v_role.get()
            role_key = ROLE_KEYS.get(label, ROLE_UNASSIGNED)
            if role_key != ROLE_UNASSIGNED:
                new_map[exe_path] = {"role": role_key, "title": v_title.get().strip()}
        self.logic.save_exe_map(new_name, new_map)
        
        # 4. Save extra config (loadfix, etc.)
        extra_conf = { "loadfix": self.v_loadfix.get(), "loadfix_size": self.v_loadfix_size.get(), "loadhigh": self.v_loadhigh.get() }
        self.logic.save_extra_config(new_name, extra_conf)

        # 5. Save dosbox.conf settings
        config_data = {
            'cpu': { 'core': self.v_core.get(), 'cputype': self.v_cputype.get(), 'cycles': self.v_cycles.get(), 'cycles_protected': self.v_cycles_prot.get() },
            'dosbox': { 'memsize': self.v_memsize.get() },
            'dos': { 'xms': str(self.v_xms.get()).lower(), 'ems': str(self.v_ems.get()).lower(), 'umb': str(self.v_umb.get()).lower() },
            'sdl': { 'output': self.v_output.get(), 'fullscreen': str(self.v_fullscreen.get()).lower(), 'windowresolution': self.v_winres.get(), 'fullresolution': self.v_fullres.get() },
            'render': { 'glshader': self.v_glshader.get(), 'integer_scaling': 'true' if self.v_intscale.get() else 'false' },
            'extra': extra_conf,
            'mixer': {'rate': self.v_rate.get(), 'blocksize': self.v_blocksize.get(), 'prebuffer': self.v_prebuffer.get()},
            'sblaster': {'sbtype': self.v_sbtype.get(), 'sbbase': self.v_sbbase.get(), 'irq': self.v_irq.get(), 'dma': self.v_dma.get(), 'hdma': self.v_hdma.get(), 'oplmode': self.v_opl.get()},
            'gus': {'gus': self.v_gus.get()},
            'speaker': {'pcspeaker': self.v_pcspeaker.get(), 'tandy': self.v_tandy.get(), 'lpt_dac': self.v_lpt.get()},
            'midi': {'mididevice': self.v_midi.get(), 'mpu401': self.v_mpu.get()}
        }
        self.logic.write_game_config(new_name, config_data)

        # 6. Refresh main UI and close
        self.parent_app.refresh_library()
        new_zip_name = new_name + ".zip"
        if new_zip_name in self.parent_app.tree.get_children():
            self.parent_app.tree.selection_set(new_zip_name)
        
        self.destroy()