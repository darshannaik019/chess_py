import pygame
import chess
from typing import Optional, List, Tuple, Dict
from src.settings import Settings
from src.piece import AnimatedPiece
from src.utils import AssetManager

class ChessBoardGUI:
    """
    Manages the GUI presentation, grid math, coordinate conversions, 
    and mouse interaction (click-to-move, drag-and-drop) of the chessboard.
    """
    def __init__(self, settings: Settings, assets: AssetManager):
        self.settings = settings
        self.assets = assets
        
        self.flipped = False  # True if Black is at the bottom
        self.square_size = 80
        self.board_rect = pygame.Rect(50, 50, 640, 640)
        
        # Selection and interaction states
        self.selected_square: Optional[chess.Square] = None
        self.hovered_square: Optional[chess.Square] = None
        self.dragging_square: Optional[chess.Square] = None
        self.drag_offset: Tuple[int, int] = (0, 0)
        self.drag_pos: Tuple[int, int] = (0, 0)
        
        # Animated pieces mapping: square -> AnimatedPiece
        self.animated_pieces: Dict[chess.Square, AnimatedPiece] = {}

    def resize(self, screen_width: int, screen_height: int):
        """Adjusts the board coordinates and square sizes to fit the screen size."""
        # Calculate available height and allocate a square board area
        margin_y = 50
        available_height = max(400, screen_height - (margin_y * 2))
        
        # Chess board is a square
        self.square_size = available_height // 8
        board_w_h = self.square_size * 8
        
        # Center vertically, place on the left side
        self.board_rect = pygame.Rect(50, (screen_height - board_w_h) // 2, board_w_h, board_w_h)

    def square_to_coords(self, square: chess.Square) -> Tuple[int, int]:
        """Converts a chess.Square (0-63) to screen pixel coordinates (center of square)."""
        file_idx = chess.square_file(square)
        rank_idx = chess.square_rank(square)
        
        if self.flipped:
            col = 7 - file_idx
            row = rank_idx
        else:
            col = file_idx
            row = 7 - rank_idx
            
        x = self.board_rect.x + (col * self.square_size) + (self.square_size // 2)
        y = self.board_rect.y + (row * self.square_size) + (self.square_size // 2)
        return x, y

    def coords_to_square(self, pos: Tuple[int, int]) -> Optional[chess.Square]:
        """Converts screen pixel coordinates (X, Y) to a chess.Square. Returns None if out of board bounds."""
        if not self.board_rect.collidepoint(pos):
            return None
            
        col = (pos[0] - self.board_rect.x) // self.square_size
        row = (pos[1] - self.board_rect.y) // self.square_size
        
        # Bound safeguard
        col = max(0, min(7, col))
        row = max(0, min(7, row))
        
        if self.flipped:
            file_idx = 7 - col
            rank_idx = row
        else:
            file_idx = col
            rank_idx = 7 - row
            
        return chess.square(file_idx, rank_idx)

    def sync_pieces(self, board: chess.Board, animated: bool = True):
        """
        Synchronizes Pygame animated pieces with the current python-chess board state.
        Triggers transition animations for moved pieces.
        """
        current_squares = set()
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                current_squares.add(square)
                symbol = piece.symbol()
                # Map standard chess symbols to our asset names (e.g. 'P' -> 'wP', 'p' -> 'bP')
                color_prefix = 'w' if piece.color == chess.WHITE else 'b'
                piece_name = f"{color_prefix}{symbol.upper()}"
                
                target_x, target_y = self.square_to_coords(square)
                
                if square in self.animated_pieces and self.animated_pieces[square].name == piece_name:
                    # Piece is already there, update animation target (just in case board resized)
                    if not self.animated_pieces[square].animating:
                        self.animated_pieces[square].set_position(target_x, target_y)
                else:
                    # Find if a piece moved here from elsewhere to trigger animation
                    found_moved = False
                    if animated:
                        for prev_sq, anim_piece in list(self.animated_pieces.items()):
                            if anim_piece.name == piece_name and prev_sq not in current_squares:
                                # We found the piece that moved to this square! Animating it.
                                anim_piece.animate_to(target_x, target_y)
                                self.animated_pieces[square] = anim_piece
                                del self.animated_pieces[prev_sq]
                                found_moved = True
                                break
                                
                    if not found_moved:
                        # New piece spawn
                        self.animated_pieces[square] = AnimatedPiece(piece_name, target_x, target_y)
                        
        # Remove pieces that are no longer on the board
        for sq in list(self.animated_pieces.keys()):
            if sq not in current_squares:
                # If we are dragging this piece, don't remove it yet
                if sq != self.dragging_square:
                    del self.animated_pieces[sq]

    def update(self) -> bool:
        """Updates all piece animations. Returns True if any animation is active."""
        animating = False
        for piece in self.animated_pieces.values():
            if piece.update():
                animating = True
        return animating

    def draw(self, surface: pygame.Surface, board: chess.Board, last_move: Optional[chess.Move] = None):
        """Renders the chessboard squares, highlights, coordinates, and pieces."""
        colors = self.settings.get_colors()
        
        # 1. Draw chessboard grid
        for row in range(8):
            for col in range(8):
                # Calculate screen coordinates of the square
                rect = pygame.Rect(
                    self.board_rect.x + (col * self.square_size),
                    self.board_rect.y + (row * self.square_size),
                    self.square_size,
                    self.square_size
                )
                
                # Check square color
                is_light = (row + col) % 2 == 0
                color = colors["light"] if is_light else colors["dark"]
                pygame.draw.rect(surface, color, rect)

        # 2. Highlight last move (start and destination squares)
        if last_move:
            for sq in [last_move.from_square, last_move.to_square]:
                x, y = self.square_to_coords(sq)
                rect = pygame.Rect(
                    x - self.square_size // 2,
                    y - self.square_size // 2,
                    self.square_size,
                    self.square_size
                )
                # Draw semi-transparent overlay
                highlight_surface = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
                highlight_surface.fill((*colors["last_move"], 100))  # 100 opacity
                surface.blit(highlight_surface, rect)

        # 3. Highlight selected piece square
        if self.selected_square is not None:
            x, y = self.square_to_coords(self.selected_square)
            rect = pygame.Rect(
                x - self.square_size // 2,
                y - self.square_size // 2,
                self.square_size,
                self.square_size
            )
            pygame.draw.rect(surface, colors["selected"], rect, 3)

        # 4. Highlight King in check
        if board.is_check():
            king_square = board.king(board.turn)
            if king_square is not None:
                x, y = self.square_to_coords(king_square)
                rect = pygame.Rect(
                    x - self.square_size // 2,
                    y - self.square_size // 2,
                    self.square_size,
                    self.square_size
                )
                # Draw red check indicator
                highlight_surface = pygame.Surface((self.square_size, self.square_size), pygame.SRCALPHA)
                highlight_surface.fill((*colors["check"], 140))
                surface.blit(highlight_surface, rect)

        # 5. Highlight legal moves (if a piece is selected)
        if self.selected_square is not None:
            legal_squares = [move.to_square for move in board.legal_moves if move.from_square == self.selected_square]
            for sq in legal_squares:
                x, y = self.square_to_coords(sq)
                
                # Check if there is an opponent piece on that square to capture
                dest_piece = board.piece_at(sq)
                if dest_piece:
                    # Draw a nice hollow ring around the piece for captures
                    pygame.draw.circle(surface, colors["legal"], (x, y), self.square_size // 2.3, 4)
                else:
                    # Draw a neat filled dot for empty squares
                    pygame.draw.circle(surface, colors["legal"], (x, y), self.square_size // 6)

        # 6. Draw Coordinate Labels (files: a-h, ranks: 1-8)
        font = self.assets.get_font(18, bold=True)
        # We place these around the margins of the board
        for i in range(8):
            file_char = chr(ord('a') + (7 - i if self.flipped else i))
            rank_char = str(i + 1 if self.flipped else 8 - i)
            
            # Rank label (left side)
            rank_text = font.render(rank_char, True, colors["text"])
            ry = self.board_rect.y + (i * self.square_size) + (self.square_size // 2)
            surface.blit(rank_text, (self.board_rect.x - 25, ry - rank_text.get_height() // 2))
            
            # File label (bottom side)
            file_text = font.render(file_char, True, colors["text"])
            fx = self.board_rect.x + (i * self.square_size) + (self.square_size // 2)
            surface.blit(file_text, (fx - file_text.get_width() // 2, self.board_rect.bottom + 10))

        # 7. Render Chess Pieces (excluding the one being dragged, which is drawn last)
        piece_images = self.assets.load_pieces(self.square_size)
        dragging_piece: Optional[AnimatedPiece] = None
        
        for sq, anim_piece in self.animated_pieces.items():
            img = piece_images.get(anim_piece.name)
            if img:
                if sq == self.dragging_square:
                    dragging_piece = anim_piece
                else:
                    anim_piece.draw(surface, img, dragging=False)
                    
        # Render the dragged piece on top of everything
        if dragging_piece and self.dragging_square is not None:
            img = piece_images.get(dragging_piece.name)
            if img:
                # Center on the mouse drag position
                dragging_piece.x = self.drag_pos[0]
                dragging_piece.y = self.drag_pos[1]
                dragging_piece.draw(surface, img, dragging=True)
