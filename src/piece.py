import pygame
import time

class AnimatedPiece:
    """
    Manages the visual presentation of a chess piece, including smooth 
    movement animations (using linear interpolation) between board coordinates.
    """
    def __init__(self, name: str, x: float, y: float):
        """
        Args:
            name: String identifier (e.g. 'wP' for White Pawn, 'bK' for Black King)
            x: Initial screen X coordinate
            y: Initial screen Y coordinate
        """
        self.name = name
        self.x = x
        self.y = y
        self.target_x = x
        self.target_y = y
        
        # Animation parameters
        self.animating = False
        self.animation_duration = 0.2  # Duration in seconds
        self.start_time = 0.0
        self.start_x = x
        self.start_y = y

    def set_position(self, x: float, y: float):
        """Instantly sets the position of the piece without animation."""
        self.x = x
        self.y = y
        self.target_x = x
        self.target_y = y
        self.animating = False

    def animate_to(self, target_x: float, target_y: float):
        """Triggers a smooth movement animation to target coordinates."""
        if self.x == target_x and self.y == target_y:
            return
            
        self.start_x = self.x
        self.start_y = self.y
        self.target_x = target_x
        self.target_y = target_y
        self.start_time = time.time()
        self.animating = True

    def update(self) -> bool:
        """
        Updates the piece position. 
        Returns True if the piece is still animating, False otherwise.
        """
        if not self.animating:
            return False

        elapsed = time.time() - self.start_time
        if elapsed >= self.animation_duration:
            # Animation complete
            self.x = self.target_x
            self.y = self.target_y
            self.animating = False
            return False
            
        # Linear interpolation (lerp)
        t = elapsed / self.animation_duration
        # Apply smoothstep for extra elegance
        t_smooth = t * t * (3 - 2 * t)
        
        self.x = self.start_x + (self.target_x - self.start_x) * t_smooth
        self.y = self.start_y + (self.target_y - self.start_y) * t_smooth
        return True

    def draw(self, surface: pygame.Surface, image: pygame.Surface, dragging: bool = False):
        """Renders the piece image centered at its current coordinates."""
        # Draw shadow if dragging for a 3D lift effect
        rect = image.get_rect(center=(int(self.x), int(self.y)))
        
        if dragging:
            # Draw subtle offset shadow
            shadow_surface = image.copy()
            shadow_surface.fill((0, 0, 0, 80), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(shadow_surface, (rect.x + 4, rect.y + 4))
            
        surface.blit(image, rect)
