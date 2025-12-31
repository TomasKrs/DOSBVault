import ttkbootstrap as tb
from ttkbootstrap.themes import standard
import json
import os

def export_themes():
    output_dir = os.path.join(os.getcwd(), "themes")
    os.makedirs(output_dir, exist_ok=True)
    
    # These are the themes we want to keep built-in
    keep_builtin = ["darkly", "litera"]
    
    for name, definition in standard.STANDARD_THEMES.items():
        if name in keep_builtin:
            continue
            
        # definition is a dictionary. We can save it as json.
        # We need to ensure it has the correct structure for ttkbootstrap to load it back.
        # Usually it expects a list of themes or a single theme object.
        
        # The structure in json usually is:
        # { "themes": [ { ... } ] }
        
        # definition contains 'colors', 'type', etc.
        # We need to add 'name': name to it if it's missing.
        
        theme_data = definition.copy()
        theme_data['name'] = name
        
        # Wrap in the expected structure
        json_data = {"themes": [theme_data]}
        
        file_path = os.path.join(output_dir, f"{name}.json")
        with open(file_path, "w") as f:
            json.dump(json_data, f, indent=4)
            
        print(f"Exported {name} to {file_path}")

if __name__ == "__main__":
    export_themes()
