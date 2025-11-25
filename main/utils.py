import os
import stat

def remove_readonly(func, path, excinfo):
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    try:
        func(path)
    except Exception:
        pass

def format_size(size_bytes):
    if size_bytes == 0: return "-"
    mb = size_bytes / (1024 * 1024)
    if mb < 1: return "< 1 MB"
    return f"{mb:.1f} MB"

def truncate_text(text, max_chars):
    if text is None: return ""
    if len(text) > max_chars: return text[:max_chars-3] + "..."
    return text

def get_folder_size(path):
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(): total += entry.stat().st_size
            elif entry.is_dir(): total += get_folder_size(entry.path)
    except Exception:
        pass
    return total
    
def get_file_size(path):
    if os.path.exists(path): return os.path.getsize(path)
    return 0