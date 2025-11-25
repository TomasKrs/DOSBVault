import sys
import os

# 1. Definovanie absolútnej cesty ku koreňovému adresáru aplikácie.
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# 2. Pridanie adresára 'script' do systémovej cesty, aby sme mohli importovať moduly.
script_dir = os.path.join(APP_ROOT, 'script')
sys.path.insert(0, script_dir)

# 3. Import modulu constants a nastavenie správnej cesty BASE_DIR.
# Toto musíme urobiť PRED importom ostatných modulov, ktoré ho používajú.
import constants
constants.BASE_DIR = APP_ROOT

# 4. Teraz, keď je všetko nastavené, môžeme bezpečne importovať a spustiť aplikáciu.
from gui import DOSManagerApp

if __name__ == "__main__":
    app = DOSManagerApp()
    app.mainloop()