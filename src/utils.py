import os
import math
import wave
import io
import urllib.request
import logging
import pygame
from typing import Dict

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class AssetManager:
    """
    Manages loading and downloading of game assets (images, sounds, fonts).
    Provides procedural audio fallbacks if sound files are missing.
    """
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    IMAGES_DIR = os.path.join(ASSETS_DIR, "images")
    SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")
    FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")

    # URL mappings for downloading pieces from Chessboard.js GitHub raw repository
    PIECE_URLS = {
        name: f"https://raw.githubusercontent.com/oakmac/chessboardjs/master/website/img/chesspieces/wikipedia/{name}.png"
        for name in ["wP", "wN", "wB", "wR", "wQ", "wK", "bP", "bN", "bB", "bR", "bQ", "bK"]
    }

    def __init__(self):
        # Create asset paths if they don't exist
        for d in [self.IMAGES_DIR, self.SOUNDS_DIR, self.FONTS_DIR]:
            os.makedirs(d, exist_ok=True)
            
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self.pieces: Dict[str, pygame.Surface] = {}
        self.fonts: Dict[str, pygame.font.Font] = {}

    def download_chess_pieces(self) -> bool:
        """
        Downloads standard transparent chess piece PNG files from Wikimedia Commons
        if they are not already cached.
        """
        logging.info("Checking chess piece assets...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        success = True
        
        for piece_name, url in self.PIECE_URLS.items():
            dest_path = os.path.join(self.IMAGES_DIR, f"{piece_name}.png")
            if not os.path.exists(dest_path):
                logging.info(f"Downloading {piece_name}.png...")
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
                        out_file.write(response.read())
                except Exception as e:
                    logging.error(f"Failed to download {piece_name}: {e}")
                    success = False
            else:
                logging.debug(f"{piece_name}.png already exists.")
        return success

    def load_pieces(self, size: int = 80) -> Dict[str, pygame.Surface]:
        """Loads piece images and scales them to the requested size."""
        self.download_chess_pieces()
        
        for name in self.PIECE_URLS.keys():
            img_path = os.path.join(self.IMAGES_DIR, f"{name}.png")
            if os.path.exists(img_path):
                try:
                    img = pygame.image.load(img_path).convert_alpha()
                    self.pieces[name] = pygame.transform.smoothscale(img, (size, size))
                except Exception as e:
                    logging.error(f"Error loading piece {name}: {e}")
                    self.pieces[name] = self._create_fallback_piece_surface(name, size)
            else:
                self.pieces[name] = self._create_fallback_piece_surface(name, size)
                
        return self.pieces

    def _create_fallback_piece_surface(self, name: str, size: int) -> pygame.Surface:
        """Creates a modern geometric text-based piece surface if image files are missing."""
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        color = (255, 255, 255) if name[0] == 'w' else (20, 20, 20)
        border_color = (20, 20, 20) if name[0] == 'w' else (240, 240, 240)
        
        # Draw a beautiful circle
        center = size // 2
        radius = int(size * 0.4)
        pygame.draw.circle(surface, color, (center, center), radius)
        pygame.draw.circle(surface, border_color, (center, center), radius, 3)
        
        # Add piece symbol text
        font = pygame.font.SysFont("arial", int(size * 0.5), bold=True)
        txt = font.render(name[1], True, border_color)
        txt_rect = txt.get_rect(center=(center, center))
        surface.blit(txt, txt_rect)
        return surface

    def load_sounds(self, sound_enabled: bool = True):
        """Loads game sounds, generating them procedurally if files are missing."""
        sound_names = ["move", "capture", "check", "game_over"]
        
        if not pygame.mixer or not pygame.mixer.get_init():
            logging.warning("Pygame mixer is not initialized. Audio disabled.")
            return

        for name in sound_names:
            file_path = os.path.join(self.SOUNDS_DIR, f"{name}.wav")
            if os.path.exists(file_path):
                try:
                    self.sounds[name] = pygame.mixer.Sound(file_path)
                except Exception as e:
                    logging.error(f"Error loading sound {name}: {e}")
                    self.sounds[name] = self._generate_procedural_sound(name)
            else:
                # Generate and save procedurally
                sound = self._generate_procedural_sound(name)
                self.sounds[name] = sound
                try:
                    # Save wav file for caching
                    wav_data = self._generate_wav_bytes(name)
                    with open(file_path, "wb") as f:
                        f.write(wav_data)
                except Exception as e:
                    logging.error(f"Failed to cache procedural sound {name}: {e}")

    def play_sound(self, name: str, enabled: bool = True):
        """Plays the requested sound if enabled and loaded."""
        if not enabled:
            return
        sound = self.sounds.get(name)
        if sound:
            try:
                sound.play()
            except Exception as e:
                logging.error(f"Error playing sound {name}: {e}")

    def get_font(self, size: int, bold: bool = False) -> pygame.font.Font:
        """Returns a font object, falling back to standard font if custom ones fail."""
        font_key = f"standard_{size}_{bold}"
        if font_key in self.fonts:
            return self.fonts[font_key]
            
        # Try to load a nice modern system font, fallback to default Pygame font
        system_fonts = ["segoeui", "helvetica", "arial", "sans-serif"]
        font = None
        for sys_font in system_fonts:
            try:
                font = pygame.font.SysFont(sys_font, size, bold=bold)
                if font:
                    break
            except Exception:
                continue
                
        if not font:
            font = pygame.font.Font(None, size)
            
        self.fonts[font_key] = font
        return font

    def _generate_procedural_sound(self, name: str) -> pygame.mixer.Sound:
        """Generates a pygame Sound directly from generated WAV bytes."""
        wav_bytes = self._generate_wav_bytes(name)
        file_like = io.BytesIO(wav_bytes)
        return pygame.mixer.Sound(file_like)

    def _generate_wav_bytes(self, name: str, rate: int = 22050) -> bytes:
        """
        Synthesizes sound effects procedurally and returns them as WAV bytes.
        """
        buffer = io.BytesIO()
        
        # Audio generation constants
        duration = 0.1
        freq_start = 220.0
        freq_end = 220.0
        noise_level = 0.0
        
        if name == "move":
            duration = 0.08
            freq_start = 250.0
            freq_end = 80.0
            noise_level = 0.05
        elif name == "capture":
            duration = 0.12
            freq_start = 380.0
            freq_end = 40.0
            noise_level = 0.25  # High noise for a 'crunch' impact
        elif name == "check":
            # Check sound: two quick tones
            duration = 0.2
            rate = 22050
            num_samples = int(duration * rate)
            
            with wave.open(buffer, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(rate)
                
                half = num_samples // 2
                # Tone 1: 523Hz (C5)
                for i in range(half):
                    envelope = (half - i) / half
                    t = i / rate
                    val = int(25000 * envelope * math.sin(2 * math.pi * 523.25 * t))
                    wav.writeframesraw(val.to_bytes(2, byteorder='little', signed=True))
                # Tone 2: 784Hz (G5)
                for i in range(half):
                    envelope = (half - i) / half
                    t = i / rate
                    val = int(25000 * envelope * math.sin(2 * math.pi * 783.99 * t))
                    wav.writeframesraw(val.to_bytes(2, byteorder='little', signed=True))
            buffer.seek(0)
            return buffer.read()
            
        elif name == "game_over":
            # Descending sad minor chord progression
            duration = 0.8
            num_samples = int(duration * rate)
            with wave.open(buffer, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(rate)
                
                # We blend a standard C-minor triad: 130Hz (C3), 155Hz (Eb3), 196Hz (G3)
                for i in range(num_samples):
                    envelope = (num_samples - i) / num_samples
                    t = i / rate
                    # Play notes with decaying amplitude
                    v1 = math.sin(2 * math.pi * 130.81 * t)
                    v2 = math.sin(2 * math.pi * 155.56 * t) * 0.8
                    v3 = math.sin(2 * math.pi * 196.00 * t) * 0.7
                    mixed = (v1 + v2 + v3) / 2.5
                    val = int(28000 * envelope * mixed)
                    wav.writeframesraw(val.to_bytes(2, byteorder='little', signed=True))
            buffer.seek(0)
            return buffer.read()

        # Generate single-tone sweep sounds (move, capture)
        num_samples = int(duration * rate)
        import random
        
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            
            phase = 0.0
            for i in range(num_samples):
                # Interpolate frequency exponentially
                pct = i / num_samples
                envelope = (num_samples - i) / num_samples
                current_freq = freq_start + (freq_end - freq_start) * pct
                
                # Advance phase based on instantaneous frequency
                phase += (2.0 * math.pi * current_freq) / rate
                
                sine_val = math.sin(phase)
                noise_val = random.uniform(-1.0, 1.0)
                
                # Blend sine and white noise
                sample = sine_val * (1.0 - noise_level) + noise_val * noise_level
                val = int(28000 * envelope * sample)
                wav.writeframesraw(val.to_bytes(2, byteorder='little', signed=True))
                
        buffer.seek(0)
        return buffer.read()
