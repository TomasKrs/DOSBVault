import logging
from gui import DOSManagerApp

if __name__ == "__main__":
    # basic logging to console for debugging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = DOSManagerApp()
    app.mainloop()