import pygame
import chess
from typing import List, Tuple, Optional, Callable, Dict
from src.settings import Settings
from src.utils import AssetManager

class Button:
    """
    A modern custom Pygame button with hover effects, rounded corners,
    text rendering, and disabled state support.
    """
    def __init__(self, rect: pygame.Rect, text: str, font: pygame.font.Font, 
                 bg_color: Tuple[int, int, int], hover_color: Tuple[int, int, int], 
                 text_color: Tuple[int, int, int], callback: Optional[Callable[[], None]] = None,
                 border_radius: int = 8):
        self.rect = rect
        self.text = text
        self.font = font
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.callback = callback
        self.border_radius = border_radius
        self.hovered = False
        self.enabled = True

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Processes mouse movement and click events. Returns True if button is clicked."""
        if not self.enabled:
            return False
            
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.rect.collidepoint(event.pos):
                if self.callback:
                    self.callback()
                return True
        return False

    def draw(self, surface: pygame.Surface):
        """Renders the button with current hover/active states."""
        if not self.enabled:
            # Draw faded gray out button
            bg = (80, 80, 80)
            txt_color = (130, 130, 130)
        else:
            bg = self.hover_color if self.hovered else self.bg_color
            txt_color = self.text_color
            
        # Draw background with rounded corners
        pygame.draw.rect(surface, bg, self.rect, border_radius=self.border_radius)
        
        # Draw border
        border_color = (min(255, bg[0] + 30), min(255, bg[1] + 30), min(255, bg[2] + 30))
        pygame.draw.rect(surface, border_color, self.rect, width=1, border_radius=self.border_radius)
        
        # Render text
        txt_surf = self.font.render(self.text, True, txt_color)
        txt_rect = txt_surf.get_rect(center=self.rect.center)
        surface.blit(txt_surf, txt_rect)


class EvaluationBar:
    """
    Renders a vertical evaluation bar indicating the positional advantage
    between White and Black.
    """
    def __init__(self, rect: pygame.Rect, assets: AssetManager):
        self.rect = rect
        self.assets = assets
        self.evaluation = 0.0  # + is white advantage, - is black

    def set_evaluation(self, eval_score: float):
        """Sets the evaluation value."""
        # Cap evaluation at +/- 10 pawns for rendering bounds
        self.evaluation = max(-10.0, min(10.0, eval_score))

    def draw(self, surface: pygame.Surface):
        # Draw background (Black advantage representation)
        pygame.draw.rect(surface, (30, 30, 30), self.rect, border_radius=5)
        
        # Calculate White advantage height (0 advantage = 50% height)
        # evaluation goes from -10 to +10, map to 0 to 1
        pct = (self.evaluation + 10.0) / 20.0
        pct = max(0.0, min(1.0, pct))
        
        # Pygame Y starts at top, so White bar is drawn from bottom up
        white_height = int(self.rect.height * pct)
        white_rect = pygame.Rect(
            self.rect.x, 
            self.rect.y + (self.rect.height - white_height),
            self.rect.width,
            white_height
        )
        
        pygame.draw.rect(surface, (230, 230, 230), white_rect, border_radius=5)
        
        # Draw thin center dividing line
        center_y = self.rect.y + self.rect.height // 2
        pygame.draw.line(surface, (128, 128, 128), (self.rect.x, center_y), (self.rect.right, center_y), 2)
        
        # Draw numerical label text
        font = self.assets.get_font(14, bold=True)
        eval_str = f"{self.evaluation:+.1f}" if abs(self.evaluation) < 90 else ("M" if self.evaluation > 0 else "-M")
        
        # Render text in black or white depending on who is winning
        text_color = (0, 0, 0) if self.evaluation >= 0 else (255, 255, 255)
        text_surf = font.render(eval_str, True, text_color)
        
        # Place text at the winning side of the bar
        if self.evaluation >= 0:
            tx = self.rect.centerx - text_surf.get_width() // 2
            ty = self.rect.bottom - 25
        else:
            tx = self.rect.centerx - text_surf.get_width() // 2
            ty = self.rect.y + 10
            
        surface.blit(text_surf, (tx, ty))


class MoveHistoryPanel:
    """
    Displays a scrollable move log using standard algebraic notation (SAN).
    """
    def __init__(self, rect: pygame.Rect, settings: Settings, assets: AssetManager):
        self.rect = rect
        self.settings = settings
        self.assets = assets
        self.moves: List[str] = []
        
        # Scrolling details
        self.scroll_y = 0
        self.line_height = 28
        self.max_visible_lines = self.rect.height // self.line_height
        
    def update_moves(self, move_log: List[str]):
        """Updates the list of move strings and auto-scrolls to the bottom."""
        self.moves = move_log
        # Automatically scroll to show the latest moves
        total_lines = (len(self.moves) + 1) // 2
        if total_lines > self.max_visible_lines:
            self.scroll_y = (total_lines - self.max_visible_lines) * self.line_height
        else:
            self.scroll_y = 0

    def handle_event(self, event: pygame.event.Event):
        """Processes scroll-wheel events for moving history."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                total_lines = (len(self.moves) + 1) // 2
                max_scroll = max(0, (total_lines - self.max_visible_lines) * self.line_height)
                if event.button == 4: # Scroll Up
                    self.scroll_y = max(0, self.scroll_y - self.line_height)
                elif event.button == 5: # Scroll Down
                    self.scroll_y = min(max_scroll, self.scroll_y + self.line_height)

    def draw(self, surface: pygame.Surface):
        colors = self.settings.get_colors()
        
        # Draw background panel
        pygame.draw.rect(surface, colors["panel_bg"], self.rect, border_radius=10)
        pygame.draw.rect(surface, colors["accent"], self.rect, width=1, border_radius=10)
        
        # Create a clipped surface for move items
        clip_rect = self.rect.inflate(-20, -20)
        sub_surf = surface.subsurface(clip_rect)
        
        # Draw move items
        font = self.assets.get_font(18)
        bold_font = self.assets.get_font(18, bold=True)
        
        y_offset = -self.scroll_y
        
        for i in range(0, len(self.moves), 2):
            move_num = (i // 2) + 1
            white_move = self.moves[i]
            black_move = self.moves[i+1] if i + 1 < len(self.moves) else ""
            
            # If line is outside drawing clip, skip it
            if y_offset + self.line_height < 0:
                y_offset += self.line_height
                continue
            if y_offset > clip_rect.height:
                break
                
            # Draw Move Number
            num_surf = bold_font.render(f"{move_num}.", True, colors["accent"])
            sub_surf.blit(num_surf, (5, y_offset))
            
            # Draw White Move
            w_surf = font.render(white_move, True, colors["text"])
            sub_surf.blit(w_surf, (60, y_offset))
            
            # Draw Black Move
            if black_move:
                b_surf = font.render(black_move, True, colors["text"])
                sub_surf.blit(b_surf, (160, y_offset))
                
            y_offset += self.line_height


class CapturedPiecesWidget:
    """
    Displays the captured pieces and computes the material advantage score.
    """
    def __init__(self, rect: pygame.Rect, assets: AssetManager):
        self.rect = rect
        self.assets = assets
        self.captured_white: List[str] = []
        self.captured_black: List[str] = []
        self.score_diff = 0  # Material advantage (+ is white, - is black)

    def update_captured(self, board: chess.Board):
        """Recalculates captured pieces by comparing starting set to current set."""
        starting_counts = {
            'P': 8, 'N': 2, 'B': 2, 'R': 2, 'Q': 1,
            'p': 8, 'n': 2, 'b': 2, 'r': 2, 'q': 1
        }
        
        # Count remaining pieces on board
        current_counts = {k: 0 for k in starting_counts.keys()}
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.piece_type != chess.KING:
                symbol = piece.symbol()
                if symbol in current_counts:
                    current_counts[symbol] += 1
                    
        # Calculate captured items
        self.captured_white.clear()  # Pieces white has captured (black pieces)
        self.captured_black.clear()  # Pieces black has captured (white pieces)
        
        # Material evaluation sum
        material_values = {'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9}
        white_val = 0
        black_val = 0
        
        # White captures (lowercase symbols in python-chess represent Black pieces)
        for char, start_count in starting_counts.items():
            diff = start_count - current_counts[char]
            if diff > 0:
                for _ in range(diff):
                    if char.islower(): # Black piece captured by White
                        self.captured_white.append(f"b{char.upper()}")
                        white_val += material_values.get(char, 0)
                    else: # White piece captured by Black
                        self.captured_black.append(f"w{char}")
                        black_val += material_values.get(char.lower(), 0)
                        
        self.score_diff = white_val - black_val

    def draw(self, surface: pygame.Surface, colors: Dict[str, Tuple[int, int, int]]):
        # Render captured list for White (top row of widget)
        # Scales icons down
        piece_imgs = self.assets.load_pieces(24) # Small size
        
        # Draw White Captures (black pieces)
        x_offset = self.rect.x
        for p in sorted(self.captured_white, key=lambda x: x[1]):
            img = piece_imgs.get(p)
            if img:
                surface.blit(img, (x_offset, self.rect.y))
                x_offset += 16
                
        # Draw material balance score if white is leading
        font = self.assets.get_font(16, bold=True)
        if self.score_diff > 0:
            txt = font.render(f"+{self.score_diff}", True, colors["accent"])
            surface.blit(txt, (x_offset + 5, self.rect.y + 4))

        # Draw Black Captures (white pieces)
        x_offset = self.rect.x
        y_bottom = self.rect.y + 30
        for p in sorted(self.captured_black, key=lambda x: x[1]):
            img = piece_imgs.get(p)
            if img:
                surface.blit(img, (x_offset, y_bottom))
                x_offset += 16
                
        # Draw material balance score if black is leading
        if self.score_diff < 0:
            txt = font.render(f"+{abs(self.score_diff)}", True, colors["accent"])
            surface.blit(txt, (x_offset + 5, y_bottom + 4))


class PromotionModal:
    """
    Popup overlay for pawn promotion, allowing selection of Q, R, B, or N.
    """
    def __init__(self, rect: pygame.Rect, assets: AssetManager, color: chess.Color):
        self.rect = rect
        self.assets = assets
        self.color = color
        
        # Define 4 selection squares
        self.size = rect.width // 4
        self.squares: List[Tuple[chess.PieceType, pygame.Rect]] = []
        
        piece_types = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
        for i, pt in enumerate(piece_types):
            sq_rect = pygame.Rect(rect.x + (i * self.size), rect.y, self.size, self.size)
            self.squares.append((pt, sq_rect))

    def handle_click(self, pos: Tuple[int, int]) -> Optional[chess.PieceType]:
        """Returns the clicked PieceType or None if clicked outside."""
        if not self.rect.collidepoint(pos):
            return None
        for pt, sq_rect in self.squares:
            if sq_rect.collidepoint(pos):
                return pt
        return None

    def draw(self, surface: pygame.Surface):
        # Draw transparent overlay background
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))
        
        # Draw popup container
        pygame.draw.rect(surface, (40, 40, 40), self.rect, border_radius=10)
        pygame.draw.rect(surface, (200, 200, 200), self.rect, width=2, border_radius=10)
        
        # Load piece icons (scaled to 80% square size)
        piece_imgs = self.assets.load_pieces(int(self.size * 0.8))
        color_prefix = 'w' if self.color == chess.WHITE else 'b'
        
        mapping = {
            chess.QUEEN: f"{color_prefix}Q",
            chess.ROOK: f"{color_prefix}R",
            chess.BISHOP: f"{color_prefix}B",
            chess.KNIGHT: f"{color_prefix}N"
        }
        
        # Get mouse position for hovering highlights
        mouse_pos = pygame.mouse.get_pos()
        
        for pt, sq_rect in self.squares:
            # Draw hover state
            if sq_rect.collidepoint(mouse_pos):
                pygame.draw.rect(surface, (70, 70, 70), sq_rect, border_radius=10)
                pygame.draw.rect(surface, (0, 180, 216), sq_rect, width=2, border_radius=10)
            
            p_name = mapping[pt]
            img = piece_imgs.get(p_name)
            if img:
                img_rect = img.get_rect(center=sq_rect.center)
                surface.blit(img, img_rect)


