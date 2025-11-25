import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

ICON_READY = "✓"
ICON_WAITING = ""
STAR_SYMBOL = "★"
HEART_SYMBOL = "❤"

# Roles
ROLE_UNASSIGNED = "unassigned"
ROLE_MAIN = "main"
ROLE_SETUP = "setup"
ROLE_CUSTOM = "custom"
ROLE_IGNORE = "ignore"

ROLE_DISPLAY = {
    ROLE_UNASSIGNED: "[ ? ] Unassigned",
    ROLE_MAIN: "[ ★ ] Main Game",
    ROLE_SETUP: "[ 🔧 ] Setup",
    ROLE_CUSTOM: "[ 📂 ] Custom / Other",
    ROLE_IGNORE: "[ 🚫 ] Ignore"
}
ROLE_KEYS = {v: k for k, v in ROLE_DISPLAY.items()}

GENRE_OPTIONS = [
    "Action", "Platformer", "Shooter", "Adventure", 
    "Interactive Fiction", "Point-and-click", "RPG", 
    "Roguelike", "Strategy", "RTS", "Simulation", 
    "Sports", "Racing", "Fighting", "Beat 'em up", 
    "Puzzle", "Educational", "Casino / Card", 
    "Horror", "Sandbox", "Hybrid / Genre-mix"
]

# --- DOSBOX CONSTANTS ---
CORE_OPTIONS = ["auto", "dynamic", "normal", "full", "simple"]
CPUTYPE_OPTIONS = ["auto", "386", "386_slow", "386_prefetch", "486", "pentium", "pentium_mmx"]
CYCLES_OPTIONS = ["auto", "max", "300", "700", "1500", "3000", "6000", "8000", "12000", "25000", "50000", "60000", "100000", "200000"]
CYCLES_PROT_OPTIONS = ["auto", "max", "60000", "80000", "90000", "110000", "160000", "200000"]

MEMSIZE_OPTIONS = ["0", "1", "2", "4", "8", "16", "32", "64"]
LOADFIX_SIZE_OPTIONS = ["0", "63", "64", "127"]
OUTPUT_OPTIONS = ["opengl", "texture", "texturenb"]
GLSHADER_OPTIONS = ["none", "crt-auto", "crt-auto-machine", "crt-auto-arcade", "crt-auto-arcade-sharp", "sharp"]
WIN_RES_OPTIONS = ["default", "small", "medium", "large", "320x200", "640x480", "800x600", "1024x768", "1280x768", "1280x960", "1280x1024"]
FULL_RES_OPTIONS = ["original", "desktop", "0x0", "320x200", "640x480", "800x600", "1024x768", "1280x768", "1280x960", "1280x1024"]

# Audio Options
SB_TYPES = ["sb16", "sbpro1", "sbpro2", "sb1", "sb2", "gb", "ess", "none"]
OPL_MODES = ["auto", "opl2", "dualopl2", "opl3", "opl3gold", "esfm", "none"]
GUS_BOOL = ["false", "true"]
SPEAKER_TYPES = ["impulse", "discrete", "none", "off"]
TANDY_TYPES = ["auto", "on", "psg", "off"]
LPT_DAC_TYPES = ["none", "disney", "covox", "ston1", "off"]
MIDI_DEVICES = ["auto", "win32", "fluidsynth", "mt32", "none"]

THEME_OPTIONS = ["darkly", "solar", "superhero", "cyborg", "vapor", "flatly", "journal", "litera", "lumen", "minty", "pulse", "sandstone", "united", "yeti", "morph", "simplex", "cerculean"]