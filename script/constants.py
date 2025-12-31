VERSION = "0.1.0"

GENRE_OPTIONS = ["Action", "Adventure", "Arcade", "Board Game", "Card Game", "Educational", "Fighting", "Flight Simulator", "Other", "Pinball", "Platform", "Puzzle", "Racing", "RPG", "Shoot 'em up", "Simulation", "Sports", "Strategy", "Wargame"]
CORE_OPTIONS = ["auto", "dynamic", "normal", "simple"]
CPUTYPE_OPTIONS = ["auto", "386", "386_fast", "386_prefetch", "486", "pentium", "pentium_mmx"]
CYCLES_OPTIONS = ["auto", "max", "1000", "2000", "3000", "5000", "10000", "20000", "30000", "40000", "50000", "60000", "80000", "100000"]
CYCLES_PROT_OPTIONS = ["auto", "max", "10000", "20000", "30000", "50000", "80000", "100000", "150000", "200000"]
MEMSIZE_OPTIONS = ["1", "2", "4", "8", "16", "32", "64", "128", "256", "512"]
LOADFIX_SIZE_OPTIONS = ["4", "16", "32", "64", "128", "256"]

ROLE_MAIN = "main"; ROLE_SETUP = "setup"; ROLE_INSTALL = "install"; ROLE_CUSTOM = "custom"; ROLE_UNASSIGNED = "unassigned"
ROLE_DISPLAY = {ROLE_MAIN: "Main Game", ROLE_SETUP: "Setup/Config", ROLE_INSTALL: "Game Installer", ROLE_CUSTOM: "Custom...", ROLE_UNASSIGNED: "Unassigned"}
ROLE_KEYS = {v: k for k, v in ROLE_DISPLAY.items()}

WIN_RES_OPTIONS = ["default", "desktop", "320x200", "640x400", "640x480", "800x600", "1024x768", "1280x720", "1280x1024", "1920x1080"]
FULL_RES_OPTIONS = ["desktop", "default", "320x200", "640x400", "640x480", "800x600", "1024x768", "1280x720", "1280x1024", "1920x1080"]
OUTPUT_OPTIONS = ["opengl", "texture", "surface", "openglnb", "texturenb", "ddraw"]
GLSHADER_OPTIONS = [
    "none", "crt-auto", "crt-auto-machine", "crt-auto-arcade", "crt-auto-arcade-sharp", "sharp", "bilinear", "nearest"
]
SCALER_OPTIONS = ["none", "normal2x", "normal3x", "advmame2x", "advmame3x", "hq2x", "hq3x", "2xsai", "super2xsai", "supereagle", "advinterp2x", "advinterp3x", "tv2x", "tv3x", "rgb2x", "rgb3x", "scan2x", "scan3x"]
ASPECT_OPTIONS = ["auto", "vga", "source", "4:3", "16:9", "16:10", "none"]
VIEWPORT_OPTIONS = ["fit", "fill", "stretch", "1:1"]
MONOCHROME_PALETTE_OPTIONS = ["amber", "green", "white", "paper-white"]
COMPOSITE_OPTIONS = ["auto", "on", "off", "cga", "pcjr", "tandy"]
ERA_OPTIONS = ["auto", "early", "mid", "late", "latest"]
VOODOO_OPTIONS = ["auto", "true", "false"]
VOODOO_MEMSIZE_OPTIONS = ["4", "2", "8", "12"]

DOSBOX_CONTROLS = """
CTRL+F1   \t\tStart keymapper
CTRL+F4   \t\tUpdate cached drive info
CTRL+F5   \t\tSave a screenshot
CTRL+ALT+F5 \t\tStart/Stop video recording
CTRL+F6   \t\tStart/Stop sound recording
CTRL+F7   \t\tDecrease frameskip
CTRL+F8   \t\tIncrease frameskip
CTRL+F9   \t\tQuit DOSBox
CTRL+F10  \t\tCapture/Release mouse
CTRL+F11  \t\tSlow down emulation
CTRL+F12  \t\tSpeed up emulation
ALT+PAUSE \t\tPause emulation
ALT+ENTER \t\tToggle fullscreen
"""
CPU_CYCLES_MAP = {140: "8086", 800: "286", 3000: "386DX", 8000: "486DX2/50", 30000: "Pentium 60", 60000: "Pentium 120", 100000: "Pentium 200 MMX"}

DEFAULT_GAME_DETAILS = {
    "title": "", "year": "", "developers": "", "publishers": "", "genre": "", "rating": 0, "critics_score": 0,
    "num_players": "", "description": "", "notes": "", "custom_dosbox_path": "", "favorite": False,
    "custom_fields": {}, "video_links": [], "executables": {}, "dosbox_settings": {},
    "custom_config_content": "", "play_count": 0, "last_played": ""
}