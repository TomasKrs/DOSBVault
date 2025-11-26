import os
import shutil
import zipfile
import subprocess
import re
import json
import threading
import time
import datetime

# Imports from our modules
from constants import *
from utils import remove_readonly

HAS_PILLOW = False
try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError: pass

class GameLogic:
    def __init__(self, settings):
        self.settings = settings
        self.folder_info = os.path.join(BASE_DIR, "info")
        self.folder_screens = os.path.join(BASE_DIR, "screens")
        self.folder_backups = os.path.join(BASE_DIR, "backups")
        self._migrate_legacy_screens()

    @property
    def installed_dir(self): return self.settings.get("root_dir")
    @property
    def zipped_dir(self): return self.settings.get("zip_dir")

    def get_dosbox_exe(self, game_name=None):
        if game_name:
            custom = self.load_meta(game_name, ".dosbox")
            if custom and os.path.exists(custom):
                return custom
        return self.settings.get("dosbox_exe")

    def find_game_folder(self, zip_name):
        name_no_zip = os.path.splitext(zip_name)[0]
        return os.path.join(self.installed_dir, name_no_zip)

    def get_screens_dir(self, game_name):
        path = os.path.join(self.folder_screens, game_name)
        if not os.path.exists(path): os.makedirs(path, exist_ok=True)
        return path

    def get_game_list(self):
        zipped = set()
        if os.path.exists(self.zipped_dir):
            zipped = {f for f in os.listdir(self.zipped_dir) if f.lower().endswith(".zip")}
        
        installed = set()
        if os.path.exists(self.installed_dir):
            for d in os.listdir(self.installed_dir):
                full_path = os.path.join(self.installed_dir, d)
                if os.path.isdir(full_path):
                    installed.add(d + ".zip")
        return sorted(list(zipped | installed)), installed

    # --- MINIMÁLNE ZMENY SÚ LEN V TEJTO METÓDE ---
    def launch_game(self, zip_name, specific_exe=None, force_fullscreen=False, hide_console=False):
        name = os.path.splitext(zip_name)[0]
        folder = os.path.join(self.installed_dir, name)
        db_exe = self.get_dosbox_exe(name)
        
        if not db_exe or not os.path.exists(db_exe): raise Exception(f"DOSBox EXE not found:\n{db_exe}")
        
        # Vytvoríme základný príkaz
        command_args = [db_exe]

        # Pridáme nové parametre
        if force_fullscreen:
            command_args.append("--fullscreen")
        if hide_console:
            command_args.append("-noconsole") # Používame -noconsole, ako ste špecifikovali
        
        if specific_exe: 
            # Pre custom exe voláme komplexnejšiu metódu, ale odovzdáme jej upravené argumenty
            self._launch_custom_mode(folder, specific_exe, command_args, mode="exe", game_name=name)
        else: 
            # Pre štandardný štart pridáme -conf a spustíme
            def run_std():
                # Pridanie -conf pre štandardný štart
                final_command = command_args + ["-conf", "dosbox.conf"]
                
                start_time = time.time()
                subprocess.call(final_command, cwd=folder, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                for f in ["stdout.txt", "stderr.txt"]:
                    fp = os.path.join(folder, f)
                    if os.path.exists(fp):
                        try: os.remove(fp)
                        except: pass
                self.import_screenshots_from_capture(folder, name, start_time)

            threading.Thread(target=run_std, daemon=True).start()

    # --- ZVYŠOK SÚBORU JE ABSOLÚTNE BEZO ZMENY ---

    def load_meta(self, game_name, extension):
        path = os.path.join(self.folder_info, f"{game_name}{extension}")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f: return f.read().strip()
            except: pass
        return ""
    def load_extra_config(self, game_name):
        path = os.path.join(self.folder_info, f"{game_name}.extra")
        if os.path.exists(path):
            try:
                with open(path, 'r') as f: return json.load(f)
            except: pass
        return {}
    def save_extra_config(self, game_name, data):
        os.makedirs(self.folder_info, exist_ok=True)
        path = os.path.join(self.folder_info, f"{game_name}.extra")
        try:
            with open(path, 'w') as f: json.dump(data, f)
        except: pass
    def load_rating(self, game_name):
        val = self.load_meta(game_name, ".rating")
        return int(val) if val.isdigit() else 0
    def is_favorite(self, game_name):
        return os.path.exists(os.path.join(self.folder_info, f"{game_name}.fav"))
    def toggle_favorite(self, game_name):
        os.makedirs(self.folder_info, exist_ok=True)
        path = os.path.join(self.folder_info, f"{game_name}.fav")
        if os.path.exists(path):
            os.remove(path)
            return False
        else:
            with open(path, 'w') as f: f.write("1")
            return True
    def save_meta(self, game_name, extension, value):
        os.makedirs(self.folder_info, exist_ok=True)
        path = os.path.join(self.folder_info, f"{game_name}{extension}")
        try:
            with open(path, 'w', encoding='utf-8') as f: f.write(str(value))
        except: pass
    def load_exe_map(self, game_name):
        path = os.path.join(self.folder_info, f"{game_name}.exes.json")
        data = {}
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    raw = json.load(f)
                    for k, v in raw.items():
                        if isinstance(v, str): data[k] = {"role": v, "title": ""}
                        else: data[k] = v
            except: pass
        return data
    def save_exe_map(self, game_name, mapping):
        os.makedirs(self.folder_info, exist_ok=True)
        path = os.path.join(self.folder_info, f"{game_name}.exes.json")
        try:
            with open(path, 'w') as f: json.dump(mapping, f, indent=4)
        except: pass
    def scan_game_executables(self, zip_name):
        game_folder = self.find_game_folder(zip_name)
        exes = []
        if not os.path.exists(game_folder): return []
        for root, _, files in os.walk(game_folder):
            if "dosbox" in root.lower(): continue 
            for f in files:
                if f.lower().endswith(('.exe', '.com', '.bat')):
                    full_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_path, game_folder)
                    exes.append(rel_path)
        return sorted(exes)
    def get_mounted_isos(self, game_name):
        game_folder = os.path.join(self.installed_dir, game_name)
        cd_folder = os.path.join(game_folder, "cd")
        isos = []
        if os.path.exists(cd_folder):
            valid_exts = ('.cue', '.iso', '.img', '.ccd', '.mdf')
            isos = [f for f in sorted(os.listdir(cd_folder)) if f.lower().endswith(valid_exts)]
        return isos
    def backup_game_saves(self, zip_name):
        game_name = os.path.splitext(zip_name)[0]
        game_folder = self.find_game_folder(zip_name)
        if not os.path.exists(game_folder): return False, "Game not installed"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_subdir = os.path.join(self.folder_backups, game_name)
        os.makedirs(backup_subdir, exist_ok=True)
        backup_zip_path = os.path.join(backup_subdir, f"save_backup_{timestamp}.zip")
        save_extensions = ('.sav', '.gam', '.dat', '.cfg', '.hi', '.scr', '.srm')
        files_to_backup = []
        for root, _, files in os.walk(game_folder):
            for f in files:
                lower = f.lower()
                if lower.endswith(save_extensions) or lower.startswith("save"):
                    full_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_path, game_folder)
                    files_to_backup.append((full_path, rel_path))
        if not files_to_backup:
            return False, "No save files found (tried .sav, .gam, .dat...)"
        try:
            with zipfile.ZipFile(backup_zip_path, 'w') as z:
                for full, rel in files_to_backup:
                    z.write(full, rel)
            return True, f"Backed up {len(files_to_backup)} files to:\n{os.path.basename(backup_zip_path)}"
        except Exception as e:
            return False, str(e)
    def read_dosbox_param(self, conf_path, section, key):
        if not os.path.exists(conf_path): return ""
        try:
            with open(conf_path, 'r') as f:
                in_section = False
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(("#", ";", "%")): continue
                    if line.startswith("[") and line.endswith("]"):
                        curr = line[1:-1].strip().lower()
                        in_section = (curr == section.lower())
                    elif in_section and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip().lower() == key.lower(): return v.strip()
        except: pass
        return ""
    def detect_protected_mode(self, game_name):
        zip_input = game_name + ".zip" if not game_name.endswith(".zip") else game_name
        game_folder = self.find_game_folder(zip_input)
        if not os.path.exists(game_folder): return False
        target_files = {'dos4gw.exe', 'dos32.exe'}
        for root, _, files in os.walk(game_folder):
            for f in files:
                if f.lower() in target_files: return True
        return False
    def write_game_config(self, game_name, config_data):
        game_folder = os.path.join(self.installed_dir, game_name)
        conf_path = os.path.join(game_folder, "dosbox.conf")
        legacy_autoexec = []
        if os.path.exists(conf_path):
            try:
                with open(conf_path, 'r') as f:
                    lines = f.readlines()
                    in_backup = False
                    for line in lines:
                        if "# --- ORIGINAL CONFIGURATION" in line: in_backup = True; continue
                        if "# --- LAUNCHER GENERATED" in line: in_backup = False; continue
                        if in_backup: legacy_autoexec.append(line)
            except: pass
        is_protected = self.detect_protected_mode(game_name)
        content = []
        for section in ['sdl', 'render', 'dosbox', 'dos', 'sblaster', 'gus', 'speaker', 'midi', 'mixer']:
            if section in config_data:
                content.append(f"[{section}]")
                for k, v in config_data.get(section, {}).items():
                     content.append(f"{k}={v}")
                content.append("")
        content.append("[cpu]")
        content.append(f"core={config_data['cpu']['core']}")
        content.append(f"cputype={config_data['cpu']['cputype']}")
        if is_protected:
            val = config_data['cpu'].get('cycles_protected', '60000')
            content.append(f"cycles={val}") # Correction: DOSBox-X uses 'cycles', not 'cpu_cycles_protected'
        else:
            val = config_data['cpu'].get('cycles', '3000')
            content.append(f"cycles={val}")
        content.append("")
        content.append("[autoexec]")
        if legacy_autoexec:
            content.append("# --- ORIGINAL CONFIGURATION (BACKUP) ---")
            content.extend([l.strip() for l in legacy_autoexec])
        content.append("# --- LAUNCHER GENERATED CONFIG START ---")
        content.append("@echo off")
        drives_c = os.path.join(game_folder, "drives", "c")
        mount_cmd = 'mount C "."'
        is_standardized = False
        if os.path.exists(drives_c):
            mount_cmd = 'mount C ".\\drives\\c"'
            is_standardized = True
        content.append(mount_cmd)
        cd_folder = os.path.join(game_folder, "cd")
        if os.path.exists(cd_folder):
            valid_exts = ('.cue', '.iso', '.img', '.ccd', '.mdf')
            images = [f for f in sorted(os.listdir(cd_folder)) if f.lower().endswith(valid_exts)]
            if images:
                img_paths = [f'".\\cd\\{img}"' for img in images]
                content.append(f'imgmount D {" ".join(img_paths)} -t iso')
        content.append("C:")
        exe_map = self.load_exe_map(game_name)
        main_exe_rel = None
        for rel, info in exe_map.items():
            if info.get("role") == ROLE_MAIN:
                main_exe_rel = rel
                break
        if not main_exe_rel:
            all_exes = self.scan_game_executables(game_name + ".zip")
            if len(all_exes) == 1: main_exe_rel = all_exes[0]
        if main_exe_rel:
            path_parts = main_exe_rel.replace("\\", "/").split("/")
            if is_standardized and len(path_parts) > 2 and path_parts[0].lower() == "drives" and path_parts[1].lower() == "c":
                path_parts = path_parts[2:]
            if len(path_parts) > 1:
                content.append(f"cd {'\\'.join(path_parts[:-1])}")
            run_cmd = path_parts[-1]
            extra = config_data.get('extra', {})
            if extra.get('loadfix', False):
                size = extra.get('loadfix_size', '0')
                if size == '0': content.append("loadfix")
                else: content.append(f"loadfix -{size}")
            if extra.get('loadhigh', False): run_cmd = f"lh {run_cmd}"
            content.append(run_cmd)
            content.append("exit")
        else:
            content.append("cls")
            content.append("echo No Main Game configured.")
        content.append("# --- LAUNCHER GENERATED CONFIG END ---")
        with open(conf_path, 'w') as f:
            f.write("\n".join(content))
    def get_game_images(self, game_name):
        target_dir = self.get_screens_dir(game_name)
        images = []
        if os.path.exists(target_dir):
            for f in os.listdir(target_dir):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    images.append(os.path.join(target_dir, f))
        return sorted(images)
    def get_next_screenshot_name(self, game_name):
        target_dir = self.get_screens_dir(game_name)
        existing = os.listdir(target_dir)
        max_idx = -1
        pattern = re.compile(rf"^{re.escape(game_name)}(\d+)\.png$", re.IGNORECASE)
        for f in existing:
            m = pattern.match(f)
            if m:
                try:
                    idx = int(m.group(1))
                    if idx > max_idx: max_idx = idx
                except: pass
        return f"{game_name}{max_idx + 1:03d}.png"
    def _migrate_legacy_screens(self):
        if not os.path.exists(self.folder_screens): return
        game_files, _ = self.get_game_list()
        game_names = [os.path.splitext(g)[0] for g in game_files]
        game_names.sort(key=len, reverse=True)
        for f in os.listdir(self.folder_screens):
            src_path = os.path.join(self.folder_screens, f)
            if not os.path.isfile(src_path): continue
            if not f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')): continue
            matched_game = None
            for g in game_names:
                if f.lower().startswith(g.lower()):
                    matched_game = g
                    break
            if matched_game:
                target_dir = self.get_screens_dir(matched_game)
                new_name = self.get_next_screenshot_name(matched_game)
                dst_path = os.path.join(target_dir, new_name)
                try:
                    if not f.lower().endswith(".png") and HAS_PILLOW:
                        try:
                            img = Image.open(src_path)
                            img.save(dst_path, "PNG")
                            os.remove(src_path)
                        except: pass
                    else: shutil.move(src_path, dst_path)
                except: pass
    def rename_game(self, old_name, new_name):
        if old_name == new_name: return True
        old_zip = os.path.join(self.zipped_dir, old_name + ".zip")
        new_zip = os.path.join(self.zipped_dir, new_name + ".zip")
        if os.path.exists(old_zip) and not os.path.exists(new_zip):
            try: os.rename(old_zip, new_zip)
            except: pass
        old_folder = os.path.join(self.installed_dir, old_name)
        new_folder = os.path.join(self.installed_dir, new_name)
        if os.path.exists(old_folder):
            try: os.rename(old_folder, new_folder)
            except: return False
        for f in os.listdir(self.folder_info):
            if f.startswith(old_name + "."):
                ext = f[len(old_name):]
                src = os.path.join(self.folder_info, f)
                dst = os.path.join(self.folder_info, new_name + ext)
                try: os.rename(src, dst)
                except: pass
        old_screen_dir = os.path.join(self.folder_screens, old_name)
        new_screen_dir = os.path.join(self.folder_screens, new_name)
        if os.path.exists(old_screen_dir):
            try: 
                os.rename(old_screen_dir, new_screen_dir)
                for img in os.listdir(new_screen_dir):
                    if img.lower().startswith(old_name.lower()):
                         suffix = img[len(old_name):]
                         new_img_name = new_name + suffix
                         os.rename(os.path.join(new_screen_dir, img), os.path.join(new_screen_dir, new_img_name))
            except: pass
        return True
    def install_game(self, zip_name):
        target = self.find_game_folder(zip_name)
        zip_path = os.path.join(self.zipped_dir, zip_name)
        if not os.path.exists(zip_path): raise Exception("ZIP not found")
        try:
            if not os.path.exists(target): os.makedirs(target)
            with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(target)
            items = os.listdir(target)
            if len(items) == 1 and os.path.isdir(os.path.join(target, items[0])):
                sub = os.path.join(target, items[0])
                for f in os.listdir(sub):
                    shutil.move(os.path.join(sub, f), os.path.join(target, f))
                os.rmdir(sub)
            for item in os.listdir(target):
                if item.lower() == "dosbox" and os.path.isdir(os.path.join(target, item)):
                    shutil.rmtree(os.path.join(target, item), ignore_errors=True)
            default_config = {
                'sdl': {'output': 'opengl', 'fullscreen': 'false', 'windowresolution': 'default', 'fullresolution': 'desktop'},
                'render': {'glshader': 'none', 'integer_scaling': 'false'},
                'cpu': {'core': 'auto', 'cputype': 'auto', 'cycles': '3000', 'cycles_protected': '60000'},
                'dosbox': {'memsize': '16'},
                'dos': {'xms': 'true', 'ems': 'true', 'umb': 'true'},
                'sblaster': {'sbtype': 'sb16', 'irq': '7', 'dma': '1', 'hdma': '5', 'oplmode': 'auto'},
                'gus': {'gus': 'false'},
                'speaker': {'pcspeaker': 'impulse', 'tandy': 'auto', 'lpt_dac': 'none'}
            }
            self.write_game_config(os.path.splitext(zip_name)[0], default_config)
            return True
        except Exception as e:
            shutil.rmtree(target, ignore_errors=True)
            raise e
    def uninstall_game(self, zip_name):
        path = self.find_game_folder(zip_name)
        if os.path.exists(path):
            shutil.rmtree(path, onerror=remove_readonly)
        name = os.path.splitext(zip_name)[0]
        for f in os.listdir(self.folder_info):
            if f.startswith(name + "."):
                try: os.remove(os.path.join(self.folder_info, f))
                except: pass
    def organize_game_structure(self, current_zip_name, new_full_name, dos_name_8char=None):
        old_folder = self.find_game_folder(current_zip_name)
        if not os.path.exists(old_folder): return None
        current_name_no_zip = os.path.splitext(current_zip_name)[0]
        if new_full_name != current_name_no_zip:
            if not self.rename_game(current_name_no_zip, new_full_name):
                return None
        game_folder = os.path.join(self.installed_dir, new_full_name)
        path_cd = os.path.join(game_folder, "cd")
        path_docs = os.path.join(game_folder, "docs")
        path_drives = os.path.join(game_folder, "drives")
        path_c = os.path.join(path_drives, "c")
        for p in [path_cd, path_docs, path_c]:
            os.makedirs(p, exist_ok=True)
        direct_iso_ext = ('.iso', '.img', '.ccd', '.mdf', '.mds')
        for f in os.listdir(game_folder):
            src = os.path.join(game_folder, f)
            if os.path.isfile(src) and f.lower().endswith(direct_iso_ext):
                shutil.move(src, os.path.join(path_cd, f))
        for f in os.listdir(game_folder):
            if f.lower().endswith(".cue"):
                src_cue = os.path.join(game_folder, f)
                shutil.move(src_cue, os.path.join(path_cd, f))
                base_name = os.path.splitext(f)[0]
                for candidate in os.listdir(game_folder):
                    if candidate.lower() == (base_name + ".bin").lower():
                        src_bin = os.path.join(game_folder, candidate)
                        shutil.move(src_bin, os.path.join(path_cd, candidate))
        excluded = ['cd', 'docs', 'drives', 'dosbox.conf', 'capture', 'screens']
        items_to_move = []
        for f in os.listdir(game_folder):
            if f not in excluded: items_to_move.append(f)
        final_dos_name = dos_name_8char
        if not final_dos_name:
            if len(items_to_move) == 1 and os.path.isdir(os.path.join(game_folder, items_to_move[0])):
                candidate_name = items_to_move[0]
                if len(candidate_name) <= 8 and " " not in candidate_name:
                    final_dos_name = candidate_name.upper()
            if not final_dos_name:
                final_dos_name = re.sub(r'[^a-zA-Z0-9]', '', new_full_name)[:8].upper()
        dos_game_dir = os.path.join(path_c, final_dos_name)
        if items_to_move:
            if len(items_to_move) == 1 and os.path.isdir(os.path.join(game_folder, items_to_move[0])):
                 folder_name = items_to_move[0]
                 src_folder = os.path.join(game_folder, folder_name)
                 if folder_name.upper() != final_dos_name.upper():
                     shutil.move(src_folder, dos_game_dir)
                 else:
                     shutil.move(src_folder, path_c)
            else:
                if not os.path.exists(dos_game_dir):
                    os.makedirs(dos_game_dir)
                for item in items_to_move:
                    src = os.path.join(game_folder, item)
                    dst = os.path.join(dos_game_dir, item)
                    shutil.move(src, dst)
        default_config = {
                'sdl': {'output': 'opengl', 'fullscreen': 'false', 'windowresolution': 'default', 'fullresolution': 'desktop'},
                'render': {'glshader': 'none', 'integer_scaling': 'false'},
                'cpu': {'core': 'auto', 'cputype': 'auto', 'cycles': '3000', 'cycles_protected': '60000'},
                'dosbox': {'memsize': '16'},
                'dos': {'xms': 'true', 'ems': 'true', 'umb': 'true'},
                'sblaster': {'sbtype': 'sb16', 'irq': '7', 'dma': '1', 'hdma': '5', 'oplmode': 'auto'},
                'gus': {'gus': 'false'},
                'speaker': {'pcspeaker': 'impulse', 'tandy': 'auto', 'lpt_dac': 'none'}
        }
        self.write_game_config(new_full_name, default_config)
        return new_full_name + ".zip"
    def launch_dosbox_prompt(self, zip_name):
        name = os.path.splitext(zip_name)[0]
        folder = os.path.join(self.installed_dir, name)
        db_exe = self.get_dosbox_exe(name)
        if not db_exe or not os.path.exists(db_exe): raise Exception("DOSBox EXE not configured!")
        self._launch_custom_mode(folder, None, [db_exe], mode="prompt", game_name=name)
    def _launch_custom_mode(self, game_folder, target_file, db_command_args, mode="exe", game_name=None):
        def thread_target():
            org_conf = os.path.join(game_folder, "dosbox.conf")
            bak_conf = os.path.join(game_folder, "dosbox.conf.bak")
            start_time = time.time()
            try:
                if os.path.exists(org_conf):
                    if os.path.exists(bak_conf): os.remove(bak_conf)
                    os.rename(org_conf, bak_conf)
                
                mount_cmd = 'mount C "."'
                drives_c = os.path.join(game_folder, "drives", "c")
                if os.path.exists(drives_c): mount_cmd = 'mount C ".\\drives\\c"'
                
                img_cmd = ""
                cd_dir = os.path.join(game_folder, "cd")
                if os.path.exists(cd_dir):
                    valid_exts = ('.cue', '.iso', '.img', '.ccd', '.mdf')
                    images = [f for f in sorted(os.listdir(cd_dir)) if f.lower().endswith(valid_exts)]
                    if images:
                        img_paths = [f'".\\cd\\{img}"' for img in images]
                        img_cmd = f'imgmount D {" ".join(img_paths)} -t iso'
                lines = []
                try:
                    with open(bak_conf, 'r') as f:
                        for line in f:
                            if '[autoexec]' in line.lower(): break
                            lines.append(line)
                except: pass
                autoexec = ["\n[autoexec]", "@echo off", mount_cmd, img_cmd, "C:"]
                if mode == "exe" and target_file:
                    dos_path = target_file
                    if os.path.exists(drives_c):
                        prefix = os.path.join("drives", "c")
                        if target_file.startswith(prefix):
                            dos_path = target_file[len(prefix):].lstrip(os.sep)
                    dos_dir = os.path.dirname(dos_path)
                    dos_exe = os.path.basename(dos_path)
                    if dos_dir: autoexec.append(f"cd {dos_dir}")
                    autoexec.append(f"{dos_exe}")
                    autoexec.append("exit")
                elif mode == "prompt":
                    autoexec.append("cls")
                    auto.append("echo DOSBox Command Mode")
                    autoexec.append("echo -------------------")
                with open(org_conf, 'w') as f:
                    f.writelines(lines)
                    f.write("\n".join(autoexec))
                
                final_command = db_command_args + ["-conf", org_conf]
                subprocess.call(final_command, cwd=game_folder, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                for f in ["stdout.txt", "stderr.txt"]:
                    fp = os.path.join(game_folder, f)
                    if os.path.exists(fp):
                        try: os.remove(fp)
                        except: pass
                if game_name:
                    self.import_screenshots_from_capture(game_folder, game_name, start_time)
            except Exception as e: print(f"Run Error: {e}")
            finally:
                if os.path.exists(org_conf): 
                    try: os.remove(org_conf)
                    except: pass
                if os.path.exists(bak_conf):
                    try: os.rename(bak_conf, org_conf)
                    except: pass
        threading.Thread(target=thread_target, daemon=True).start()
    def import_screenshots_from_capture(self, game_folder, game_name, start_time):
        paths_to_check = []
        conf_capture = self.settings.get("capture_dir")
        if conf_capture:
            if os.path.isabs(conf_capture):
                if os.path.exists(conf_capture):
                    paths_to_check.append((conf_capture, True))
            else:
                local_path = os.path.join(game_folder, conf_capture)
                if os.path.exists(local_path):
                     paths_to_check.append((local_path, False))
        local_cap = os.path.join(game_folder, "capture")
        if os.path.exists(local_cap) and local_cap not in [p[0] for p in paths_to_check]:
            paths_to_check.append((local_cap, False)) 
        paths_to_check.append((game_folder, True))
        target_dir = self.get_screens_dir(game_name)
        for source_dir, check_time in paths_to_check:
            if not os.path.exists(source_dir): continue
            for f in os.listdir(source_dir):
                if f.lower().endswith(".png"):
                    src_path = os.path.join(source_dir, f)
                    if os.path.dirname(src_path) == target_dir: continue
                    if check_time:
                        ctime = os.path.getmtime(src_path)
                        if ctime < start_time: continue
                    new_name = self.get_next_screenshot_name(game_name)
                    dst_path = os.path.join(target_dir, new_name)
                    try:
                        time.sleep(0.1)
                        shutil.move(src_path, dst_path)
                    except: pass
    def open_config_in_notepad(self, zip_name):
        name = os.path.splitext(zip_name)[0]
        conf_path = os.path.join(self.installed_dir, name, "dosbox.conf")
        if os.path.exists(conf_path):
            try: os.startfile(conf_path) 
            except AttributeError:
                if os.name == 'posix': subprocess.call(['xdg-open', conf_path])
                else: subprocess.call(['notepad', conf_path])