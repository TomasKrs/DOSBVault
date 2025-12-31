import ttkbootstrap as tb
import os
import json

def export_themes():
    style = tb.Style()
    theme_names = style.theme_names()
    
    output_dir = os.path.join(os.getcwd(), "themes")
    os.makedirs(output_dir, exist_ok=True)
    
    # We want to keep darkly and litera as built-in, but export others?
    # Or export all? User said "Export all themes... remove hardcoded... keep only darkly and litera".
    # This implies the app should only *know* about darkly and litera by default, and load others from files.
    
    for name in theme_names:
        if name in ["darkly", "litera"]:
            continue
            
        # How to get theme definition?
        # ttkbootstrap doesn't have a direct 'export to json' for a loaded theme easily accessible 
        # without digging into internal structures or using the ThemeDefinition object if it was created from one.
        # However, built-in themes are loaded from internal JSONs.
        # We can try to access the internal theme definitions.
        
        try:
            # This is a bit hacky, relying on ttkbootstrap internals
            from ttkbootstrap.themes import standard, user
            
            # Check if it's a standard theme
            theme_def = None
            if name in standard.STANDARD_THEMES:
                theme_def = standard.STANDARD_THEMES[name]
            
            if theme_def:
                # It's a dictionary-like object or we can construct one
                # Actually STANDARD_THEMES contains the definitions.
                # We need to serialize it.
                pass
                
        except Exception as e:
            print(f"Could not export {name}: {e}")

    # Since extracting built-in themes back to JSON is non-trivial without using internal APIs 
    # (and they are already inside the library), maybe the user just wants the *files* to exist 
    # so they can be edited?
    # 
    # Alternatively, I can just list the themes available in ttkbootstrap and if the user wants to "remove" them
    # from the program, I just filter the list in the UI.
    # 
    # "Exportuj vsetky temy do priecinku themes" -> Export all themes to themes folder.
    # "odstran z programu (myslim napevno zadane temy)" -> Remove hardcoded themes.
    # 
    # If I can't easily export them, I might just have to skip the export part or find a way.
    # 
    # Let's look at how ttkbootstrap loads themes. `style.load_user_themes(path)`.
    # 
    # If I cannot export them, I will just filter the list in the UI to only show [darkly, litera] + whatever is in `themes/`.
    # And I will try to find the JSONs for standard themes online or in the library path and copy them?
    # 
    # Let's try to find where ttkbootstrap is installed and copy the json files?
    pass

if __name__ == "__main__":
    # I will just use the UI filtering approach for now, as "exporting" built-in themes is complex.
    # But wait, I can try to locate the site-packages/ttkbootstrap/themes.json if it exists.
    import ttkbootstrap
    print(os.path.dirname(ttkbootstrap.__file__))
