import os
import json
import logging

class Settings:
    """
    Manages game configuration and settings persistence.
    """
    # Application Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    SAVES_DIR = os.path.join(BASE_DIR, "saves")
    DB_DIR = os.path.join(BASE_DIR, "database")
    SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

    # Ensure required directories exist
    for directory in [SAVES_DIR, DB_DIR]:
        os.makedirs(directory, exist_ok=True)

    # Game Modes
    MODE_PVP = "PVP"    # Player vs Player (local)
    MODE_PVC = "PVC"    # Player vs Computer
    MODE_CVC = "CVC"    # Computer vs Computer
    MODE_TRAINING = "TRAINING"

    # AI Difficulty levels
    DIFFICULTY_EASY = "EASY"
    DIFFICULTY_MEDIUM = "MEDIUM"
    DIFFICULTY_HARD = "HARD"
    DIFFICULTY_EXPERT = "EXPERT"

    # Piece Styles
    STYLE_STANDARD = "cburnett"

    # Color Themes definition
    THEMES = {
        "wood": {
            "light": (240, 217, 181),
            "dark": (181, 136, 99),
            "selected": (186, 202, 43),
            "legal": (130, 151, 105),
            "check": (231, 76, 60),
            "last_move": (205, 210, 106),
            "bg": (46, 32, 26),
            "panel_bg": (62, 44, 36),
            "text": (240, 240, 240),
            "accent": (212, 163, 115)
        },
        "glass": {
            "light": (44, 47, 51),
            "dark": (28, 30, 33),
            "selected": (0, 180, 216),
            "legal": (72, 202, 228),
            "check": (242, 100, 25),
            "last_move": (58, 80, 107),
            "bg": (15, 17, 20),
            "panel_bg": (24, 27, 31),
            "text": (224, 225, 226),
            "accent": (0, 180, 216)
        },
        "modern_flat": {
            "light": (238, 238, 210),
            "dark": (118, 150, 86),
            "selected": (247, 247, 105),
            "legal": (130, 180, 80),
            "check": (235, 97, 85),
            "last_move": (186, 202, 43),
            "bg": (34, 34, 34),
            "panel_bg": (46, 46, 46),
            "text": (240, 240, 240),
            "accent": (118, 150, 86)
        },
        "classic": {
            "light": (240, 240, 240),
            "dark": (80, 80, 80),
            "selected": (255, 255, 100),
            "legal": (100, 200, 100),
            "check": (255, 100, 100),
            "last_move": (220, 220, 100),
            "bg": (20, 20, 20),
            "panel_bg": (40, 40, 40),
            "text": (255, 255, 255),
            "accent": (200, 200, 200)
        }
    }

    # Time Controls presets (in seconds)
    TIME_PRESETS = {
        "Bullet (1+0)": (60, 0),
        "Blitz (3+2)": (180, 2),
        "Blitz (5+0)": (300, 0),
        "Rapid (10+0)": (600, 0),
        "Rapid (15+10)": (900, 10),
        "Classical (30+0)": (1800, 0),
        "Infinite": (0, 0)
    }

    def __init__(self):
        # Default Settings
        self.width = 1200
        self.height = 800
        self.fullscreen = False
        self.theme = "wood"
        self.piece_style = self.STYLE_STANDARD
        self.sound_enabled = True
        self.music_enabled = False
        self.game_mode = self.MODE_PVP
        self.difficulty = self.DIFFICULTY_MEDIUM
        self.stockfish_path = "" # Empty means use fallback AI
        self.best_move_suggestion = False
        self.eval_bar_enabled = True
        
        # Default time control: Rapid (10+0)
        self.time_limit = 600
        self.time_increment = 0

        self.load()

    def save(self):
        """Saves current settings to disk in JSON format."""
        data = {
            "width": self.width,
            "height": self.height,
            "fullscreen": self.fullscreen,
            "theme": self.theme,
            "piece_style": self.piece_style,
            "sound_enabled": self.sound_enabled,
            "music_enabled": self.music_enabled,
            "game_mode": self.game_mode,
            "difficulty": self.difficulty,
            "stockfish_path": self.stockfish_path,
            "best_move_suggestion": self.best_move_suggestion,
            "eval_bar_enabled": self.eval_bar_enabled,
            "time_limit": self.time_limit,
            "time_increment": self.time_increment
        }
        try:
            with open(self.SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving settings: {e}")

    def load(self):
        """Loads settings from disk if the file exists."""
        if not os.path.exists(self.SETTINGS_FILE):
            return
        try:
            with open(self.SETTINGS_FILE, "r") as f:
                data = json.load(f)
            
            self.width = data.get("width", self.width)
            self.height = data.get("height", self.height)
            self.fullscreen = data.get("fullscreen", self.fullscreen)
            self.theme = data.get("theme", self.theme)
            self.piece_style = data.get("piece_style", self.piece_style)
            self.sound_enabled = data.get("sound_enabled", self.sound_enabled)
            self.music_enabled = data.get("music_enabled", self.music_enabled)
            self.game_mode = data.get("game_mode", self.game_mode)
            self.difficulty = data.get("difficulty", self.difficulty)
            self.stockfish_path = data.get("stockfish_path", self.stockfish_path)
            self.best_move_suggestion = data.get("best_move_suggestion", self.best_move_suggestion)
            self.eval_bar_enabled = data.get("eval_bar_enabled", self.eval_bar_enabled)
            self.time_limit = data.get("time_limit", self.time_limit)
            self.time_increment = data.get("time_increment", self.time_increment)
        except Exception as e:
            logging.error(f"Error loading settings: {e}")

    def get_colors(self):
        """Returns colors dictionary for current theme."""
        return self.THEMES.get(self.theme, self.THEMES["wood"])
