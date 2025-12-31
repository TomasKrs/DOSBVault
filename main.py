import os
import sys
import json

# Add the project root to the Python path.
# This allows for absolute imports like `from script.gui import ...`
# and also makes relative imports within the `script` package work correctly.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from script.gui import DOSManagerApp

def check_and_create_structure():
    """
    Checks for the existence of necessary directories and default files,
    and creates them if they are missing.
    """
    base_dir = os.getcwd()
    
    dirs_to_create = ["games", "archive", "export", "themes", "DOSBox", "import", "log", "database", "database/templates", "database/games_datainfo"]
    
    try:
        for d in dirs_to_create:
            path = os.path.join(base_dir, d)
            if not os.path.isdir(path):
                print(f"Directory '{d}' not found. Creating...")
                os.makedirs(path)
    except OSError as e:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Critical Error", f"Failed to create necessary directories.\n\nError: {e}\n\nPlease check disk space and permissions.\nThe application will now exit.")
        sys.exit(1)

    settings_path = os.path.join(base_dir, 'settings.json')
    if not os.path.exists(settings_path):
        print("Settings file 'settings.json' not found. Creating default.")
        default_settings = {
            "theme": "darkly",
            "zip_dir": "archive",
            "root_dir": "games",
            "dosbox_root_dir": "DOSBox"
        }
        with open(settings_path, 'w') as f:
            json.dump(default_settings, f, indent=4)
            
    themes_dir = os.path.join(base_dir, "themes")
    
    darkly_path = os.path.join(themes_dir, 'darkly.json')
    if not os.path.exists(darkly_path):
        print("Default theme 'darkly.json' not found. Creating.")
        darkly_theme = {
            "colors": {
                "primary": "#375a7f", "secondary": "#444", "success": "#00bc8c",
                "info": "#3498db", "warning": "#f39c12", "danger": "#e74c3c",
                "light": "#303030", "dark": "#dee2e6", "bg": "#222", "fg": "#fff",
                "selectbg": "#375a7f", "selectfg": "#fff", "border": "#2f2f2f",
                "inputfg": "#fff", "inputbg": "#444"
            }
        }
        with open(darkly_path, 'w') as f:
            json.dump(darkly_theme, f, indent=4)

    litera_path = os.path.join(themes_dir, 'litera.json')
    if not os.path.exists(litera_path):
        print("Default theme 'litera.json' not found. Creating.")
        litera_theme = {
            "colors": {
                "primary": "#2583C5", "secondary": "#F8F9FA", "success": "#32B877",
                "info": "#46B8ED", "warning": "#FFC107", "danger": "#E85642",
                "light": "#F8F9FA", "dark": "#343A40", "bg": "#FFFFFF", "fg": "#343A40",
                "selectbg": "#2583C5", "selectfg": "#FFFFFF", "border": "#E2E3E5",
                "inputfg": "#343A40", "inputbg": "#FFFFFF"
            }
        }
        with open(litera_path, 'w') as f:
            json.dump(litera_theme, f, indent=4)


if __name__ == "__main__":
    # check_and_create_structure() # Disabled to let Start Wizard handle it 
    
    # Splash Screen
    import tkinter as tk
    splash = tk.Tk()
    splash.overrideredirect(True)
    splash.geometry("300x100+{}+{}".format(
        (splash.winfo_screenwidth() - 300) // 2,
        (splash.winfo_screenheight() - 100) // 2
    ))
    tk.Label(splash, text="DOSBVault", font=("Helvetica", 16, "bold")).pack(pady=(20, 5))
    tk.Label(splash, text="Loading... Please wait.", font=("Helvetica", 10)).pack(pady=5)
    splash.update()
    
    # Destroy splash before creating the main app to avoid Tcl conflicts
    splash.destroy()
    
    try:
        app = DOSManagerApp()
        app.mainloop()
    except KeyboardInterrupt:
        print("Application stopped by user.")
        sys.exit(0) 