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

# Conf sections
CONF_DEFAULTS = "dosbox_default"
CONF_USER = "dosbox_user"

# Run EXE options
EXE_RUN_TYPE_DOSBOX = "dosbox"
EXE_RUN_TYPE_WINDOWS = "windows"

# DOSBox settings
MACHINE_TYPES = ["svga_s3", "svga_et3000", "svga_et4000", "svga_paradise", "vgaonly", "svga_nolfb", "vesa_nolfb", "vesa_oldvbe", "hercules", "cga", "tandy", "pcjr", "ega"]
MEM_SIZES = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1023]
CPU_TYPES = ["auto", "386", "386_slow", "486_slow", "pentium_slow", "386_prefetch"]
CPU_CYCLES = ["auto", "max", "fixed"]
AUDIO_RATES = [49716, 48000, 44100, 32000, 22050, 16000, 11025, 8000]
SB_TYPES = ["sb1", "sb2", "sbpro1", "sbpro2", "sb16", "gb", "none"]
OPL_MODES = ["auto", "cms", "opl2", "dualopl2", "opl3", "none"]
GUS_ULTRASND = ["true", "false"]
LPT_DAC_TYPES = ["none", "disney", "covox", "ston1", "off"]
MIDI_DEVICES = ["auto", "win32", "fluidsynth", "mt32", "none"]

THEME_OPTIONS = ["darkly", "solar", "superhero", "cyborg", "vapor", "flatly", "journal", "litera", "lumen", "minty", "pulse", "sandstone", "united", "yeti", "morph", "simplex", "cerculean"]
