# Tento súbor bude teraz očakávať, že BASE_DIR nastaví vstupný bod aplikácie (main.py)
BASE_DIR = None 

# --- Ostatné konštanty zostávajú bez zmeny ---
HEART_SYMBOL = "★"
STAR_SYMBOL = "★"
ICON_READY = "✓"
ICON_WAITING = "…"

# ... (všetky ostatné konštanty, ktoré tam máte, ako GENRE_OPTIONS, ROLE_DISPLAY atď.)

# Príklady (doplňte podľa vášho aktuálneho súboru):
GENRE_OPTIONS = ["Action", "Adventure", "RPG", "Strategy", "Simulation", "Sports", "Other"]
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
# ... atď.