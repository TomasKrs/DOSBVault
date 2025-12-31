import os
import shutil
import subprocess
import zipfile
import json
import threading
import csv
from tkinter import messagebox
import re
import time
import tempfile
from datetime import datetime
import copy
from configparser import ConfigParser
try:
    import py7zr
    HAS_7ZIP = True
except ImportError:
    HAS_7ZIP = False

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

from . import constants
from .utils import remove_readonly
from .components.offline_db import OfflineDatabase

class DOSBoxConfigParser:
    """
    Parses DOSBox configuration files, preserving structure and comments.
    Supports cascading configurations.
    """
    def __init__(self):
        self.sections = {} # section -> { key: value }
        self.raw_lines = [] # List of dicts: {type, val, section, key, original_key}

    def parse(self, content):
        self.sections = {}
        self.raw_lines = []
        current_section = None
        
        for line in content.splitlines():
            s = line.strip()
            line_obj = {'val': line}
            
            if not s:
                line_obj['type'] = 'empty'
            elif s.startswith(('#', '%', ';')):
                line_obj['type'] = 'comment'
            elif s.startswith('[') and s.endswith(']'):
                current_section = s[1:-1].lower()
                line_obj['type'] = 'section'
                line_obj['name'] = current_section
                if current_section not in self.sections:
                    self.sections[current_section] = {}
            elif '=' in s and current_section:
                key, val = s.split('=', 1)
                key = key.strip().lower()
                val = val.strip()
                line_obj['type'] = 'key'
                line_obj['section'] = current_section
                line_obj['key'] = key
                line_obj['value'] = val
                line_obj['original_key'] = s.split('=')[0].strip()
                self.sections[current_section][key] = val
            else:
                line_obj['type'] = 'unknown'
                
            self.raw_lines.append(line_obj)

    def get(self, section, key, default=None):
        return self.sections.get(section.lower(), {}).get(key.lower(), default)

    def get_section(self, section):
        return self.sections.get(section.lower(), {})

    def set(self, section, key, value):
        section = section.lower()
        key = key.lower()
        if section not in self.sections:
            self.sections[section] = {}
            # Add section to raw lines
            self.raw_lines.append({'type': 'empty', 'val': ''})
            self.raw_lines.append({'type': 'section', 'name': section, 'val': f"[{section}]"})
            
        self.sections[section][key] = value
        
        # Update raw lines
        found = False
        for item in self.raw_lines:
            if item.get('type') == 'key' and item.get('section') == section and item.get('key') == key:
                item['value'] = value
                item['val'] = f"{item['original_key']} = {value}"
                found = True
                break
        
        if not found:
            # Append to section
            # Find last line of section
            last_idx = -1
            for i, item in enumerate(self.raw_lines):
                if item.get('type') == 'section' and item.get('name') == section:
                    last_idx = i
                elif item.get('section') == section:
                    last_idx = i
            
            if last_idx != -1:
                self.raw_lines.insert(last_idx + 1, {'type': 'key', 'section': section, 'key': key, 'value': value, 'original_key': key, 'val': f"{key} = {value}"})
            else:
                # Should not happen if we added section above
                pass

    def to_string(self):
        return "\n".join(item['val'] for item in self.raw_lines)

