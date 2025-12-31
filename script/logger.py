import os
import logging
from datetime import datetime

class Logger:
    _instance = None

    def __new__(cls, settings_manager=None):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance.settings = settings_manager
            cls._instance.log_dir = os.path.join(os.getcwd(), "log")
            os.makedirs(cls._instance.log_dir, exist_ok=True)
            cls._instance.logger = logging.getLogger("DOSManager")
            cls._instance.logger.setLevel(logging.INFO)
            cls._instance._setup_handler()
        return cls._instance

    def _setup_handler(self):
        # Clear existing handlers
        if self.logger.handlers:
            self.logger.handlers.clear()
            
        if self.settings and self.settings.get("enable_logging", False):
            filename = datetime.now().strftime("%Y-%m-%d.log")
            filepath = os.path.join(self.log_dir, filename)
            handler = logging.FileHandler(filepath, encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        else:
            self.logger.addHandler(logging.NullHandler())

    def refresh_settings(self):
        self._setup_handler()

    def log(self, message, level="info", category=None):
        if not self.settings or not self.settings.get("enable_logging", False): return
        
        # Check category filter
        if category:
            setting_key = f"log_{category}"
            # Default to True if category setting not found? Or False?
            # User asked to "enable/disable what to log". So default should probably be True if not set, or False.
            # Let's assume if key exists and is False, we skip.
            if self.settings.get(setting_key, True) is False: return

        if level == "info": self.logger.info(message)
        elif level == "warning": self.logger.warning(message)
        elif level == "error": self.logger.error(message)
        elif level == "debug": self.logger.debug(message)

    def clear_logs(self):
        if os.path.exists(self.log_dir):
            for f in os.listdir(self.log_dir):
                if f.endswith(".log"):
                    try: os.remove(os.path.join(self.log_dir, f))
                    except: pass
