# BASE_DIR bude nastavený pri štarte aplikácie v main.py
BASE_DIR = None

# --- SYMBOLS ---
HEART_SYMBOL = "★"
STAR_SYMBOL = "★"
ICON_READY = "✓"
ICON_WAITING = "…"

# --- GAME ROLES ---
ROLE_MAIN = "main"
ROLE_SETUP = "setup"
ROLE_CUSTOM = "custom"
ROLE_UNASSIGNED = "unassigned"

ROLE_DISPLAY = {
    ROLE_MAIN: "▶ Main Executable",
    ROLE_SETUP: "⚙ Setup / Install",
    ROLE_CUSTOM: "📂 Custom / Addon",
    ROLE_UNASSIGNED: "(Unassigned)"
}
ROLE_KEYS = {v: k for k, v in ROLE_DISPLAY.items()}

# --- GAME METADATA OPTIONS ---
GENRE_OPTIONS = [
    "Action", "Adventure", "RPG", "Strategy", "Simulation", "Sports", "Other",
    "Action, Adventure", "Action, RPG", "Strategy, RPG", "Racing", "Puzzle", "Fighting"
]

# --- DOSBOX CONFIGURATION OPTIONS (CHÝBAJÚCE KONŠTANTY) ---
CORE_OPTIONS = ["auto", "dynamic", "normal", "simple", "full"]
CPUTYPE_OPTIONS = ["auto", "386", "386_slow", "486_slow", "pentium_slow", "386_prefetch"]
CYCLES_OPTIONS = ["auto", "max", "3000", "6000", "10000", "20000", "30000", "50000"]
CYCLES_PROT_OPTIONS = CYCLES_OPTIONS + ["60000", "80000", "100000", "120000"]
MEMSIZE_OPTIONS = ["8", "16", "32", "64"]
LOADFIX_SIZE_OPTIONS = ["16", "32", "64", "128"]
OUTPUT_OPTIONS = ["opengl", "surface", "openglnb", "ddraw", "texture"]
WIN_RES_OPTIONS = ["default", "640x480", "800x600", "1024x768", "1280x960", "1600x1200"]
FULL_RES_OPTIONS = ["desktop", "original", "640x480", "800x600", "1024x768", "1280x960", "1600x1200"]
GLSHADER_OPTIONS = ["none", "default", "advinterp", "crt-easymode", "crt-geom", "sharp"]
SB_TYPES = ["sb16", "sbpro1", "sbpro2", "sb2", "gb", "none"]
OPL_MODES = ["auto", "opl2", "opl3", "dualopl2", "none"]
GUS_BOOL = ["false", "true"]
SPEAKER_TYPES = ["auto", "fast", "on", "off", "impulse"]
TANDY_TYPES = ["auto", "on", "off"]
LPT_DAC_TYPES = ["none", "disney", "stereo"]
MIDI_DEVICES = ["auto", "default", "alsa", "oss", "win32", "coremidi", "none"]