import os
import sys
import shutil
import subprocess

def restart_program():
    sys.stdout.flush()
    
    # Use relauncher script to ensure clean restart
    # We need to point to the relauncher.py in the root directory
    # __file__ is script/utils.py, so dirname is script, dirname(dirname) is root
    relauncher = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "relauncher.py")
    
    if os.path.exists(relauncher):
        # Pass current PID, python executable, and script args
        # sys.argv[0] is the script path (main.py)
        # We need to ensure we pass the correct arguments to relauncher
        # relauncher.py expects: pid, executable, script_path, args...
        
        # If we are running from python.exe, sys.argv[0] is the script
        script_path = sys.argv[0]
        script_args = sys.argv[1:]
        
        cmd = [sys.executable, relauncher, str(os.getpid()), sys.executable, script_path] + script_args
        subprocess.Popen(cmd)
    else:
        # Fallback to os.execl (might fail if file is locked or other issues)
        try:
            python = sys.executable
            os.execl(python, python, *sys.argv)
        except Exception as e:
            print(f"Restart failed: {e}")
    
    # Force kill self to ensure we don't hang
    os._exit(0)

def format_size(size_bytes):
    if size_bytes == 0: return "0 B"
    power = 1024; n = 0; power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size_bytes >= power and n < len(power_labels): size_bytes /= power; n += 1
    return f"{size_bytes:.1f} {power_labels[n]}B"

def truncate_text(text, max_length):
    return (text[:max_length-3] + '...') if len(text) > max_length else text

def get_folder_size(path):
    if not os.path.isdir(path): return 0
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp): total += os.path.getsize(fp)
    return total

def get_file_size(path):
    try: return os.path.getsize(path)
    except FileNotFoundError: return 0

def remove_readonly(func, path, exc_info):
    import stat; os.chmod(path, stat.S_IWRITE); func(path)