class GameLogic:
    def __init__(self, settings):
        self.settings = settings
        self.base_dir = os.getcwd()
        self.info_dir = os.path.join(self.base_dir, "info")
        self.screens_dir = os.path.join(self.base_dir, "screens") # Kept for backward compatibility but logic uses database path
        self.export_dir = os.path.join(self.base_dir, "export")
        self.import_dir = os.path.join(self.base_dir, "import")
        # os.makedirs(self.info_dir, exist_ok=True) # Handled by Start Wizard
        # os.makedirs(self.screens_dir, exist_ok=True)
        # os.makedirs(self.export_dir, exist_ok=True)
        # os.makedirs(self.import_dir, exist_ok=True)
        self.db = OfflineDatabase(os.path.join(self.base_dir, "database", "DOSmetainfo.csv"))
        self._run_migration()
        self.HAS_7ZIP = HAS_7ZIP

    @property
    def zipped_dir(self): return os.path.join(self.base_dir, self.settings.get("zip_dir", "archive"))
    @property
    def installed_dir(self): return os.path.join(self.base_dir, self.settings.get("root_dir", "games"))
    
    @property
    def default_dosbox_exe(self):
        installations = self.settings.get("dosbox_installations", [])
        for item in installations:
            if item.get("default"): return item.get("path", "")
        return ""

    def check_dosbox_exists(self):
        """Checks if a valid DOSBox executable exists in the DOSBox folder."""
        dosbox_root = os.path.join(self.base_dir, "DOSBox")
        if not os.path.exists(dosbox_root):
            try:
                os.makedirs(dosbox_root)
            except: pass
            return False
            
        for root, dirs, files in os.walk(dosbox_root):
            for file in files:
                if file.lower().endswith(".exe"):
                    # Simple check, maybe check for 'dosbox' in name?
                    # User said "dosbox.exe a podobne"
                    if "dosbox" in file.lower():
                        return True
        return False

    def is_portable(self):
        """Checks if the installation is portable (all paths relative)."""
        # We assume it is portable if we are running from the base dir and using default relative paths
        # But user might have changed paths in settings.
        # For now, let's just check if the configured paths are inside base_dir
        
        def is_subpath(path, parent):
            try:
                rel = os.path.relpath(path, parent)
                return not rel.startswith("..") and not os.path.isabs(rel)
            except: return False

        # Check zipped, games, DOSBox
        if not is_subpath(self.zipped_dir, self.base_dir): return False
        if not is_subpath(self.installed_dir, self.base_dir): return False
        
        # Check DOSBox installations
        installations = self.settings.get("dosbox_installations", [])
        for inst in installations:
            if not is_subpath(inst.get("path", ""), self.base_dir): return False
            
        return True

    def prepare_import(self, source_path, is_zip=False):
        """
        Prepares a game for import.
        1. Creates a temp folder in games/!TEMP_<timestamp>
        2. Extracts ZIP or copies folder there.
        3. Drills down to find the actual game root.
        4. Returns (temp_path, suggested_msdos_name, has_subfolders)
        """
        timestamp = int(time.time())
        temp_name = f"!TEMP_{timestamp}"
        temp_path = os.path.join(self.installed_dir, temp_name)
        os.makedirs(temp_path, exist_ok=True)
        
        try:
            if is_zip:
                if source_path.lower().endswith('.7z'):
                    if not HAS_7ZIP:
                        raise Exception("py7zr module not found. Please install it to support 7z files (pip install py7zr).")
                    with py7zr.SevenZipFile(source_path, mode='r') as z:
                        z.extractall(path=temp_path)
                else:
                    with zipfile.ZipFile(source_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_path)
            else:
                # Copy folder content
                # shutil.copytree requires dest to not exist usually, or dirs_exist_ok=True
                # But we want to copy CONTENT of source_path to temp_path
                for item in os.listdir(source_path):
                    s = os.path.join(source_path, item)
                    d = os.path.join(temp_path, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)
        except Exception as e:
            # Cleanup on fail
            shutil.rmtree(temp_path, ignore_errors=True)
            raise e
            
        # Drill down logic
        current_path = temp_path
        suggested_name = "GAME"
        
        # Loop to drill down until we find a folder with multiple items or files
        while True:
            items = os.listdir(current_path)
            # Filter out system files/folders if needed
            items = [i for i in items if i.lower() not in ['.ds_store', 'thumbs.db', '__macosx']]
            
            if not items: break # Empty folder
            
            if len(items) == 1:
                item_path = os.path.join(current_path, items[0])
                if os.path.isdir(item_path):
                    # It's a single directory, drill down
                    suggested_name = items[0] # Use this folder name as suggestion
                    current_path = item_path
                    continue
            
            # If we are here, it means we have either multiple items or a single file
            # This is our root.
            break
            
        # If we drilled down, we should move everything up to temp_path?
        # Or just return this path as the "game root"?
        # The user said: "zistime nazov priecinku, v ktorom sme a to moze tvorit MSDOS nazov priecinka"
        # "Temp sa tym padom mozem premenovat na priecinok, s ktorym budeme dalej pracovat."
        
        # If we are deep, move content up to temp_path so we can rename temp_path later easily
        if current_path != temp_path:
            # Move content of current_path to temp_path
            # We need to be careful not to overwrite.
            # Actually, if we drilled down, current_path is inside temp_path.
            # We want current_path to BECOME the game folder.
            # So we can move current_path to installed_dir/NEW_TEMP and delete old temp_path?
            
            new_temp_path = os.path.join(self.installed_dir, f"!TEMP_{timestamp}_ROOT")
            
            # Move the deep folder to the new temp location
            # Note: current_path is the full path to the deep folder
            shutil.move(current_path, new_temp_path)
            
            # Remove the old wrapper structure
            # We need to be careful. temp_path contains current_path.
            # If we moved current_path out, temp_path should be empty or contain empty folders.
            shutil.rmtree(temp_path, ignore_errors=True) 
            
            temp_path = new_temp_path
            
        # Sanitize suggested name for MSDOS (8 chars, no spaces)
        suggested_msdos = re.sub(r'[^a-zA-Z0-9]', '', suggested_name).upper()[:8]
        if not suggested_msdos: suggested_msdos = "GAME"
        
        return temp_path, suggested_msdos

    def get_dosbox_conf_content(self, dosbox_path=None):
        if not dosbox_path: dosbox_path = self.default_dosbox_exe
        if not dosbox_path: return ""
        
        base_dir = os.path.dirname(dosbox_path)
        # Try to find a .conf file
        conf_files = [f for f in os.listdir(base_dir) if f.endswith('.conf')]
        # Prefer dosbox.conf, then dosbox-staging.conf, then dosbox-x.conf
        for name in ['dosbox.conf', 'dosbox-staging.conf', 'dosbox-x.conf']:
             if name in conf_files:
                 try:
                     with open(os.path.join(base_dir, name), 'r') as f: return f.read()
                 except: pass
        
        # If not found, return empty or generic
        return ""
        
    def get_default_dosbox_conf_path(self, dosbox_path=None):
        """Returns the absolute path to the default config file for the given DOSBox executable."""
        if not dosbox_path: dosbox_path = self.default_dosbox_exe
        if not dosbox_path: return None
        
        base_dir = os.path.dirname(dosbox_path)
        exe_name = os.path.basename(dosbox_path).lower()
        conf_files = [f for f in os.listdir(base_dir) if f.endswith('.conf')]
        
        # Determine priority based on exe name
        priority = ['dosbox.conf'] # Default priority
        if 'staging' in exe_name:
            priority = ['dosbox-staging.conf', 'dosbox.conf']
        elif 'dosbox-x' in exe_name:
            priority = ['dosbox-x.conf', 'dosbox.conf']
            
        for name in priority:
             if name in conf_files:
                 return os.path.join(base_dir, name)
        
        # Fallback to any .conf
        if conf_files:
            return os.path.join(base_dir, conf_files[0])
            
        return None

    def _get_game_json_path(self, game_name): return os.path.join(self.base_dir, "database", "games_datainfo", game_name, f"{game_name}.json")

    def get_game_details(self, game_name):
        defaults = copy.deepcopy(constants.DEFAULT_GAME_DETAILS)
        defaults['title'] = game_name
        path = self._get_game_json_path(game_name)

        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if isinstance(value, dict) and key in defaults and isinstance(defaults[key], dict):
                            defaults[key].update(value)
                        else:
                            defaults[key] = value
            except (json.JSONDecodeError, IOError): pass
        return defaults

    def save_game_details(self, game_name, data):
        path = self._get_game_json_path(game_name)
        game_datainfo_dir = os.path.dirname(path)
        os.makedirs(game_datainfo_dir, exist_ok=True)
        
        # Ensure subfolders exist
        os.makedirs(os.path.join(game_datainfo_dir, "confs"), exist_ok=True)
        os.makedirs(os.path.join(game_datainfo_dir, "screenshots"), exist_ok=True)
        
        try:
            with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)
            return True
        except IOError: return False

    def rename_game(self, old_name, new_name):
        if not new_name: return None, "No name change."
        
        # Check if names are identical (case-sensitive)
        if old_name == new_name: return None, "No name change."
        
        old_game_dir = self.find_game_folder(old_name)
        new_game_dir = self.find_game_folder(new_name)
        
        # Check if target exists, but allow if it's the same folder (case-insensitive rename on Windows)
        if os.path.exists(new_game_dir):
            if os.path.normpath(old_game_dir).lower() != os.path.normpath(new_game_dir).lower():
                return None, f"A folder named '{new_name}' already exists."
            # If they are the same path (case-insensitive), we proceed with rename to update case
        
        if os.path.exists(old_game_dir): 
            try:
                os.rename(old_game_dir, new_game_dir)
            except OSError:
                # If rename fails (e.g. same name different case on some filesystems), we might need temp rename
                # But usually os.rename handles case change on Windows fine if it's the same inode
                pass

        # Rename metadata folder and file
        old_meta_dir = os.path.join(self.base_dir, "database", "games_datainfo", old_name)
        new_meta_dir = os.path.join(self.base_dir, "database", "games_datainfo", new_name)
        
        if os.path.exists(new_meta_dir) and os.path.normpath(old_meta_dir).lower() != os.path.normpath(new_meta_dir).lower():
             shutil.rmtree(new_meta_dir, onerror=remove_readonly)
        
        if os.path.exists(old_meta_dir):
            os.rename(old_meta_dir, new_meta_dir)
            # Rename the JSON file inside
            old_json_path = os.path.join(new_meta_dir, f"{old_name}.json")
            new_json_path = os.path.join(new_meta_dir, f"{new_name}.json")
            if os.path.exists(old_json_path):
                os.rename(old_json_path, new_json_path)
        
        # Rename Archive file if it exists (support .zip and .7z)
        for ext in ['.zip', '.7z']:
            old_archive = os.path.join(self.zipped_dir, f"{old_name}{ext}")
            new_archive = os.path.join(self.zipped_dir, f"{new_name}{ext}")
            
            if os.path.exists(old_archive) and not os.path.exists(new_archive):
                try:
                    os.rename(old_archive, new_archive)
                except Exception as e:
                    print(f"Could not rename archive {ext}: {e}")
        
        # Update title in JSON
        try:
            details = self.get_game_details(new_name)
            details['title'] = new_name
            self.save_game_details(new_name, details)
        except Exception as e:
            print(f"Could not update title in JSON: {e}")
                
        return new_name, None

    def uninstall_game(self, zip_name):
        game_name = os.path.splitext(zip_name)[0]
        
        # Offer backup
        if messagebox.askyesno("Uninstall", "Do you want to keep save data (backup changes)?"):
            self.backup_save_data(game_name)
            
        install_path = self.find_game_folder(game_name)
        if os.path.isdir(install_path): shutil.rmtree(install_path, onerror=remove_readonly)
        
        # Remove manifest
        manifest_path = os.path.join(self.base_dir, "info", f"{game_name}.manifest")
        if os.path.exists(manifest_path): os.remove(manifest_path)

    def install_game(self, zip_name, new_folder_name, source_path=None, progress_callback=None):
        if source_path:
            zip_path = source_path
        else:
            # Fallback logic if source_path not provided (legacy calls)
            # Try zip then 7z
            base = os.path.splitext(zip_name)[0]
            p1 = os.path.join(self.zipped_dir, f"{base}.zip")
            p2 = os.path.join(self.zipped_dir, f"{base}.7z")
            if os.path.exists(p1): zip_path = p1
            elif os.path.exists(p2): zip_path = p2
            else: zip_path = os.path.join(self.zipped_dir, zip_name) # Try as is
            
        if not os.path.exists(zip_path): raise Exception("Archive file not found.")
        install_folder = self.find_game_folder(new_folder_name)
        if os.path.exists(install_folder): raise Exception(f"A folder named '{new_folder_name}' already exists.")
        os.makedirs(install_folder, exist_ok=True)
        
        if zip_path.lower().endswith('.7z'):
            if not HAS_7ZIP: raise Exception("py7zr module not found.")
            with py7zr.SevenZipFile(zip_path, mode='r') as z:
                if progress_callback:
                    # py7zr doesn't support progress callback easily for extractall
                    # We can iterate and extract
                    all_files = z.getnames()
                    total = len(all_files)
                    z.extractall(path=install_folder)
                    # Just update to 100% as we can't track per file easily without manual extraction loop which is slower
                    progress_callback(total, total)
                else:
                    z.extractall(path=install_folder)
        else:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                if progress_callback:
                    file_list = zip_ref.namelist()
                    total = len(file_list)
                    for i, file in enumerate(file_list):
                        zip_ref.extract(file, install_folder)
                        if i % 10 == 0: # Update every 10 files to avoid UI lag
                            progress_callback(i + 1, total)
                    progress_callback(total, total)
                else:
                    zip_ref.extractall(install_folder)
            
        new_game_name = os.path.basename(install_folder)
        
        # Set default Reference Config for new game
        try:
            default_conf_path = self.get_default_dosbox_conf_path()
            if default_conf_path:
                # Store relative path if possible
                try:
                    rel_path = os.path.relpath(default_conf_path, self.base_dir)
                    # If rel_path starts with .., it's outside base_dir, so keep absolute
                    if rel_path.startswith(".."):
                        final_path = default_conf_path
                    else:
                        final_path = rel_path
                except ValueError:
                    final_path = default_conf_path
                    
                details = self.get_game_details(new_game_name)
                details['reference_conf'] = final_path
                self.save_game_details(new_game_name, details)
        except Exception as e:
            print(f"Error setting default reference config: {e}")

        # Attempt to import settings from dosbox.conf if no json exists
        self.import_from_dosbox_conf(new_game_name)
        
        # Move/Rename the source ZIP to zipped folder if it's not already there
        # Logic for moving is tricky with 7z support.
        # If we installed from an external file, we might want to move it.
        # But usually install_game is called on existing library items.
        # If source_path is external (not in zipped_dir), we should move it.
        
        if os.path.dirname(os.path.abspath(zip_path)) != os.path.abspath(self.zipped_dir):
             # It's external?
             # Actually, install_game is usually called from library context where file is already in zipped_dir.
             # But if we use "Import" wizard, it calls install_game? No, wizard does its own thing.
             # on_install is called from context menu.
             pass

        # Create manifest for save game tracking
        self.create_install_manifest(new_game_name)
        
        # Check for backups
        self.check_and_restore_backup(new_game_name)

        return new_game_name

    def create_install_manifest(self, game_name):
        game_folder = self.find_game_folder(game_name)
        if not os.path.exists(game_folder): return
        
        manifest = {}
        for root, dirs, files in os.walk(game_folder):
            for file in files:
                path = os.path.join(root, file)
                rel_path = os.path.relpath(path, game_folder)
                try:
                    stat = os.stat(path)
                    manifest[rel_path] = {
                        "size": stat.st_size,
                        "mtime": stat.st_mtime
                    }
                except: pass
        
        manifest_path = os.path.join(self.base_dir, "database", "games_datainfo", game_name, f"{game_name}.manifest")
        try:
            os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f)
        except Exception as e:
            print(f"Failed to create manifest: {e}")

    def backup_save_data(self, game_name):
        manifest_path = os.path.join(self.base_dir, "database", "games_datainfo", game_name, f"{game_name}.manifest")
        if not os.path.exists(manifest_path): return
        
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        except:
            return

        game_folder = self.find_game_folder(game_name)
        changed_files = []
        
        for root, dirs, files in os.walk(game_folder):
            for file in files:
                path = os.path.join(root, file)
                rel_path = os.path.relpath(path, game_folder)
                
                # Check if new or changed
                if rel_path not in manifest:
                    changed_files.append(path)
                else:
                    try:
                        stat = os.stat(path)
                        # Check size or mtime (allow 2 second tolerance for FAT/zip timestamps)
                        if stat.st_size != manifest[rel_path]["size"] or abs(stat.st_mtime - manifest[rel_path]["mtime"]) > 2:
                            changed_files.append(path)
                    except: pass
                        
        if not changed_files: 
            messagebox.showinfo("Backup", "No changes detected.")
            return
        
        # Create archive
        backup_dir = os.path.join(self.base_dir, "archive", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        archive_name = f"{game_name}_{date_str}.save.7z"
        archive_path = os.path.join(backup_dir, archive_name)
        
        try:
            if HAS_7ZIP:
                with py7zr.SevenZipFile(archive_path, 'w') as z:
                    for file in changed_files:
                        rel = os.path.relpath(file, game_folder)
                        z.write(file, rel)
            else:
                # Fallback to zip
                archive_path = archive_path.replace(".7z", ".zip")
                with zipfile.ZipFile(archive_path, 'w') as z:
                    for file in changed_files:
                        rel = os.path.relpath(file, game_folder)
                        z.write(file, rel)
                        
            messagebox.showinfo("Backup Created", f"Save data backed up to:\n{archive_name}")
        except Exception as e:
            messagebox.showerror("Backup Error", f"Failed to create backup: {e}")

    def check_and_restore_backup(self, game_name):
        backup_dir = os.path.join(self.base_dir, "archive", "backups")
        if not os.path.exists(backup_dir): return
        
        # Find backups for this game
        backups = [f for f in os.listdir(backup_dir) if f.startswith(game_name + "_") and (f.endswith(".7z") or f.endswith(".zip"))]
        if not backups: return
        
        # Sort by date (descending)
        backups.sort(reverse=True)
        latest_backup = backups[0]
        
        if messagebox.askyesno("Restore Backup", f"Found a backup for {game_name}:\n{latest_backup}\n\nDo you want to restore it?"):
            archive_path = os.path.join(backup_dir, latest_backup)
            game_folder = self.find_game_folder(game_name)
            
            try:
                if archive_path.endswith(".7z") and HAS_7ZIP:
                    with py7zr.SevenZipFile(archive_path, 'r') as z:
                        z.extractall(path=game_folder)
                else:
                    with zipfile.ZipFile(archive_path, 'r') as z:
                        z.extractall(game_folder)
                messagebox.showinfo("Restore Complete", "Save data restored.")
            except Exception as e:
                messagebox.showerror("Restore Error", f"Failed to restore backup: {e}")

    def _run_migration(self):
        all_games, _ = self.get_game_list(skip_migration=True)
        for zip_name in all_games:
            game_name = os.path.splitext(zip_name)[0]; new_json_path = self._get_game_json_path(game_name)
            if os.path.exists(new_json_path):
                details = self.get_game_details(game_name); needs_saving = False
                if 'developer' in details: details['developers'] = details.pop('developer'); needs_saving = True
                if 'player_score' in details: details.pop('player_score', None); needs_saving = True
                if 'custom_dosbox_exe' in details: details['custom_dosbox_path'] = details.pop('custom_dosbox_exe'); needs_saving = True
                if needs_saving: self.save_game_details(game_name, details)
        
        # Migration for screenshots
        old_screens_root = os.path.join(self.base_dir, "screens")
        if os.path.exists(old_screens_root):
            for item in os.listdir(old_screens_root):
                old_path = os.path.join(old_screens_root, item)
                if os.path.isdir(old_path):
                    # It's a game folder
                    new_path = os.path.join(self.base_dir, "database", "games_datainfo", item, "screenshots")
                    if not os.path.exists(new_path):
                        os.makedirs(new_path, exist_ok=True)
                        # Move content
                        try:
                            for f in os.listdir(old_path):
                                shutil.move(os.path.join(old_path, f), os.path.join(new_path, f))
                            # Remove old dir
                            os.rmdir(old_path)
                        except Exception as e:
                            print(f"Error migrating screenshots for {item}: {e}")
            # Try to remove root if empty
            try:
                os.rmdir(old_screens_root)
            except: pass

    def get_game_list(self, skip_migration=False):
        if not skip_migration and not hasattr(self, '_migration_done'): self._run_migration(); self._migration_done = True
        all_game_basenames = set()
        if self.zipped_dir and os.path.exists(self.zipped_dir):
            for f in os.listdir(self.zipped_dir):
                if f.lower().endswith(('.zip', '.7z')): all_game_basenames.add(os.path.splitext(f)[0])
        installed_games_basenames = set()
        if self.installed_dir and os.path.exists(self.installed_dir):
            for d in os.listdir(self.installed_dir):
                if os.path.isdir(os.path.join(self.installed_dir, d)): installed_games_basenames.add(d)
        all_game_basenames.update(installed_games_basenames)
        
        # We need to return filenames that exist in zipped_dir, or just .zip if only installed
        # The GUI expects a list of IDs. Previously it was just basename.zip.
        # Now it can be basename.7z.
        # If both exist, which one? Or both?
        # The GUI uses ID to check existence.
        # Let's return all valid archive names found, plus virtual .zip names for installed-only games?
        # Actually, the ID system relies on unique IDs.
        # If I have game.zip and game.7z, they are the same game.
        # But the GUI treats ID as the file name.
        # Let's stick to: ID = basename + ".zip" (virtual) if installed only.
        # If archive exists, ID = archive filename.
        # If both exist, we might have a conflict in ID if we just use basename.
        # But wait, the GUI uses `zip_name` as ID.
        
        game_list = []
        for basename in sorted(all_game_basenames):
            # Check for archives
            found_archive = False
            if self.zipped_dir and os.path.exists(self.zipped_dir):
                if os.path.exists(os.path.join(self.zipped_dir, f"{basename}.zip")):
                    game_list.append(f"{basename}.zip")
                    found_archive = True
                if os.path.exists(os.path.join(self.zipped_dir, f"{basename}.7z")):
                    game_list.append(f"{basename}.7z")
                    found_archive = True
            
            if not found_archive and basename in installed_games_basenames:
                # Virtual entry for installed game without archive
                game_list.append(f"{basename}.zip")
                
        return game_list, installed_games_basenames
    
    def toggle_favorite(self, game_name):
        details = self.get_game_details(game_name); details["favorite"] = not details.get("favorite", False)
        self.save_game_details(game_name, details)

    def find_game_folder(self, name): return os.path.join(self.installed_dir, name)
    def get_all_executables(self, name):
        game_folder = self.find_game_folder(name)
        if not game_folder or not os.path.isdir(game_folder): return []
        executables = []
        for root, _, files in os.walk(game_folder):
            for file in files:
                if file.lower().endswith(('.exe', '.com', '.bat')): executables.append(os.path.relpath(os.path.join(root, file), game_folder).replace(os.sep, '/'))
        return sorted(executables)

    def get_mounted_isos(self, game_name):
        game_folder = self.find_game_folder(game_name); cd_folder = os.path.join(game_folder, "cd")
        if not os.path.isdir(cd_folder): return []
        return sorted([f for f in os.listdir(cd_folder) if f.lower().endswith(('.iso', '.cue'))])
    
    def get_game_images(self, name):
        game_screens_dir = os.path.join(self.base_dir, "database", "games_datainfo", name, "screenshots")
        image_extensions = ('.png', '.jpg', '.jpeg', '.gif'); video_extensions = ('.mp4', '.avi', '.mkv'); media_files = []
        if os.path.isdir(game_screens_dir):
            for f in sorted(os.listdir(game_screens_dir)):
                if f.lower().endswith(image_extensions) or f.lower().endswith(video_extensions): media_files.append(os.path.join(game_screens_dir, f))
        return media_files
    
    def get_dosbox_engines(self):
        """
        Returns a list of available DOSBox engines (Staging, X, etc.)
        based on installations in settings.
        """
        installations = self.settings.get("dosbox_installations", [])
        engines = []
        for inst in installations:
            name = inst.get("name", "Unknown")
            path = inst.get("path", "")
            engine_type = "dosbox" # Default
            if "staging" in name.lower() or "staging" in path.lower():
                engine_type = "dosbox-staging"
            elif "dosbox-x" in name.lower() or "dosbox-x" in path.lower():
                engine_type = "dosbox-x"
            
            engines.append({
                "name": name,
                "path": path,
                "type": engine_type
            })
        return engines

    def get_base_config(self, engine_type):
        """
        Returns the content of the base configuration file for the given engine type.
        """
        # Look for reference files in DOSBox folder
        dosbox_root = os.path.join(self.base_dir, "DOSBox")
        
        candidates = []
        if engine_type == "dosbox-staging":
            candidates = ["dosbox-staging.conf", "dosbox-staging.reference.conf"]
        elif engine_type == "dosbox-x":
            candidates = ["dosbox-x.reference.full.conf", "dosbox-x.reference.conf", "dosbox-x.conf"]
        else:
            candidates = ["dosbox.conf"]
            
        for root, dirs, files in os.walk(dosbox_root):
            for f in files:
                if f in candidates:
                    try:
                        with open(os.path.join(root, f), "r", encoding="utf-8") as file:
                            return file.read()
                    except: pass
                    
        # Fallback: Return empty or minimal config
        return ""

    def prepare_launch_configs(self, game_name, engine_type, user_overrides):
        """
        Generates the 3-layer configuration for launching.
        Returns (base_conf_path, game_conf_path, override_conf_path)
        """
        temp_dir = os.path.join(self.base_dir, "database", "games_datainfo", game_name, "confs")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Layer 1: Base Config
        base_content = self.get_base_config(engine_type)
        base_conf_path = os.path.join(temp_dir, "base_engine.conf")
        with open(base_conf_path, "w", encoding="utf-8") as f:
            f.write(base_content)
            
        # Layer 2: Game Static Config
        game_folder = self.find_game_folder(game_name)
        game_conf_path = os.path.join(game_folder, "dosbox.conf")
        
        # Ensure it exists
        if not os.path.exists(game_conf_path):
            self.write_game_config(game_name, None, self.get_game_details(game_name), False)
            
        # Layer 3: User Override Config
        override_conf_path = os.path.join(temp_dir, "user_override.conf")
        parser = DOSBoxConfigParser()
        
        # user_overrides is a dict: { section: { key: value } }
        if user_overrides:
            for section, keys in user_overrides.items():
                for key, value in keys.items():
                    parser.set(section, key, value)
                
        with open(override_conf_path, "w", encoding="utf-8") as f:
            f.write(parser.to_string())
            
        return base_conf_path, game_conf_path, override_conf_path

    def _get_mount_root(self, details, game_folder):
        """
        Determines the mount root (local path mounted as C:) from details.
        """
        # Check for new 'mounts' list
        if "mounts" in details and details["mounts"]:
            for mount in details["mounts"]:
                drive = mount.get("drive", "").lower()
                m_type = mount.get("type", "dir")
                path = mount.get("path", "")
                
                if drive == "c" and m_type == "dir" and path:
                    # Handle multiple paths (semicolon separated), take first
                    paths = [p.strip() for p in path.split(";") if p.strip()]
                    if paths: return paths[0]
        
        # Legacy behavior
        mount_c_path = details.get("mount_c", "")
        if not mount_c_path:
            # Fallback to auto-detection
            drives_c_path = os.path.join(game_folder, "drives", "c")
            if os.path.isdir(drives_c_path):
                mount_c_path = "drives/c"
            else:
                mount_c_path = "."
        return mount_c_path

    def _get_mount_root(self, details, game_folder):
        """
        Determines the mount root (local path mounted as C:) from details.
        """
        # Check for new 'mounts' list
        if "mounts" in details and details["mounts"]:
            for mount in details["mounts"]:
                drive = mount.get("drive", "").lower()
                m_type = mount.get("type", "dir")
                path = mount.get("path", "")
                
                if drive == "c" and m_type == "dir" and path:
                    # Handle multiple paths (semicolon separated), take first
                    paths = [p.strip() for p in path.split(";") if p.strip()]
                    if paths: return paths[0]
        
        # Legacy behavior
        mount_c_path = details.get("mount_c", "")
        if not mount_c_path:
            # Fallback to auto-detection
            drives_c_path = os.path.join(game_folder, "drives", "c")
            if os.path.isdir(drives_c_path):
                mount_c_path = "drives/c"
            else:
                mount_c_path = "."
        return mount_c_path

    def launch_game(self, zip_name, specific_exe=None, force_fullscreen=False, auto_exit=False, dos_prompt_only=False, dosbox_path_override=None, config_override_path=None, details_override=None):
        game_name = os.path.splitext(zip_name)[0]
        details = details_override if details_override else self.get_game_details(game_name)
        
        # Determine Engine and Executable
        # If dosbox_path_override is set, we use it.
        # Otherwise we check details['engine'] and find the matching installation.
        # Or fallback to details['custom_dosbox_path'] or default.
        
        dosbox_executable = None
        engine_type = "dosbox"
        
        if dosbox_path_override:
            dosbox_executable = dosbox_path_override
            # Try to guess engine type from path
            if "staging" in dosbox_executable.lower(): engine_type = "dosbox-staging"
            elif "dosbox-x" in dosbox_executable.lower(): engine_type = "dosbox-x"
        else:
            # Check if game has specific custom path set (Priority 1)
            custom_path = details.get("custom_dosbox_path")
            if custom_path:
                dosbox_executable = custom_path
                # Guess type
                if "staging" in dosbox_executable.lower(): engine_type = "dosbox-staging"
                elif "dosbox-x" in dosbox_executable.lower(): engine_type = "dosbox-x"
            else:
                # Check if game has specific engine set (Priority 2)
                preferred_engine = details.get("engine") # e.g. "dosbox-staging"
                
                installations = self.get_dosbox_engines()
                
                if preferred_engine:
                    # Find first installation matching this type
                    for inst in installations:
                        if inst['type'] == preferred_engine:
                            dosbox_executable = inst['path']
                            engine_type = preferred_engine
                            break
            
            if not dosbox_executable:
                # Fallback to default
                dosbox_executable = self.default_dosbox_exe
                # Guess type
                if dosbox_executable:
                    if "staging" in dosbox_executable.lower(): engine_type = "dosbox-staging"
                    elif "dosbox-x" in dosbox_executable.lower(): engine_type = "dosbox-x"

        if not dosbox_executable: raise Exception("DOSBox executable not found. Please set a default in Settings.")
        dosbox_abs_path = os.path.abspath(dosbox_executable)
        if not os.path.exists(dosbox_abs_path): raise Exception(f"DOSBox executable not found at path: {dosbox_abs_path}")
        
        game_folder = self.find_game_folder(game_name)
        if not os.path.isdir(game_folder): raise Exception(f"Game '{game_name}' is not installed.")
        
        is_main_game_launch = False
        exe_map = details.get("executables", {})
        main_exe_role_path = next((exe for exe, info in exe_map.items() if info.get("role") == constants.ROLE_MAIN), None)
        
        if dos_prompt_only: main_exe_rel_path = None
        elif specific_exe:
            main_exe_rel_path = specific_exe
            if main_exe_rel_path == main_exe_role_path: is_main_game_launch = True
        else:
            if not main_exe_role_path: raise Exception("Main executable not set for this game.")
            main_exe_rel_path = main_exe_role_path
            is_main_game_launch = True
        
        # Prepare Configs (Cascading)
        user_overrides = details.get("user_overrides", {})
        
        if not config_override_path:
            if specific_exe or dos_prompt_only:
                 # Use a temp file for game config to avoid overwriting persistent dosbox.conf
                 # and to ensure custom_autoexec doesn't override our specific exe
                 details_to_use = details.copy()
                 # details_to_use["custom_autoexec"] = [] # Force generation to ensure specific exe is used
                 
                 # Pass specific_exe as main_executable to generate_config_content
                 # This ensures that if generate_autoexec is called (no custom_autoexec), it uses specific_exe
                 # And if custom_autoexec IS present, specific_exe_override handles the replacement.
                 
                 # Use minimal=True to respect Reference Config and avoid redundant settings
                 content = self.generate_config_content(game_name, specific_exe if specific_exe else main_exe_rel_path, details_to_use, dos_prompt_only, dosbox_path_override=dosbox_executable, specific_exe_override=specific_exe, auto_exit=auto_exit, minimal=True)
                 
                 temp_dir = os.path.join(self.base_dir, "database", "games_datainfo", game_name, "confs")
                 os.makedirs(temp_dir, exist_ok=True)
                 temp_conf_path = os.path.join(temp_dir, "temp_launch.conf")
                 
                 with open(temp_conf_path, 'w', encoding='utf-8') as f:
                     f.write("\n".join(content))
                     
                 config_override_path = temp_conf_path
            else:
                # Pass main_exe_rel_path as specific_exe_override to ensure it overrides custom_autoexec launch command
                self.write_game_config(game_name, main_exe_rel_path, details, dos_prompt_only, dosbox_path_override=dosbox_executable, auto_exit=auto_exit, specific_exe_override=main_exe_rel_path)
        
        base_conf, game_conf, override_conf = self.prepare_launch_configs(game_name, engine_type, user_overrides)
        
        # Simplified Launch Logic as requested:
        # 1. Do NOT pass base_conf (DOSBox finds it itself or we assume defaults)
        # 2. Pass game_conf (contains overrides)
        # 3. Pass autoexec.conf (contains mounts + launch + exit)
        
        # However, prepare_launch_configs returns paths.
        # game_conf is the path to dosbox.conf in game folder.
        # override_conf is the path to temp_launch.conf (if used) or None.
        
        # If config_override_path is set (e.g. temp_test.conf), we use that as the main config.
        
        cmd = [dosbox_abs_path]
        
        # Add Reference Config if available (Layer 1)
        reference_conf = details.get("reference_conf")
        if reference_conf:
            if not os.path.isabs(reference_conf):
                reference_conf = os.path.join(self.base_dir, reference_conf)
            if os.path.exists(reference_conf):
                cmd.extend(["-conf", reference_conf])
        
        if config_override_path:
             # Testing mode or specific override
             cmd.extend(["-conf", config_override_path])
        else:
             # Standard launch
             # We only pass the game's dosbox.conf if it exists
             if os.path.exists(game_conf):
                 cmd.extend(["-conf", game_conf])
                 
        if force_fullscreen: cmd.append("-fullscreen")
        
        # --- Launch Commands via -c ---
        # We must pass mount commands via -c as well, because -c commands run BEFORE [autoexec] in config files.
        # If we don't mount here, the launch commands (cd, exe) will fail.
        
        # WAIT! The user explicitly said: "v tempe si vytvoris autoexec.conf... a prikaz exit... cele by to malo v podstate vyzerat tak, ze spustas len jeden dosbox.conf... a v tempe si vytvoris autoexec.conf"
        # And "naco spustas base_engine... ten ani nemusis udavat"
        
        # So we should NOT use -c for mounts if we are using autoexec.conf.
        # We should put EVERYTHING in autoexec.conf.
        
        # Let's build the autoexec.conf content
        
        # 1. Mounts
        # We use generate_autoexec with dos_prompt_only=True to get just the mounts and c: switch
        # But we need to filter custom autoexec if present
        
        autoexec_lines = ["[autoexec]"]
        
        # Helper to construct full launch command
        def get_full_launch_command(target_exe):
            if not target_exe: return None
            
            mount_root = self._get_mount_root(details, game_folder)
            target_exe_norm = target_exe.replace("\\", "/")
            mount_root_norm = mount_root.replace("\\", "/")
            if mount_root_norm == ".": mount_root_norm = ""
            
            if mount_root_norm and target_exe_norm.lower().startswith(mount_root_norm.lower() + "/"):
                internal_path = target_exe_norm[len(mount_root_norm)+1:]
            elif mount_root_norm and target_exe_norm.lower() == mount_root_norm.lower():
                 internal_path = ""
            else:
                internal_path = target_exe_norm

            internal_path = internal_path.replace("/", "\\")
            exe_name = os.path.basename(internal_path)
            
            # Add params
            params = details.get("executables", {}).get(target_exe, {}).get("params", "")
            if params: exe_name += f" {params}"
            
            # Add loadfix/loadhigh from settings
            dosbox_settings = details.get("dosbox_settings", {})
            if extra_settings := dosbox_settings.get('extra', {}):
                if extra_settings.get("loadfix"): exe_name = f"loadfix -{extra_settings.get('loadfix_size', '64')} {exe_name}"
                if extra_settings.get("loadhigh"): exe_name = f"lh {exe_name}"
                
            # Fix for BAT files: Use CALL
            if exe_name.lower().endswith(".bat") or ".bat " in exe_name.lower():
                exe_name = f"call {exe_name}"
            
            return internal_path, exe_name

        # New Autoexec Logic: Pre + Mounts + C: + CD + Exe + Post + Exit
        # We ignore 'custom_autoexec' (legacy) if we are using the new system, or we can support both.
        # The user wants to split it.
        
        autoexec_pre = details.get("autoexec_pre", [])
        if isinstance(autoexec_pre, str): autoexec_pre = autoexec_pre.splitlines()
        
        autoexec_post = details.get("autoexec_post", [])
        if isinstance(autoexec_post, str): autoexec_post = autoexec_post.splitlines()
        
        # 1. Mounts (Always generated)
        # We use generate_autoexec with dos_prompt_only=True to get just the mounts and c: switch
        # But generate_autoexec might include 'exit' if we are not careful.
        # Let's use it but strip exit if needed.
        mount_lines = self.generate_autoexec(game_name, main_exe_rel_path, details, dos_prompt_only=True)
        
        # Filter out 'exit' from mount_lines just in case
        mount_lines = [l for l in mount_lines if l.strip().lower() != 'exit']
        
        autoexec_lines.extend(mount_lines)
        
        # 2. Pre-Launch Commands (Only for Main Game)
        target_exe = specific_exe if specific_exe else main_exe_rel_path
        is_main_launch = (not specific_exe) or (specific_exe == main_exe_rel_path)
        
        # Check if specific_exe is actually the main game (by role)
        if specific_exe:
            exes = details.get("executables", {})
            if exes.get(specific_exe, {}).get("role") == constants.ROLE_MAIN:
                is_main_launch = True
        
        if is_main_launch and autoexec_pre:
            autoexec_lines.append("\n# User Pre-Launch Commands")
            autoexec_lines.extend(autoexec_pre)
            
        # 3. Launch Commands
        if not dos_prompt_only:
            if target_exe:
                internal_path, full_cmd = get_full_launch_command(target_exe)
                exe_dir = os.path.dirname(internal_path)
                
                if exe_dir: autoexec_lines.append(f"cd \\{exe_dir}")
                else: autoexec_lines.append("cd \\")
                
                autoexec_lines.append(full_cmd)
        
        # 4. Post-Launch Commands (Only for Main Game)
        if is_main_launch and autoexec_post:
            autoexec_lines.append("\n# User Post-Launch Commands")
            autoexec_lines.extend(autoexec_post)
            
        # 5. Exit
        if auto_exit:
            autoexec_lines.append("exit")
        
        # Write autoexec.conf
        temp_dir = os.path.join(self.base_dir, "database", "games_datainfo", game_name, "confs")
        os.makedirs(temp_dir, exist_ok=True)
        temp_autoexec_path = os.path.join(temp_dir, "autoexec.conf")
        
        try:
            with open(temp_autoexec_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(autoexec_lines))
            cmd.extend(["-conf", temp_autoexec_path])
        except Exception as e:
            print(f"Error creating autoexec.conf: {e}")
            # Fallback to -c if file creation fails
            if not dos_prompt_only and 'exe_name' in locals():
                 if 'exe_dir' in locals() and exe_dir: cmd.extend(["-c", f"cd \\{exe_dir}"])
                 else: cmd.extend(["-c", "cd \\"])
                 cmd.extend(["-c", exe_name])
                 if auto_exit: cmd.extend(["-c", "exit"])

        print(f"DEBUG: Launching game. Auto-Exit: {auto_exit}")
        if auto_exit and "exit" not in autoexec_lines:
             print("WARNING: Auto-Exit is True but 'exit' command missing from autoexec_lines!")
        print(f"DEBUG: Final Command: {cmd}")

        dosbox_dir = os.path.dirname(dosbox_abs_path); capture_dir = os.path.join(dosbox_dir, "capture")
        
        # Run in a separate thread to avoid blocking the UI
        def run_process():
            try:
                start_time = time.time()
                process = subprocess.Popen(cmd, creationflags=0x08000000 if os.name == 'nt' else 0, cwd=game_folder)
                
                # Attempt to bring window to front (Windows only)
                if os.name == 'nt':
                    try:
                        import ctypes
                        import time as t_mod
                        
                        # Wait loop for window to appear
                        hwnd_found = None
                        
                        def enum_windows_callback(hwnd, pid):
                            import ctypes.wintypes
                            lpdwProcessId = ctypes.c_ulong()
                            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdwProcessId))
                            if lpdwProcessId.value == pid:
                                # Check if visible
                                if ctypes.windll.user32.IsWindowVisible(hwnd):
                                    return False # Stop enumeration, found it
                            return True
                            
                        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                        
                        # Try for up to 10 seconds
                        for _ in range(40):
                            t_mod.sleep(0.25)
                            # We need to find the HWND again because we can't easily pass it out of callback in Python 
                            # without a mutable object or global, but we can just use FindWindow if we knew the class/title.
                            # Since we don't, we iterate again or use a mutable list.
                            found_hwnds = []
                            def callback_wrapper(hwnd, _):
                                import ctypes.wintypes
                                lpdwProcessId = ctypes.c_ulong()
                                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdwProcessId))
                                if lpdwProcessId.value == process.pid and ctypes.windll.user32.IsWindowVisible(hwnd):
                                    found_hwnds.append(hwnd)
                                    return False
                                return True
                                
                            ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback_wrapper), 0)
                            
                            if found_hwnds:
                                hwnd = found_hwnds[0]
                                # Force to top
                                HWND_TOPMOST = -1
                                HWND_NOTOPMOST = -2
                                HWND_TOP = 0
                                SWP_NOMOVE = 0x0002
                                SWP_NOSIZE = 0x0001
                                SWP_SHOWWINDOW = 0x0040
                                
                                # 1. Restore if minimized
                                ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE
                                
                                # 2. Bring to foreground
                                ctypes.windll.user32.SetForegroundWindow(hwnd)
                                
                                ctypes.windll.user32.SetFocus(hwnd)
                                break
                                
                    except Exception as e: 
                        print(f"Focus error: {e}")

                process.wait()
                end_time = time.time()
                duration = end_time - start_time
                
                if is_main_game_launch:
                    current_details = self.get_game_details(game_name)
                    current_details['play_count'] = current_details.get('play_count', 0) + 1
                    current_details['last_played'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    current_details['play_time'] = current_details.get('play_time', 0) + duration
                    self.save_game_details(game_name, current_details)
                
                # self._handle_screenshots(dosbox_dir, game_folder, game_name) # Moved to finally block
                pass
                
            except Exception as e:
                print(f"Error running game: {e}")
            finally:
                # Ensure screenshots are handled even if error occurs
                try:
                    # Wait a bit for file system to sync?
                    time.sleep(1)
                    self._handle_screenshots(dosbox_dir, game_folder, game_name)
                except Exception as e:
                    print(f"Screenshot handling error: {e}")

        t = threading.Thread(target=run_process, daemon=True)
        t.start()
        return t

    def _handle_screenshots(self, dosbox_dir, game_folder, game_name):
        # Potential capture directories
        # 1. DOSBox default capture folder
        # 2. Game folder capture (if configured there)
        # 3. Temp export folder capture (if running test)
        
        capture_dirs = [
            os.path.join(dosbox_dir, "capture"),
            os.path.join(game_folder, "capture"),
            os.path.join(self.base_dir, "database", "games_datainfo", game_name, "confs", "capture"), # Check temp folder too
            os.path.join(self.base_dir, "database", "games_datainfo", game_name, "conf", "capture") # Check singular conf folder too
        ]
        
        # Destination directory
        # Screenshots should go to database/games_datainfo/<game>/screenshots
        dest_dir = os.path.join(self.base_dir, "database", "games_datainfo", game_name, "screenshots")
        os.makedirs(dest_dir, exist_ok=True)

        # Find next available index
        last_num = 0
        # Pattern: game_name_XXX.ext
        # We need to escape game_name for regex in case it has special chars
        escaped_name = re.escape(game_name)
        pattern = re.compile(rf"^{escaped_name}_(\d+)\.(?:png|jpg|jpeg|bmp|avi|mp4|mkv|wav|mid|mp3)$", re.IGNORECASE)
        
        for fname in os.listdir(dest_dir):
            if match := pattern.match(fname):
                try:
                    num = int(match.group(1))
                    last_num = max(last_num, num)
                except ValueError: pass
        
        current_index = last_num + 1
        
        # Extensions to look for
        extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.avi', '.mp4', '.mkv', '.wav', '.mid', '.mp3'}
        
        for cap_dir in capture_dirs:
            if not os.path.isdir(cap_dir): continue
            
            # Sort files by modification time to preserve capture order
            files = []
            for f in os.listdir(cap_dir):
                ext = os.path.splitext(f)[1].lower()
                if ext in extensions:
                    full_path = os.path.join(cap_dir, f)
                    files.append((full_path, ext))
            
            files.sort(key=lambda x: os.path.getmtime(x[0]))
            
            for src_path, ext in files:
                new_name = f"{game_name}_{current_index:03d}{ext}"
                dest_path = os.path.join(dest_dir, new_name)
                
                try:
                    shutil.move(src_path, dest_path)
                    print(f"Moved capture: {src_path} -> {dest_path}")
                    current_index += 1
                except Exception as e:
                    print(f"Failed to move {src_path}: {e}")

    def resize_image(self, img, target_size):
        if not HAS_PILLOW: return None
        target_width, target_height = target_size
        if target_width <= 1 or target_height <= 1: return None
        original_width, original_height = img.size; ratio = min(target_width / original_width, target_height / original_height)
        new_width = int(original_width * ratio); new_height = int(original_height * ratio)
        if new_width <= 0 or new_height <= 0: return None
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def game_has_dos4gw(self, game_name):
        game_folder = self.find_game_folder(game_name)
        if not os.path.isdir(game_folder): return False
        for root, _, files in os.walk(game_folder):
            for file in files:
                if file.lower() == 'dos4gw.exe': return True
        return False
        
    def apply_settings_to_conf(self, base_content, details):
        """
        Parses base_content (INI format) and updates values based on details['dosbox_settings'].
        Returns the updated content as a list of lines.
        """
        dosbox_settings = details.get("dosbox_settings", {})
        if not dosbox_settings:
            return base_content.splitlines()

        # Parse base content into a structure: [ {'type': 'comment', 'val': '...'}, {'type': 'section', 'name': '...'}, {'type': 'key', 'key': '...', 'val': '...'} ]
        # This is a simple parser to preserve comments and structure.
        lines = base_content.splitlines()
        parsed_lines = []
        current_section = None
        
        for line in lines:
            s = line.strip()
            if not s:
                parsed_lines.append({'type': 'empty', 'val': line})
                continue
            if s.startswith(('#', '%', ';')):
                parsed_lines.append({'type': 'comment', 'val': line})
                continue
            if s.startswith('[') and s.endswith(']'):
                current_section = s[1:-1].lower()
                parsed_lines.append({'type': 'section', 'name': current_section, 'val': line})
                continue
            
            if '=' in s:
                key, val = s.split('=', 1)
                key = key.strip().lower()
                parsed_lines.append({'type': 'key', 'section': current_section, 'key': key, 'val': line, 'original_key': s.split('=')[0].strip()})
            else:
                parsed_lines.append({'type': 'unknown', 'val': line})

        # Now update values
        # We iterate through our known settings and update the parsed structure
        # If a section or key doesn't exist, we might need to append it.
        # For simplicity, if section exists but key doesn't, we append to section.
        # If section doesn't exist, we append section at end.
        
        # Flatten settings for easier lookup
        # details['dosbox_settings'] = { 'cpu': {'cycles': '...'}, ... }
        
        for section, keys in dosbox_settings.items():
            section = section.lower()
            for key, value in keys.items():
                key = key.lower()
                # Find if this key exists in this section
                found = False
                for item in parsed_lines:
                    if item['type'] == 'key' and item.get('section') == section and item['key'] == key:
                        # Update value
                        # Reconstruct line preserving original key case if possible
                        item['val'] = f"{item['original_key']} = {value}"
                        found = True
                        break
                
                if not found:
                    # Key not found. Check if section exists.
                    section_found = False
                    last_section_index = -1
                    for i, item in enumerate(parsed_lines):
                        if item['type'] == 'section' and item['name'] == section:
                            section_found = True
                        if item['type'] == 'section':
                            if item['name'] == section:
                                last_section_index = i # Start of section
                            elif section_found and last_section_index != -1:
                                # We found the start of NEXT section, so previous section ended here
                                # Insert before this
                                # But wait, we need to find the END of the target section.
                                pass
                    
                    if section_found:
                        # Find the end of the section (either next section start or end of file)
                        insert_idx = len(parsed_lines)
                        for i in range(len(parsed_lines)):
                            if parsed_lines[i]['type'] == 'section' and parsed_lines[i]['name'] == section:
                                # Found start
                                for j in range(i + 1, len(parsed_lines)):
                                    if parsed_lines[j]['type'] == 'section':
                                        insert_idx = j
                                        break
                                break
                        
                        parsed_lines.insert(insert_idx, {'type': 'key', 'section': section, 'key': key, 'val': f"{key} = {value}", 'original_key': key})
                    else:
                        # Section not found, append to end
                        parsed_lines.append({'type': 'empty', 'val': ''})
                        parsed_lines.append({'type': 'section', 'name': section, 'val': f"[{section}]"})
                        parsed_lines.append({'type': 'key', 'section': section, 'key': key, 'val': f"{key} = {value}", 'original_key': key})

        # Reconstruct content
        return [item['val'] for item in parsed_lines]

    def _replace_exe_in_autoexec(self, autoexec_lines, specific_exe, full_command=None):
        """
        Replaces the first executable launch command in autoexec_lines with specific_exe.
        If full_command is provided, it uses that instead of just the exe name.
        """
        new_lines = []
        replaced = False
        
        # Normalize specific_exe path
        specific_exe_norm = specific_exe.replace("/", "\\")
        exe_dir = os.path.dirname(specific_exe_norm)
        exe_name = os.path.basename(specific_exe_norm)
        
        if full_command:
            # If full command is provided (e.g. "call GAME.BAT -params"), use it
            # But we still need exe_dir for CD command
            pass
        else:
            full_command = exe_name
        
        setup_commands = (
            'mount ', 'imgmount ', 'echo ', '@', 'pause', 'exit', 
            'set ', 'path ', 'prompt ', 'cls', 'config ', 'keyb '
        )
        
        for line in autoexec_lines:
            s = line.strip().lower()
            
            if replaced:
                new_lines.append(line)
                continue
                
            is_setup = False
            if s.startswith(setup_commands): is_setup = True
            if s.endswith(':') and len(s) == 2: is_setup = True
            if s.startswith('cd ') or s.startswith('cd\\'): is_setup = True 
            
            if not is_setup and s and not s.startswith(('#', ';', '%')):
                # Found the launch line
                # Inject CD if needed
                if exe_dir:
                    new_lines.append(f"cd \\{exe_dir}")
                else:
                    new_lines.append("cd \\")
                    
                new_lines.append(full_command)
                replaced = True
            else:
                new_lines.append(line)
                
        if not replaced:
            # If we didn't find a line to replace, append it
            if exe_dir:
                new_lines.append(f"cd \\{exe_dir}")
            new_lines.append(full_command)
            
        return new_lines

    def _filter_autoexec_for_mounts(self, autoexec_lines):
        """
        Keeps only setup commands (mount, imgmount, config, etc.) from autoexec.
        Stops at the first sign of execution (cd, or unknown command).
        """
        kept_lines = []
        setup_commands = (
            'mount ', 'imgmount ', 'echo ', '@', 'path ', 'prompt ', 'set ', 'config ', 'keyb ', 'cls'
        )
        
        for line in autoexec_lines:
            s = line.strip().lower()
            if not s or s.startswith(('#', ';', '%')):
                kept_lines.append(line)
                continue
                
            is_setup = False
            if s.startswith(setup_commands): is_setup = True
            if s.endswith(':') and len(s) == 2: is_setup = True # Drive change (c:) is considered setup usually
            
            if is_setup:
                kept_lines.append(line)
            else:
                # Found something that looks like a launch command or CD
                # Stop here
                break
                
        return kept_lines

    def generate_config_content(self, game_name, main_executable, details, for_standalone=False, standalone_msdos_name=None, dosbox_path_override=None, specific_exe_override=None, auto_exit=False, minimal=False, clean_export=False, include_autoexec=False):
        print(f"DEBUG: Generating config for {game_name}. Specific EXE: {specific_exe_override}, Auto-Exit: {auto_exit}, Minimal: {minimal}, Clean Export: {clean_export}")
        
        # Inject captures path - Use a temp capture folder so we can process/rename them later
        # Only inject if NOT cleaning for export
        if not clean_export:
            captures_path = os.path.join(self.base_dir, "database", "games_datainfo", game_name, "confs", "capture")
            os.makedirs(captures_path, exist_ok=True)
        
        # Work with a copy of settings to avoid polluting the persistent JSON with absolute paths
        # We need to inject this into details['dosbox_settings'] but without modifying the original object if possible.
        # Since details might be a reference, we should be careful.
        # However, for minimal config, we iterate game_settings.
        # For full config, we pass details to apply_settings_to_conf.
        
        # Let's create a shallow copy of details and a deep copy of dosbox_settings
        details_copy = details.copy()
        if "dosbox_settings" in details:
            details_copy["dosbox_settings"] = copy.deepcopy(details["dosbox_settings"])
        else:
            details_copy["dosbox_settings"] = {}
            
        if not clean_export:
            # Inject Standard/X
            if "dosbox" not in details_copy["dosbox_settings"]: details_copy["dosbox_settings"]["dosbox"] = {}
            details_copy["dosbox_settings"]["dosbox"]["captures"] = captures_path
            
            # Inject Staging
            if "capture" not in details_copy["dosbox_settings"]: details_copy["dosbox_settings"]["capture"] = {}
            details_copy["dosbox_settings"]["capture"]["capture_dir"] = captures_path
        
        if minimal:
            # Minimal config generation: Only write differences from reference config
            # The user wants "dosbox.conf v priecinku hry... obsahuje iba to, co je odlisne".
            
            # 1. Load Reference Config
            reference_conf_path = details_copy.get("reference_conf")
            reference_settings = {}
            
            if reference_conf_path:
                if not os.path.isabs(reference_conf_path):
                    reference_conf_path = os.path.join(self.base_dir, reference_conf_path)
                
                if os.path.exists(reference_conf_path):
                    try:
                        with open(reference_conf_path, 'r', encoding='utf-8', errors='ignore') as f:
                            reference_settings = self.parse_dosbox_conf_to_json(f.read())
                    except Exception as e:
                        print(f"Error reading reference config: {e}")
            
            # 2. Compare Game Settings with Reference
            game_settings = details_copy.get("dosbox_settings", {})
            content = []
            
            for section, keys in game_settings.items():
                if section.lower() == "autoexec": continue
                
                section_diff = []
                ref_section = reference_settings.get(section, {})
                
                for key, val in keys.items():
                    ref_val = ref_section.get(key)
                    # If value is different from reference, or key doesn't exist in reference
                    if str(val) != str(ref_val):
                        section_diff.append(f"{key}={val}")
                
                if section_diff:
                    content.append(f"[{section}]")
                    content.extend(section_diff)
                    content.append("")
            
            # Do not add [autoexec] to minimal config unless requested
            if include_autoexec:
                content.append("[autoexec]")
                autoexec_lines = self.generate_autoexec(game_name, main_executable, details, dos_prompt_only=False)
                content.extend(autoexec_lines)
                content.append("exit")
                
            return content

        # --- Layer 2: Game Config (dosbox.conf) ---
        dosbox_path = dosbox_path_override or details_copy.get("custom_dosbox_path") or details_copy.get("dosbox_path")
        base_conf = self.get_clean_dosbox_conf(dosbox_path)
        game_folder = self.find_game_folder(game_name)
        game_conf_path = os.path.join(game_folder, "dosbox.conf")
        if os.path.exists(game_conf_path):
            try:
                with open(game_conf_path, 'r', encoding='utf-8') as f:
                    game_conf_content = f.read()
                
                game_conf_settings = self.parse_dosbox_conf_to_json(game_conf_content)
                # Apply Layer 2 to base_conf
                dummy_details = {"dosbox_settings": game_conf_settings}
                base_conf_lines = self.apply_settings_to_conf(base_conf, dummy_details)
                base_conf = "\n".join(base_conf_lines)
                
            except Exception as e:
                print(f"Error reading game dosbox.conf: {e}")
        
        # --- Layer 3: User Overrides ---
        # Apply settings from details to base_conf
        content = self.apply_settings_to_conf(base_conf, details_copy)
        
        # Ensure [autoexec] is handled correctly
        # Remove existing [autoexec] from content if present
        autoexec_idx = -1
        for i, line in enumerate(content):
            if line.strip().lower() == '[autoexec]':
                autoexec_idx = i
                break
        
        if autoexec_idx != -1:
            content = content[:autoexec_idx]
            
        content.append("")
        content.append("[autoexec]")
        # Leave [autoexec] empty in the main config file
        # The actual commands will be in autoexec.conf passed via -conf
        
        return content

    def get_clean_dosbox_conf(self, dosbox_path=None):
        content = self.get_dosbox_conf_content(dosbox_path)
        if not content: return ""
        
        clean_lines = []
        for line in content.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("%"): continue
            clean_lines.append(line)
        return "\n".join(clean_lines)

    def _generate_launch_commands(self, game_name, main_executable, details):
        content = []
        game_folder = self.find_game_folder(game_name)
        dosbox_settings = details.get("dosbox_settings", {})
        
        # We need to know mount_root to calculate relative path
        # This duplicates logic from generate_autoexec, but we need it here.
        mount_root = "." 
        if "mounts" in details and details["mounts"]:
             for mount in details["mounts"]:
                if mount.get("drive", "").lower() == "c" and mount.get("type") == "dir":
                    paths = [p.strip() for p in mount.get("path", "").split(";") if p.strip()]
                    if paths: mount_root = paths[0]
                    break
        else:
             mount_c_path = details.get("mount_c", "")
             if not mount_c_path:
                drives_c_path = os.path.join(game_folder, "drives", "c")
                if os.path.isdir(drives_c_path): mount_c_path = "drives/c"
                else: mount_c_path = "."
             mount_root = mount_c_path

        if main_executable:
            exe_rel_path = main_executable.replace("\\", "/")
            
            # Normalize paths
            mount_root_norm = mount_root.replace("\\", "/").strip("/")
            if mount_root_norm == ".": mount_root_norm = ""
            
            if mount_root_norm and exe_rel_path.lower().startswith(mount_root_norm.lower() + "/"):
                internal_path = exe_rel_path[len(mount_root_norm)+1:]
            else:
                internal_path = exe_rel_path
                
            cd_path = os.path.dirname(internal_path)
            if cd_path and cd_path != ".": content.append(f"cd {cd_path}")
            
            exe_command = os.path.basename(internal_path)
            # Add parameters to exe command
            params = details.get("executables", {}).get(main_executable, {}).get("params", "")
            if params: exe_command += f" {params}"
            if extra_settings := dosbox_settings.get('extra', {}):
                if extra_settings.get("loadfix"): exe_command = f"loadfix -{extra_settings.get('loadfix_size', '64')} {exe_command}"
                if extra_settings.get("loadhigh"): exe_command = f"lh {exe_command}"
            content.append(exe_command)
            
        return content

    def generate_autoexec(self, game_name, main_executable, details, dos_prompt_only=False):
        # Extracted autoexec generation logic
        content = []
        game_folder = self.find_game_folder(game_name)
        dosbox_settings = details.get("dosbox_settings", {})
        
        mount_root = "." # Default
        
        # Check for new 'mounts' list
        if "mounts" in details and details["mounts"]:
            for mount in details["mounts"]:
                drive = mount.get("drive", "").lower()
                m_type = mount.get("type", "dir")
                path = mount.get("path", "")
                label = mount.get("label", "")
                as_type = mount.get("as", "iso")
                
                if not drive or not path: continue
                
                # Handle multiple paths for images (semicolon separated)
                paths = [p.strip() for p in path.split(";") if p.strip()]
                quoted_paths = [f'"{p}"' for p in paths]
                path_str = " ".join(quoted_paths)
                
                cmd = ""
                if m_type == "dir":
                    cmd = f'mount {drive} {path_str}'
                    if label: cmd += f' -label {label}'
                    if drive == "c": mount_root = paths[0]
                else: # image
                    cmd = f'imgmount {drive} {path_str} -t {as_type}'
                
                content.append(cmd)
        else:
            # Legacy behavior
            # Determine mount root
            mount_c_path = details.get("mount_c", "")
            if not mount_c_path:
                # Fallback to auto-detection
                drives_c_path = os.path.join(game_folder, "drives", "c")
                if os.path.isdir(drives_c_path):
                    mount_c_path = "drives/c"
                else:
                    mount_c_path = "."
            
            content.append(f'mount c "{mount_c_path}"')
            mount_root = mount_c_path
            
            
            # Mount D
            mount_d_path = details.get("mount_d", "")
            if mount_d_path:
                 content.append(f'imgmount d "{mount_d_path}" -t iso')
            else:
                # Fallback to auto-detection
                cd_dir = os.path.join(game_folder, "cd")
                if os.path.isdir(cd_dir):
                    isos = [f for f in sorted(os.listdir(cd_dir)) if f.lower().endswith(('.iso', '.cue'))]
                    if isos:
                        # Mount all found ISOs to D if multiple? Or just first?
                        # Legacy logic was:
                        # for i, iso_file in enumerate(isos):
                        #    drive_letter = chr(ord('D') + i)
                        #    content.append(f'imgmount {drive_letter} "cd/{iso_file}" -t iso')
                        # But the code I read earlier had a loop mounting D, E, F...
                        # Let's preserve that loop logic from the file read I did earlier.
                        for i, iso_file in enumerate(isos):
                            drive_letter = chr(ord('D') + i)
                            content.append(f'imgmount {drive_letter} "cd/{iso_file}" -t iso')

        content.append("c:")
        
        if dos_prompt_only:
            return content

        # Pre-Launch Commands (User defined)
        if "autoexec_pre" in details and details["autoexec_pre"]:
            content.extend(details["autoexec_pre"])

        if main_executable:
            exe_rel_path = main_executable.replace("\\", "/")
            
            # Calculate path relative to the MOUNT ROOT (C:)
            # If mount_root is "drives/c" and exe is "drives/c/GAME/GAME.EXE", internal is "GAME/GAME.EXE"
            # If mount_root is "." and exe is "GAME.EXE", internal is "GAME.EXE"
            
            # Normalize paths
            mount_root_norm = mount_root.replace("\\", "/").strip("/")
            if mount_root_norm == ".": mount_root_norm = ""
            
            if mount_root_norm and exe_rel_path.lower().startswith(mount_root_norm.lower() + "/"):
                internal_path = exe_rel_path[len(mount_root_norm)+1:]
            else:
                internal_path = exe_rel_path
                
            cd_path = os.path.dirname(internal_path)
            if cd_path and cd_path != ".": content.append(f"cd {cd_path}")
            
            exe_command = os.path.basename(internal_path)
            # Add parameters to exe command
            params = details.get("executables", {}).get(main_executable, {}).get("params", "")
            if params: exe_command += f" {params}"
            if extra_settings := dosbox_settings.get('extra', {}):
                if extra_settings.get("loadfix"): exe_command = f"loadfix -{extra_settings.get('loadfix_size', '64')} {exe_command}"
                if extra_settings.get("loadhigh"): exe_command = f"lh {exe_command}"
            
            # Fix for BAT files: Use CALL to ensure control returns to autoexec
            if exe_command.lower().endswith(".bat") or ".bat " in exe_command.lower():
                exe_command = f"call {exe_command}"
                
            content.append(exe_command)
            
            # Post-Launch Commands (User defined)
            if "autoexec_post" in details and details["autoexec_post"]:
                content.extend(details["autoexec_post"])
            
            if details.get("auto_exit", False): 
                content.append("exit")
                
        return content

    def write_game_config(self, game_name, main_executable, details, dos_prompt_only=False, dosbox_path_override=None, auto_exit=False, specific_exe_override=None):
        # We need to know auto_exit preference here too, but it's usually passed at runtime.
        # However, write_game_config writes the persistent config.
        # If we bake 'exit' into persistent config, it will always exit.
        # The user preference in UI (Auto-Close) is runtime.
        # So we should NOT bake 'exit' into persistent config unless it's a permanent setting in details.
        # details['auto_exit'] exists.
        
        # Combine runtime auto_exit with details setting (runtime takes precedence if True? No, usually UI passes the state)
        should_auto_exit = auto_exit or details.get("auto_exit", False)
        
        game_folder = self.find_game_folder(game_name); conf_path = os.path.join(game_folder, "dosbox.conf")
        
        # Generate content using the new robust method
        # Use clean_export=True to avoid absolute paths like captures
        # Use include_autoexec=False to avoid baking autoexec into persistent config (handled by autoexec.conf at runtime)
        content_lines = self.generate_config_content(game_name, main_executable, details, for_standalone=dos_prompt_only, dosbox_path_override=dosbox_path_override, auto_exit=should_auto_exit, specific_exe_override=specific_exe_override, minimal=True, clean_export=True, include_autoexec=False)
        final_content = "\n".join(content_lines)
            
        try:
            with open(conf_path, 'w', encoding='utf-8') as f: f.write(final_content)
        except IOError as e: raise Exception(f"Failed to write dosbox.conf: {e}")

    def update_dosbox_conf(self, game_name, details, from_content=False):
        # This replaces update_custom_conf. It writes directly to dosbox.conf AND updates the 'custom_config_content' in details if needed.
        
        exe_map = details.get("executables", {})
        main_exe = next((exe for exe, info in exe_map.items() if info.get("role") == constants.ROLE_MAIN), None)
        
        content_str = ""
        if from_content:
            content_str = details.get("custom_config_content", "").strip()
        
        if not content_str:
            # Regenerate from details using the robust method
            # Use clean_export=True to avoid absolute paths
            content = self.generate_config_content(game_name, main_exe, details, minimal=True, clean_export=True, include_autoexec=False)
            content_str = "\n".join(content)
        
        # Write to dosbox.conf
        game_folder = self.find_game_folder(game_name)
        conf_path = os.path.join(game_folder, "dosbox.conf")
        try:
            with open(conf_path, 'w', encoding='utf-8') as f:
                f.write(content_str)
        except Exception as e:
            print(f"Failed to update dosbox.conf: {e}")
            
        # Remove custom.conf if it exists (cleanup)
        custom_conf_path = os.path.join(game_folder, "custom.conf")
        if os.path.exists(custom_conf_path):
            try: os.remove(custom_conf_path)
            except: pass
    
    def _prepare_export_folder(self, game_name, temp_dir):
        source_dir = self.find_game_folder(game_name)
        # Copy content to temp_dir
        for item in os.listdir(source_dir):
            s = os.path.join(source_dir, item)
            d = os.path.join(temp_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
                
        # Clean dosbox.conf
        conf_path = os.path.join(temp_dir, "dosbox.conf")
        details = self.get_game_details(game_name)
        exe_map = details.get("executables", {})
        main_exe = next((exe for exe, info in exe_map.items() if info.get("role") == constants.ROLE_MAIN), None)
        
        # Generate clean config with autoexec
        content = self.generate_config_content(game_name, main_exe, details, minimal=True, clean_export=True, include_autoexec=True)
        
        with open(conf_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(content))
            
        return temp_dir

    def make_zip_archive(self, game_name, output_path, progress_callback=None):
        # Check extension to decide format
        if output_path.lower().endswith('.7z'):
            if HAS_7ZIP:
                self.make_7z_archive(game_name, output_path, progress_callback)
                return
            else:
                pass

        with tempfile.TemporaryDirectory() as temp_dir:
            export_root = self._prepare_export_folder(game_name, temp_dir)
            
            total_files = 0
            for _, _, files in os.walk(export_root):
                total_files += len(files)
            processed_files = 0
                
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(export_root):
                    arcname = os.path.relpath(root, export_root)
                    for file in files: 
                        zipf.write(os.path.join(root, file), os.path.join(arcname, file))
                        processed_files += 1
                        if progress_callback:
                            progress_callback(processed_files, total_files)

    def make_7z_archive(self, game_name, output_path, progress_callback=None):
        if not HAS_7ZIP: raise Exception("py7zr module not found.")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            export_root = self._prepare_export_folder(game_name, temp_dir)
            
            # Calculate total files for progress
            total_files = 0
            for _, _, files in os.walk(export_root):
                total_files += len(files)
                
            processed_files = 0
            
            with py7zr.SevenZipFile(output_path, 'w') as z:
                for root, _, files in os.walk(export_root):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, export_root)
                        z.write(full_path, rel_path)
                        processed_files += 1
                        if progress_callback:
                            progress_callback(processed_files, total_files)

    def make_standalone_archive(self, game_name, msdos_name, zip_path, flat_structure):
        details = self.get_game_details(game_name); game_folder = self.find_game_folder(game_name)
        dosbox_path = details.get("custom_dosbox_path") or self.default_dosbox_exe
        if not dosbox_path or not os.path.isdir(os.path.dirname(dosbox_path)): raise Exception("Valid DOSBox path not found.")
        dosbox_root = os.path.dirname(dosbox_path)
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = os.path.join(temp_dir, game_name); os.makedirs(package_root)
            shutil.copytree(game_folder, package_root, dirs_exist_ok=True)
            dest_dosbox_path = os.path.join(package_root, "DOSBox") if not flat_structure else package_root
            if not flat_structure: os.makedirs(dest_dosbox_path, exist_ok=True)
            shutil.copytree(dosbox_root, dest_dosbox_path, dirs_exist_ok=True, ignore=shutil.ignore_patterns('*.zip'))
            main_exe = next((exe for exe, info in details.get("executables", {}).items() if info.get("role") == constants.ROLE_MAIN), None)
            conf_content = "\n".join(self.generate_config_content(game_name, main_exe, details, for_standalone=True, standalone_msdos_name=msdos_name))
            with open(os.path.join(package_root, "dosbox.conf"), 'w') as f: f.write(conf_content)
            bat_path = os.path.join(package_root, "!start.bat"); dosbox_exe_rel_path = os.path.join("DOSBox", "dosbox.exe") if not flat_structure else "dosbox.exe"; conf_rel_path = "dosbox.conf"
            bat_content = f'@echo off\npushd %~dp0\n"{dosbox_exe_rel_path}" -conf "{conf_rel_path}" -exit\npopd'
            with open(bat_path, 'w') as f: f.write(bat_content)
            shutil.make_archive(os.path.splitext(zip_path)[0], 'zip', temp_dir)

    def find_vlc(self):
        if os.name == 'nt':
            for path in [os.path.join(os.environ.get("ProgramFiles", ""), "VideoLAN", "VLC", "vlc.exe"), os.path.join(os.environ.get("ProgramFiles(x86)", ""), "VideoLAN", "VLC", "vlc.exe")]:
                if os.path.exists(path): return path
        if shutil.which("vlc"): return "vlc"
        return None

    def get_available_dosbox_confs(self):
        """
        Scans the DOSBox directory for available configuration files.
        Returns a list of paths relative to the workspace root if possible.
        """
        dosbox_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "DOSBox")
        conf_files = []
        
        # 1. Scan default DOSBox folder
        if os.path.exists(dosbox_root):
            for root, _, files in os.walk(dosbox_root):
                for file in files:
                    if file.endswith(".conf"):
                         full_path = os.path.join(root, file)
                         # Make relative to base_dir for cleaner UI
                         try:
                             rel_path = os.path.relpath(full_path, self.base_dir)
                             conf_files.append(rel_path)
                         except ValueError:
                             conf_files.append(full_path)
                             
        # 2. Scan configured DOSBox installations
        installations = self.settings.get("dosbox_installations", [])
        for inst in installations:
            path = inst.get("path")
            if path and os.path.exists(path):
                # Look for .conf in the same directory
                inst_dir = os.path.dirname(path)
                try:
                    for f in os.listdir(inst_dir):
                        if f.endswith(".conf"):
                            full_path = os.path.join(inst_dir, f)
                            # Avoid duplicates
                            is_dup = False
                            for existing in conf_files:
                                # Resolve existing to abs
                                existing_abs = os.path.abspath(os.path.join(self.base_dir, existing)) if not os.path.isabs(existing) else existing
                                if os.path.abspath(full_path) == existing_abs:
                                    is_dup = True
                                    break
                            
                            if not is_dup:
                                try:
                                    rel_path = os.path.relpath(full_path, self.base_dir)
                                    conf_files.append(rel_path)
                                except ValueError:
                                    conf_files.append(full_path)
                except Exception: pass
                
        return sorted(conf_files)

    def get_default_dosbox_conf(self, custom_dosbox_path=None, specific_conf_path=None):
        if specific_conf_path and os.path.exists(specific_conf_path):
            try:
                with open(specific_conf_path, 'r', encoding='utf-8') as f: return f.read()
            except: pass

        dosbox_exe_path = custom_dosbox_path or self.default_dosbox_exe
        if not dosbox_exe_path: return None
        dosbox_dir = os.path.dirname(dosbox_exe_path)
        # Added dosbox-x.reference.conf to the list
        # Priority: dosbox-staging.conf > dosbox-x.reference.conf > dosbox.conf
        possible_conf_names = ['dosbox-staging.conf', 'dosbox-x.reference.conf', 'dosbox.conf']
        for conf_name in possible_conf_names:
            conf_path = os.path.join(dosbox_dir, conf_name)
            if os.path.exists(conf_path):
                try:
                    with open(conf_path, 'r', encoding='utf-8') as f: return f.read()
                except IOError as e: print(f"Error reading default DOSBox conf at {conf_path}: {e}"); return None
        try:
            result = subprocess.run([dosbox_exe_path, "-printconf"], capture_output=True, text=True, check=True, creationflags=0x08000000 if os.name == 'nt' else 0)
            conf_path = result.stdout.strip()
            if os.path.exists(conf_path):
                with open(conf_path, 'r', encoding='utf-8') as f: return f.read()
        except (subprocess.CalledProcessError, FileNotFoundError, IOError) as e:
            print(f"Error getting default DOSBox conf via -printconf: {e}")
        return None

    def parse_dosbox_conf_to_json(self, conf_content):
        if not conf_content: return copy.deepcopy(constants.DEFAULT_GAME_DETAILS['dosbox_settings'])
        
        # Find the first section header to skip any preamble/intro text
        first_section_index = conf_content.find('[')
        if first_section_index == -1: return copy.deepcopy(constants.DEFAULT_GAME_DETAILS['dosbox_settings'])
        
        clean_content = conf_content[first_section_index:]
        
        parser = ConfigParser(comment_prefixes=('#',), inline_comment_prefixes=('#',), allow_no_value=True, strict=False, interpolation=None)
        try:
            parser.read_string(clean_content)
        except Exception as e:
            print(f"Error parsing DOSBox config: {e}")
            return copy.deepcopy(constants.DEFAULT_GAME_DETAILS['dosbox_settings'])

        settings = {}
        for section in parser.sections():
            settings[section] = {}
            for option, value in parser.items(section):
                settings[section][option] = value
        return settings

    def detect_dosbox_version(self, conf_content):
        """
        Detects DOSBox version from configuration content.
        Returns (variant, version) tuple.
        """
        if not conf_content: return ("Unknown", "Unknown")
        
        # Check first few lines specifically
        lines = conf_content.splitlines()[:15]
        for line in lines:
            # Case-insensitive check for "configuration file for" or just "DOSBox"
            if "configuration file" in line.lower() or "dosbox" in line.lower():
                # Remove leading comment chars
                clean_line = line.lstrip('#% ').strip()
                
                # Regex 1: DOSBox [Variant] [Version] (Version starts with digit)
                # Priority: Check for version number pattern first to avoid greedy variant capture
                # Matches: DOSBox-X 2025.10.07, DOSBox Staging 0.82.2
                match_noparens = re.search(r'dosbox\s*[-]?\s*([a-zA-Z0-9_\s]*?)\s+([0-9][0-9.]+[0-9]*)', clean_line, re.IGNORECASE)
                if match_noparens:
                     variant = match_noparens.group(1).strip()
                     version = match_noparens.group(2).strip()
                     
                     # If variant is empty, it might be Original
                     if not variant: variant = "Original"
                     
                     # Normalize variant names
                     if variant.lower().startswith("staging"): variant = "Staging"
                     if variant.lower().startswith("x"): variant = "X"
                     
                     return (variant, version)

                # Regex 2: DOSBox [Variant] (Version)
                # Matches: DOSBox Staging (0.82.2)
                match_parens = re.search(r'dosbox\s*[-]?\s*([^(]+)\s*\(([^)]+)\)', clean_line, re.IGNORECASE)
                if match_parens:
                    variant = match_parens.group(1).strip()
                    version = match_parens.group(2).strip()
                    if variant.lower().startswith("staging"): variant = "Staging"
                    if variant.lower().startswith("x"): variant = "X"
                    return (variant, version)

        # Fallback for original DOSBox or other formats
        if "DOSBox 0.74" in conf_content: return ("Original", "0.74")
        
        return ("Unknown", "Unknown")

    def load_dosbox_metadata_json(self, variant):
        """
        Loads metadata from JSON based on DOSBox variant.
        Returns a dictionary: {section: {key: {'default': val, 'possible': list, 'info': text}}}
        """
        json_name = "dosbox_standard.json"
        variant_lower = variant.lower()
        
        if "staging" in variant_lower: 
            json_name = "dosbox_staging.json"
        elif "x" in variant_lower or "-x" in variant_lower: 
            json_name = "dosbox_x.json"
        
        json_path = os.path.join(self.base_dir, "database", json_name)
        if not os.path.exists(json_path): 
            # print(f"JSON not found: {json_path}") # Suppress error as requested
            return {}, "n/a"
        
        metadata = {}
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                
                # Handle List of Objects (e.g. from CSV conversion)
                if isinstance(raw_data, list):
                    for item in raw_data:
                        # Expecting keys: section, key, default, possible, info
                        sec = item.get("section", "General")
                        key = item.get("key", "")
                        if not key: continue
                        
                        sec_lower = sec.lower()
                        k_lower = key.lower()
                        
                        if sec_lower not in metadata: metadata[sec_lower] = {}
                        
                        # Parse possible values if string
                        poss = item.get("possible", [])
                        if isinstance(poss, str):
                            poss = [x.strip() for x in poss.split(',')] if poss else []
                            
                        metadata[sec_lower][k_lower] = {
                            "section": sec,
                            "default": item.get("default", ""),
                            "possible": poss,
                            "info": item.get("info", "")
                        }

                # Handle Dictionary Structure
                elif isinstance(raw_data, dict):
                    for sec, keys in raw_data.items():
                        sec_lower = sec.lower()
                        if sec_lower not in metadata: metadata[sec_lower] = {}
                        
                        for k, v in keys.items():
                            k_lower = k.lower()
                            # Ensure fields exist, handling both "default" and "default_value" styles
                            default_val = v.get("default_value", v.get("default", ""))
                            possible_val = v.get("possible_values", v.get("possible", []))
                            
                            metadata[sec_lower][k_lower] = {
                                "section": sec,
                                "default": default_val,
                                "possible": possible_val,
                                "info": v.get("info", "")
                            }
                            
        except Exception as e:
            print(f"Error loading JSON metadata: {e}")
            
        return metadata, json_name

    def parse_dosbox_conf_with_metadata(self, conf_content):
        """
        Parses DOSBox config content to extract structure (sections/keys).
        Metadata is now loaded from CSV files via load_dosbox_metadata_csv, 
        but we still return the structure here.
        """
        if not conf_content: return {}
        
        extracted_data = {}
        current_section = "General"
        
        lines = conf_content.splitlines()
        
        for line in lines:
            raw_line = line.strip()
            
            if not raw_line: continue
                
            if raw_line.startswith('[') and raw_line.endswith(']'):
                current_section = raw_line[1:-1]
                if current_section not in extracted_data:
                    extracted_data[current_section] = {}
                continue
                
            if raw_line.startswith('#') or raw_line.startswith('%'): continue
                
            if '=' in raw_line:
                key, value = raw_line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                if current_section not in extracted_data:
                    extracted_data[current_section] = {}
                    
                # We only store the value here. Metadata comes from CSV later.
                extracted_data[current_section][key] = {
                    "value": value,
                    "description": "", # Will be filled from CSV
                    "possible_values": "",
                    "possible_values_list": []
                }
        
        return extracted_data

    def update_dosbox_conf_content(self, original_content, new_settings):
        """
        Updates the original DOSBox configuration content with new settings.
        Preserves comments and structure. Adds missing keys and sections.
        """
        lines = original_content.splitlines()
        updated_lines = []
        current_section = None
        
        # Create a mutable copy of new_settings to track what has been applied
        settings_to_apply = copy.deepcopy(new_settings)
        
        # First pass: Update existing keys
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                current_section = stripped[1:-1].lower()
                updated_lines.append(line)
                continue
            
            if current_section and current_section in settings_to_apply:
                if '=' in stripped and not stripped.startswith(('#', ';', '%')):
                    key = stripped.split('=', 1)[0].strip().lower()
                    match_key = next((k for k in settings_to_apply[current_section] if k.lower() == key), None)
                    
                    if match_key:
                        new_value = settings_to_apply[current_section][match_key]
                        indent = line[:line.find(stripped)]
                        updated_lines.append(f"{indent}{match_key} = {new_value}")
                        del settings_to_apply[current_section][match_key]
                        continue

            updated_lines.append(line)
            
        # Second pass: Add missing keys to existing sections or add new sections
        final_lines = []
        current_section = None
        
        for line in updated_lines:
            stripped = line.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                # Before switching section, append leftover keys for the PREVIOUS section
                if current_section and current_section in settings_to_apply and settings_to_apply[current_section]:
                    for k, v in settings_to_apply[current_section].items():
                        final_lines.append(f"{k} = {v}")
                    del settings_to_apply[current_section]
                
                current_section = stripped[1:-1].lower()
                final_lines.append(line)
                continue
            
            final_lines.append(line)
            
        # Handle the last section
        if current_section and current_section in settings_to_apply and settings_to_apply[current_section]:
            for k, v in settings_to_apply[current_section].items():
                final_lines.append(f"{k} = {v}")
            del settings_to_apply[current_section]
            
        # Add completely new sections
        for section, keys in settings_to_apply.items():
            if not keys: continue
            final_lines.append("")
            final_lines.append(f"[{section}]")
            for k, v in keys.items():
                final_lines.append(f"{k} = {v}")
                
        return "\n".join(final_lines)

    def sync_dosbox_settings_with_reference(self, game_data):
        """
        Synchronizes game_data['dosbox_settings'] with the reference configuration.
        1. Identifies the target DOSBox variant (Staging vs X vs Standard) from reference_conf.
        2. Loads mapping_functions.json.
        3. Iterates through dosbox_settings.
        4. Maps keys to the target variant.
        5. Removes keys that do not exist in the reference configuration.
        """
        if 'reference_conf' not in game_data or not game_data['reference_conf']:
            return game_data

        ref_conf_path = game_data['reference_conf']
        if not os.path.isabs(ref_conf_path):
            ref_conf_path = os.path.join(self.base_dir, ref_conf_path)

        if not os.path.exists(ref_conf_path):
            return game_data

        # Determine target variant
        target_variant = "standard"
        lower_path = ref_conf_path.lower()
        if "staging" in lower_path:
            target_variant = "staging"
        elif "dosbox-x" in lower_path or "dosbox_x" in lower_path:
            target_variant = "x"
        
        # Load reference config to check for existence of keys
        try:
            with open(ref_conf_path, 'r', encoding='utf-8', errors='ignore') as f:
                ref_content = f.read()
            
            ref_parser = DOSBoxConfigParser()
            ref_parser.parse(ref_content)
        except Exception:
            return game_data

        # Load mapping functions
        mapping_path = os.path.join(self.base_dir, "database", "mapping_functions.json")
        mapping = {}
        if os.path.exists(mapping_path):
            try:
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    mapping = json.load(f)
            except Exception:
                pass

        if 'dosbox_settings' not in game_data:
            return game_data

        new_settings = {}
        
        # Iterate through existing settings
        for section, keys in game_data['dosbox_settings'].items():
            section_lower = section.lower()
            
            for key, value in keys.items():
                key_lower = key.lower()
                
                # Check if key exists in reference
                ref_val = ref_parser.get(section_lower, key_lower)
                
                final_section = section_lower
                final_key = key_lower
                
                if ref_val is None:
                    # Key not found in reference. Check mapping.
                    mapped_found = False
                    target_map = None
                    
                    if section_lower in mapping:
                        # Case 1: key is in mapping
                        if key_lower in mapping[section_lower]:
                            target_map = mapping[section_lower][key_lower].get(target_variant)
                        else:
                            # Case 2: key might be the source for another variant
                            for canonical, variants in mapping[section_lower].items():
                                for var_name, var_data in variants.items():
                                    if var_data and var_data.get('key') == key_lower:
                                        target_map = variants.get(target_variant)
                                        break
                                if target_map: break
                    
                    if target_map and target_map.get('key'):
                        final_section = target_map.get('section', section_lower)
                        final_key = target_map.get('key')
                        
                        # Check if mapped key exists in reference
                        if ref_parser.get(final_section, final_key) is not None:
                            mapped_found = True
                    
                    if not mapped_found:
                        # Key doesn't exist in reference and no valid mapping found.
                        continue
                
                # Add to new_settings
                if final_section not in new_settings:
                    new_settings[final_section] = {}
                new_settings[final_section][final_key] = value

        game_data['dosbox_settings'] = new_settings
        return game_data

    def import_from_dosbox_conf(self, game_name):
        if os.path.exists(self._get_game_json_path(game_name)):
            return self.get_game_details(game_name)

        details = self.get_game_details(game_name)
        
        # Set default DOSBox config based on settings
        default_exe = self.default_dosbox_exe
        if default_exe and os.path.exists(default_exe):
            exe_dir = os.path.dirname(default_exe)
            conf_candidates = [f for f in os.listdir(exe_dir) if f.lower().endswith(".conf")]
            selected_conf = None
            exe_name = os.path.basename(default_exe).lower()
            
            if "staging" in exe_name:
                selected_conf = next((f for f in conf_candidates if "staging" in f.lower()), None)
            elif "dosbox-x" in exe_name:
                selected_conf = next((f for f in conf_candidates if "dosbox-x" in f.lower()), None)
            
            if not selected_conf and conf_candidates:
                selected_conf = next((f for f in conf_candidates if "dosbox.conf" in f.lower()), conf_candidates[0])
                
            if selected_conf:
                details['reference_conf'] = os.path.join(exe_dir, selected_conf)
                self.save_game_details(game_name, details)

        game_folder = self.find_game_folder(game_name)
        
        conf_path = None
        drives_c_path = os.path.join(game_folder, "drives", "c")
        if os.path.isdir(drives_c_path) and os.path.exists(os.path.join(drives_c_path, "dosbox.conf")):
            conf_path = os.path.join(drives_c_path, "dosbox.conf")
        elif os.path.exists(os.path.join(game_folder, "dosbox.conf")):
             conf_path = os.path.join(game_folder, "dosbox.conf")
        
        if not conf_path: return details

        try:
            with open(conf_path, 'r', encoding='utf-8', errors='ignore') as f: conf_content = f.read()
            parser = ConfigParser(comment_prefixes=('#',), inline_comment_prefixes=('#',), allow_no_value=True, strict=False); parser.read_string(conf_content)
            details['dosbox_settings'] = self.parse_dosbox_conf_to_json(conf_content)
            if parser.has_section('autoexec'):
                autoexec_lines = parser.get('autoexec', 'autoexec', fallback='').splitlines()
                autoexec_lines = [line.strip() for line in autoexec_lines if line.strip() and not line.strip().startswith(('#', '@echo off', 'cls'))]
                exe_line = next((line for line in reversed(autoexec_lines) if any(word.lower().endswith(ext) for ext in ['.exe', '.com', '.bat'] for word in line.split())), None)
                if exe_line:
                    exe_candidate, params_candidate = "", ""
                    for word in exe_line.split():
                        if any(word.lower().endswith(ext) for ext in ['.exe', '.com', '.bat']):
                            exe_candidate = word; params_candidate = exe_line.split(exe_candidate, 1)[1].strip(); break
                    if exe_candidate:
                        all_exes = self.get_all_executables(game_name)
                        found_exe = next((exe for exe in all_exes if os.path.basename(exe).lower() == exe_candidate.lower()), None)
                        if found_exe:
                            if 'executables' not in details or not details['executables']:
                                details['executables'] = {exe:{"role": constants.ROLE_UNASSIGNED, "title": "", "params": ""} for exe in all_exes}
                            for exe_path in details['executables']: details['executables'][exe_path]['role'] = constants.ROLE_UNASSIGNED
                            details['executables'][found_exe] = {"role": constants.ROLE_MAIN, "title": "", "params": params_candidate}
            self.save_game_details(game_name, details)
            # os.rename(conf_path, conf_path + ".bak")
            messagebox.showinfo("Import Successful", "Settings from existing dosbox.conf have been imported.", parent=None)
            return self.get_game_details(game_name)
        except Exception as e:
            print(f"Could not import from dosbox.conf: {e}"); return details

    def sanitize_dosbox_settings(self, settings, target_variant):
        """
        Sanitizes DOSBox settings based on the target variant using mapping_functions.json.
        target_variant: "dosbox-staging", "dosbox-x", "dosbox-standard"
        Returns (new_settings, remapped_keys) where remapped_keys is a set of (section, key) tuples that were remapped/removed.
        """
        mapping_path = os.path.join(self.base_dir, "database", "mapping_functions.json")
        if not os.path.exists(mapping_path): return settings, set()
        
        try:
            with open(mapping_path, 'r') as f:
                mapping = json.load(f)
        except: return settings, set()
        
        # Map variant to JSON keys: "staging", "x"
        variant_key = "x" 
        if "staging" in target_variant.lower(): variant_key = "staging"
        elif "dosbox-x" in target_variant.lower(): variant_key = "x"
        
        new_settings = {}
        remapped_keys = set()
        
        # Normalize mapping keys to lowercase for case-insensitive lookup
        normalized_mapping = {k.lower(): {sub_k.lower(): sub_v for sub_k, sub_v in v.items()} for k, v in mapping.items()}
        
        for section, keys in settings.items():
            for key, value in keys.items():
                # Find mapping
                # Mapping structure: section -> key -> variant -> {section, key}
                
                map_info = None
                sec_lower = section.lower()
                key_lower = key.lower()
                
                # Check if section exists in mapping
                if sec_lower in normalized_mapping:
                    # Check if key exists in mapping[section]
                    if key_lower in normalized_mapping[sec_lower]:
                        if variant_key in normalized_mapping[sec_lower][key_lower]:
                            map_info = normalized_mapping[sec_lower][key_lower][variant_key]
                
                if map_info:
                    target_sec = map_info.get("section")
                    target_key = map_info.get("key")
                    
                    # Mark original key as remapped
                    remapped_keys.add((section, key))
                    
                    if target_sec and target_key:
                        if target_sec not in new_settings: new_settings[target_sec] = {}
                        # If the key already exists (e.g. mapped from another key), we overwrite it.
                        new_settings[target_sec][target_key] = value
                        
                        # Special case: If we are mapping TO cpu_cycles (in Staging), ensure 'cycles' is NOT in new_settings
                        # This handles the case where 'cycles' maps to 'cpu_cycles', but 'cpu_cycles' might also be present in input.
                        # If 'cpu_cycles' is present in input, it will be processed separately.
                        # If 'cycles' is processed first, it sets 'cpu_cycles'.
                        # If 'cpu_cycles' is processed later, it overwrites 'cpu_cycles'.
                        # But we must ensure 'cycles' is never added to new_settings if it's remapped.
                        # Since we are building new_settings from scratch, 'cycles' won't be added unless we add it.
                        # And we only add it in the 'else' block below (No mapping found).
                        # So this logic is correct.
                        pass
                        
                    # If target_sec is None, it's removed/excluded (so we don't add it to new_settings)
                else:
                    # No mapping found, keep as is
                    # BUT check if this key is 'cycles' and we are in Staging.
                    # If 'cycles' is not in mapping (maybe mapping file is missing or incomplete?), we should still force remove it for Staging.
                    if variant_key == "staging" and section.lower() == "cpu" and key.lower() == "cycles":
                         remapped_keys.add((section, key))
                         continue

                    if section not in new_settings: new_settings[section] = {}
                    new_settings[section][key] = value
                    
        return new_settings, remapped_keys

    def create_differential_backup(self, game_name, progress_callback=None):
        """
        Creates a backup of the game, but only includes files that are different from the original archive.
        Returns (success, message)
        """
        try:
            backup_dir = os.path.join(self.base_dir, "archive", "backups")
            if not os.path.exists(backup_dir): os.makedirs(backup_dir)
            
            timestamp = datetime.now().strftime("%Y-%m-%d")
            archive_name = f"{game_name}_{timestamp}.save.7z"
            archive_path = os.path.join(backup_dir, archive_name)
            
            game_folder = self.find_game_folder(game_name)
            if not os.path.exists(game_folder):
                return False, "Game folder not found."

            # Find original archive
            original_zip = None
            possible_exts = [".zip", ".7z", ".rar"]
            for ext in possible_exts:
                p = os.path.join(self.zipped_dir, game_name + ext)
                if os.path.exists(p):
                    original_zip = p
                    break
            
            if not original_zip:
                return False, "Original archive not found. Cannot perform differential backup."

            # Get list of files in original archive with their CRCs or sizes
            original_files = {} # path -> size
            
            if progress_callback: progress_callback(0, 100, "Scanning original archive...")

            if original_zip.lower().endswith(".zip"):
                with zipfile.ZipFile(original_zip, 'r') as zf:
                    for info in zf.infolist():
                        norm_path = os.path.normpath(info.filename)
                        original_files[norm_path] = info.file_size
            elif original_zip.lower().endswith(".7z") and HAS_7ZIP:
                with py7zr.SevenZipFile(original_zip, 'r') as zf:
                    for info in zf.list():
                        norm_path = os.path.normpath(info.filename)
                        original_files[norm_path] = info.uncompressed
            
            # Identify changed files
            files_to_backup = []
            
            if progress_callback: progress_callback(20, 100, "Scanning game folder...")
            
            all_files = []
            for root, dirs, files in os.walk(game_folder):
                for file in files:
                    all_files.append(os.path.join(root, file))
            
            total_scan = len(all_files)
            for i, file_path in enumerate(all_files):
                rel_path = os.path.relpath(file_path, game_folder)
                norm_rel_path = os.path.normpath(rel_path)
                
                should_backup = False
                if norm_rel_path not in original_files:
                    should_backup = True # New file
                else:
                    if os.path.getsize(file_path) != original_files[norm_rel_path]:
                        should_backup = True # Modified size
                
                if should_backup:
                    files_to_backup.append((file_path, rel_path))
                
                if progress_callback and i % 10 == 0:
                     progress_callback(20 + int((i / total_scan) * 30), 100, f"Scanning: {rel_path}")

            # Filter out if only dosbox.conf changed
            # User request: "Ak je archiv 0 rozdiel, alebo tam ides zbalit len subor dosbox.conf, tak to ani nerob"
            if not files_to_backup:
                return True, "No changes detected. Backup skipped."
            
            # Check if only config files are changed
            # We consider .conf files in the root as "config files"
            only_configs = True
            for _, rel_path in files_to_backup:
                if os.path.dirname(rel_path) == "" and rel_path.lower().endswith(".conf"):
                    continue
                only_configs = False
                break
            
            if only_configs:
                return True, "Only configuration files changed. Backup skipped as requested."

            # Create backup archive
            if progress_callback: progress_callback(50, 100, "Creating backup archive...")
            
            total_backup = len(files_to_backup)
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for i, (file_path, arcname) in enumerate(files_to_backup):
                    zipf.write(file_path, arcname)
                    if progress_callback and i % 5 == 0:
                        progress_callback(50 + int((i / total_backup) * 50), 100, f"Archiving: {arcname}")
            
            if progress_callback: progress_callback(100, 100, "Done!")
            
            return True, f"Differential backup created:\n{archive_name}\n({len(files_to_backup)} files)"
            
        except Exception as e:
            return False, f"Failed to create backup: {e}"