class GameOverModal:
    """
    Renders the game over status, winner name, termination description, 
    and menu buttons in a pop-up dialog.
    """
    def __init__(self, rect: pygame.Rect, assets: AssetManager, 
                 title: str, reason: str, restart_callback: Callable[[], None], menu_callback: Callable[[], None]):
        self.rect = rect
        self.assets = assets
        self.title = title
        self.reason = reason
        
        font = assets.get_font(20, bold=True)
        btn_y = rect.bottom - 60
        self.restart_btn = Button(
            pygame.Rect(rect.x + 30, btn_y, 140, 40),
            "New Game", font, (72, 202, 228), (0, 180, 216), (255, 255, 255),
            restart_callback
        )
        self.menu_btn = Button(
            pygame.Rect(rect.right - 170, btn_y, 140, 40),
            "Main Menu", font, (60, 60, 60), (90, 90, 90), (255, 255, 255),
            menu_callback
        )

    def handle_event(self, event: pygame.event.Event):
        self.restart_btn.handle_event(event)
        self.menu_btn.handle_event(event)

    def draw(self, surface: pygame.Surface):
        # Draw translucent screen shadow
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        
        # Modal box
        pygame.draw.rect(surface, (30, 32, 35), self.rect, border_radius=15)
        pygame.draw.rect(surface, (72, 202, 228), self.rect, width=2, border_radius=15)
        
        # Modal Title
        title_font = self.assets.get_font(32, bold=True)
        title_surf = title_font.render(self.title, True, (255, 255, 255))
        title_rect = title_surf.get_rect(centerx=self.rect.centerx, y=self.rect.y + 35)
        surface.blit(title_surf, title_rect)
        
        # Termination reason description
        desc_font = self.assets.get_font(20)
        desc_surf = desc_font.render(self.reason, True, (180, 185, 190))
        desc_rect = desc_surf.get_rect(centerx=self.rect.centerx, y=self.rect.y + 90)
        surface.blit(desc_surf, desc_rect)
        
        # Draw buttons
        self.restart_btn.draw(surface)
        self.menu_btn.draw(surface)
