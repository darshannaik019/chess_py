import os
import sys
import queue
import logging
import pygame
import chess
from src.settings import Settings
from src.utils import AssetManager
from src.database import DatabaseManager
from src.game import ChessGame
from src.ui import Button, EvaluationBar, CapturedPiecesWidget, PromotionModal, GameOverModal, MoveHistoryPanel

# Initialize Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class ChessApp:
    """
    Main application orchestrator running the Pygame execution loop,
    handling window resizing, screen transitions, input dispatching,
    and thread-safe background AI queues.
    """
    STATE_MENU = "MENU"
    STATE_GAME = "GAME"
    STATE_SETTINGS = "SETTINGS"
    STATE_STATS = "STATS"

    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        pygame.display.set_caption("Chess Supreme")

        self.settings = Settings()
        self.assets = AssetManager()
        self.db = DatabaseManager(self.settings.DB_DIR)

        # Assets loading (including procedural sound caching)
        self.assets.load_sounds(self.settings.sound_enabled)
        
        # Screen Setup
        self.screen_flags = pygame.RESIZABLE
        if self.settings.fullscreen:
            self.screen_flags |= pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((self.settings.width, self.settings.height), self.screen_flags)
        
        # Load pieces and initialize Game coordinates
        self.assets.load_pieces(80)
        self.game = ChessGame(self.settings, self.assets, self.db)
        self.game.board_gui.resize(self.settings.width, self.settings.height)

        self.state = self.STATE_MENU
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Thread-safe queue for AI moves
        self.ai_move_queue = queue.Queue()
        
        # UI Component instances
        self.eval_bar = EvaluationBar(pygame.Rect(15, 50, 20, 640), self.assets)
        self.captured_widget = CapturedPiecesWidget(pygame.Rect(760, 100, 380, 60), self.assets)
        self.move_panel = MoveHistoryPanel(pygame.Rect(760, 220, 380, 340), self.settings, self.assets)
        
        # Game Modals & Pauses
        self.promotion_modal: Optional[PromotionModal] = None
        self.game_over_modal: Optional[GameOverModal] = None
        self.is_paused = False
        
        # Screen UI buttons lists
        self.menu_buttons: List[Button] = []
        self.settings_buttons: List[Button] = []
        self.stats_buttons: List[Button] = []
        self.game_buttons: List[Button] = []
        self.pause_buttons: List[Button] = []

        self._build_ui_buttons()

    def _build_ui_buttons(self):
        """Creates the UI buttons for all application states based on screen coordinates."""
        w, h = self.screen.get_size()
        font_large = self.assets.get_font(24, bold=True)
        font_medium = self.assets.get_font(20, bold=True)
        font_small = self.assets.get_font(16, bold=True)
        
        # --- 1. Main Menu Buttons ---
        menu_w = 260
        menu_h = 45
        menu_x = (w - menu_w) // 2
        
        self.menu_buttons = [
            Button(pygame.Rect(menu_x, h // 2 - 120, menu_w, menu_h), "Player vs Player", font_medium, (62, 44, 36), (212, 163, 115), (240, 240, 240), lambda: self.start_new_match(Settings.MODE_PVP)),
            Button(pygame.Rect(menu_x, h // 2 - 60, menu_w, menu_h), "Player vs Computer", font_medium, (62, 44, 36), (212, 163, 115), (240, 240, 240), lambda: self.start_new_match(Settings.MODE_PVC)),
            Button(pygame.Rect(menu_x, h // 2, menu_w, menu_h), "Computer vs Computer", font_medium, (62, 44, 36), (212, 163, 115), (240, 240, 240), lambda: self.start_new_match(Settings.MODE_CVC)),
            Button(pygame.Rect(menu_x, h // 2 + 60, menu_w, menu_h), "Training Mode", font_medium, (62, 44, 36), (212, 163, 115), (240, 240, 240), lambda: self.start_new_match(Settings.MODE_TRAINING)),
            Button(pygame.Rect(menu_x, h // 2 + 120, menu_w, menu_h), "Settings", font_medium, (62, 44, 36), (110, 110, 110), (240, 240, 240), lambda: self.set_state(self.STATE_SETTINGS)),
            Button(pygame.Rect(menu_x, h // 2 + 180, menu_w, menu_h), "Statistics", font_medium, (62, 44, 36), (110, 110, 110), (240, 240, 240), lambda: self.set_state(self.STATE_STATS)),
            Button(pygame.Rect(menu_x, h // 2 + 240, menu_w, menu_h), "Exit Game", font_medium, (120, 40, 40), (160, 50, 50), (255, 255, 255), self.quit_app)
        ]

        # --- 2. Settings Screen Buttons ---
        sett_w = 160
        sett_h = 40
        
        self.settings_buttons = [
            # Toggles
            Button(pygame.Rect(w // 2 + 50, 150, sett_w, sett_h), "Board Theme", font_small, (60, 60, 60), (90, 90, 90), (255, 255, 255), self.toggle_theme),
            Button(pygame.Rect(w // 2 + 50, 210, sett_w, sett_h), "Sound FX", font_small, (60, 60, 60), (90, 90, 90), (255, 255, 255), self.toggle_sound),
            Button(pygame.Rect(w // 2 + 50, 270, sett_w, sett_h), "Difficulty", font_small, (60, 60, 60), (90, 90, 90), (255, 255, 255), self.toggle_difficulty),
            Button(pygame.Rect(w // 2 + 50, 330, sett_w, sett_h), "Time Control", font_small, (60, 60, 60), (90, 90, 90), (255, 255, 255), self.toggle_time_control),
            Button(pygame.Rect(w // 2 + 50, 390, sett_w, sett_h), "Fullscreen", font_small, (60, 60, 60), (90, 90, 90), (255, 255, 255), self.toggle_fullscreen),
            Button(pygame.Rect(w // 2 + 50, 450, sett_w, sett_h), "Stockfish Path", font_small, (60, 60, 60), (90, 90, 90), (255, 255, 255), self.configure_stockfish_path),
            Button(pygame.Rect(w // 2 - 100, h - 100, 200, 45), "Back to Menu", font_medium, (62, 44, 36), (212, 163, 115), (240, 240, 240), lambda: self.set_state(self.STATE_MENU))
        ]

        # --- 3. Statistics Screen Buttons ---
        self.stats_buttons = [
            Button(pygame.Rect(w // 2 - 210, h - 100, 200, 45), "Reset Stats", font_medium, (120, 40, 40), (160, 50, 50), (255, 255, 255), self.reset_statistics),
            Button(pygame.Rect(w // 2 + 10, h - 100, 200, 45), "Back to Menu", font_medium, (62, 44, 36), (212, 163, 115), (240, 240, 240), lambda: self.set_state(self.STATE_MENU))
        ]

        # --- 4. Game Screen Action Buttons (right control panel) ---
        # Panel X starts at 760, width 380
        btn_w = 110
        btn_h = 35
        y_bottom_btns = 640
        
        self.game_buttons = [
            Button(pygame.Rect(760, y_bottom_btns, btn_w, btn_h), "Undo", font_small, (50, 50, 50), (80, 80, 80), (255, 255, 255), self.game.undo_move),
            Button(pygame.Rect(895, y_bottom_btns, btn_w, btn_h), "Redo", font_small, (50, 50, 50), (80, 80, 80), (255, 255, 255), self.game.redo_move),
            Button(pygame.Rect(1030, y_bottom_btns, btn_w, btn_h), "Flip Board", font_small, (50, 50, 50), (80, 80, 80), (255, 255, 255), self.flip_board),
            Button(pygame.Rect(760, y_bottom_btns + 45, btn_w, btn_h), "Pause Menu", font_small, (62, 44, 36), (212, 163, 115), (240, 240, 240), self.pause_game),
            Button(pygame.Rect(895, y_bottom_btns + 45, btn_w, btn_h), "Draw Offer", font_small, (50, 50, 50), (80, 80, 80), (255, 255, 255), self.game.offer_draw),
            Button(pygame.Rect(1030, y_bottom_btns + 45, btn_w, btn_h), "Resign", font_small, (120, 40, 40), (160, 50, 50), (255, 255, 255), lambda: self.game.resign_game(self.game.board.turn))
        ]

        # --- 5. Pause Menu Overlay Buttons ---
        pause_w = 220
        pause_h = 40
        pause_x = (w - pause_w) // 2
        pause_y = h // 2 - 100
        
        self.pause_buttons = [
            Button(pygame.Rect(pause_x, pause_y, pause_w, pause_h), "Resume Game", font_medium, (62, 44, 36), (212, 163, 115), (240, 240, 240), self.resume_game),
            Button(pygame.Rect(pause_x, pause_y + 55, pause_w, pause_h), "Save Game", font_medium, (50, 50, 50), (80, 80, 80), (255, 255, 255), self.trigger_save_dialog),
            Button(pygame.Rect(pause_x, pause_y + 110, pause_w, pause_h), "Load Game", font_medium, (50, 50, 50), (80, 80, 80), (255, 255, 255), self.trigger_load_dialog),
            Button(pygame.Rect(pause_x, pause_y + 165, pause_w, pause_h), "Export PGN", font_medium, (50, 50, 50), (80, 80, 80), (255, 255, 255), self.trigger_pgn_export),
            Button(pygame.Rect(pause_x, pause_y + 220, pause_w, pause_h), "Import PGN", font_medium, (50, 50, 50), (80, 80, 80), (255, 255, 255), self.trigger_pgn_import),
            Button(pygame.Rect(pause_x, pause_y + 275, pause_w, pause_h), "Exit to Menu", font_medium, (120, 40, 40), (160, 50, 50), (255, 255, 255), self.exit_to_main_menu)
        ]

    def set_state(self, new_state: str):
        """Switches screens and pauses/unpauses gameplay timers."""
        self.state = new_state
        if new_state == self.STATE_GAME:
            self.game.timer.start()
        else:
            self.game.timer.pause()
        self._build_ui_buttons()

    def start_new_match(self, mode: str):
        """Launches a new chess match under the selected game mode."""
        self.settings.game_mode = mode
        self.settings.save()
        self.is_paused = False
        self.promotion_modal = None
        self.game_over_modal = None
        self.game.reset_game()
        self.set_state(self.STATE_GAME)

    def flip_board(self):
        """Flips the chessboard orientation (White/Black on bottom)."""
        self.game.board_gui.flipped = not self.game.board_gui.flipped
        self.game.board_gui.sync_pieces(self.game.board, animated=False)

    def pause_game(self):
        self.is_paused = True
        self.game.timer.pause()

    def resume_game(self):
        self.is_paused = False
        if not self.game.game_over:
            self.game.timer.start()

    def exit_to_main_menu(self):
        self.is_paused = False
        self.set_state(self.STATE_MENU)

    def trigger_save_dialog(self):
        """Saves current match to an automated JSON save slot."""
        # Simple auto save file
        success = self.game.save_json("auto_save")
        if success:
            logging.info("Game saved to auto_save.json successfully.")
        self.resume_game()

    def trigger_load_dialog(self):
        """Loads match from the automated JSON save slot."""
        filepath = os.path.join(self.settings.SAVES_DIR, "auto_save.json")
        if os.path.exists(filepath):
            success = self.game.load_json(filepath)
            if success:
                logging.info("Loaded game successfully from auto_save.json")
                self.is_paused = False
                self.set_state(self.STATE_GAME)
        else:
            logging.warning("No auto_save.json file found to load.")
        self.resume_game()

    def trigger_pgn_export(self):
        """Saves current match in PGN format to saves folder."""
        filepath = os.path.join(self.settings.SAVES_DIR, "chess_game.pgn")
        self.game.export_pgn_file(filepath)
        self.resume_game()

    def trigger_pgn_import(self):
        """Imports game from chess_game.pgn if exists."""
        filepath = os.path.join(self.settings.SAVES_DIR, "chess_game.pgn")
        if os.path.exists(filepath):
            success = self.game.import_pgn_file(filepath)
            if success:
                self.is_paused = False
                self.set_state(self.STATE_GAME)
        else:
            logging.warning("No PGN file found to import.")
        self.resume_game()

    def toggle_theme(self):
        themes = list(self.settings.THEMES.keys())
        idx = themes.index(self.settings.theme)
        self.settings.theme = themes[(idx + 1) % len(themes)]
        self.settings.save()

    def toggle_sound(self):
        self.settings.sound_enabled = not self.settings.sound_enabled
        self.settings.save()

    def toggle_difficulty(self):
        diffs = [Settings.DIFFICULTY_EASY, Settings.DIFFICULTY_MEDIUM, Settings.DIFFICULTY_HARD, Settings.DIFFICULTY_EXPERT]
        idx = diffs.index(self.settings.difficulty)
        self.settings.difficulty = diffs[(idx + 1) % len(diffs)]
        self.settings.save()

    def toggle_time_control(self):
        presets = list(self.settings.TIME_PRESETS.keys())
        # Find current preset
        curr_tuple = (self.settings.time_limit, self.settings.time_increment)
        curr_preset = "Custom"
        for name, values in self.settings.TIME_PRESETS.items():
            if values == curr_tuple:
                curr_preset = name
                break
                
        if curr_preset in presets:
            idx = presets.index(curr_preset)
            next_preset = presets[(idx + 1) % len(presets)]
        else:
            next_preset = presets[0]
            
        limit, inc = self.settings.TIME_PRESETS[next_preset]
        self.settings.time_limit = limit
        self.settings.time_increment = inc
        self.settings.save()

    def toggle_fullscreen(self):
        self.settings.fullscreen = not self.settings.fullscreen
        self.settings.save()
        
        # Re-initialize screen
        self.screen_flags = pygame.RESIZABLE
        if self.settings.fullscreen:
            self.screen_flags |= pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((self.settings.width, self.settings.height), self.screen_flags)
        self._build_ui_buttons()

    def configure_stockfish_path(self):
        """Simplistic path toggler: toggles standard Windows paths for Stockfish or leaves blank."""
        paths = ["", "stockfish.exe", "C:\\Stockfish\\stockfish.exe"]
        try:
            idx = paths.index(self.settings.stockfish_path)
            self.settings.stockfish_path = paths[(idx + 1) % len(paths)]
        except ValueError:
            self.settings.stockfish_path = ""
        self.settings.save()
        self.game.ai.set_stockfish_path(self.settings.stockfish_path)

    def reset_statistics(self):
        self.db.clear_history()
        logging.info("Statistics wiped.")

    def quit_app(self):
        self.game.ai.close()
        self.running = False

    def handle_ai_callback(self, move: Optional[chess.Move], eval_score: float):
        """Background thread AI callback; safely enqueues the move for the main thread."""
        self.ai_move_queue.put((move, eval_score))

    def _process_ai_queue(self):
        """Dequeues calculated AI moves and executes them on the main thread."""
        try:
            while True:
                move, eval_score = self.ai_move_queue.get_nowait()
                if move and not self.game.game_over:
                    self.game.make_move(move)
                    self.eval_bar.set_evaluation(eval_score)
                self.ai_move_queue.task_done()
        except queue.Empty:
            pass

    def run(self):
        """Primary application loop."""
        while self.running:
            dt = self.clock.tick(60) / 1000.0  # 60 FPS cap
            
            # 1. Event Handling
            self._handle_events()
            
            # 2. Logic Updates
            self._update_logic(dt)
            
            # 3. Draw & Render
            self._draw_screen()
            
            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def _handle_events(self):
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.quit_app()
                return

            if event.type == pygame.VIDEORESIZE:
                self.settings.width, self.settings.height = event.size
                self.settings.save()
                self.screen = pygame.display.set_mode(event.size, self.screen_flags)
                self.game.board_gui.resize(event.size[0], event.size[1])
                self._build_ui_buttons()
                continue

            # Dispatch event based on state
            if self.state == self.STATE_MENU:
                for btn in self.menu_buttons:
                    btn.handle_event(event)

            elif self.state == self.STATE_SETTINGS:
                for btn in self.settings_buttons:
                    btn.handle_event(event)

            elif self.state == self.STATE_STATS:
                for btn in self.stats_buttons:
                    btn.handle_event(event)

            elif self.state == self.STATE_GAME:
                # 1. Handle Game-Over Modal Events (if game ended)
                if self.game.game_over and self.game_over_modal:
                    self.game_over_modal.handle_event(event)
                    continue

                # 2. Handle Pause Menu Overlay Events
                if self.is_paused:
                    for btn in self.pause_buttons:
                        btn.handle_event(event)
                    continue

                # 3. Handle Pawn Promotion Dialog Events
                if self.promotion_modal:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        piece_type = self.promotion_modal.handle_click(event.pos)
                        if piece_type:
                            # Finalize pawn promotion move
                            from_sq = self.game.board_gui.dragging_square
                            to_sq = self.game.board_gui.selected_square
                            move = chess.Move(from_sq, to_sq, promotion=piece_type)
                            self.game.make_move(move)
                            self.promotion_modal = None
                            self.game.board_gui.selected_square = None
                            self.game.board_gui.dragging_square = None
                    continue

                # 4. Handle Side Action Panel Events
                for btn in self.game_buttons:
                    btn.handle_event(event)
                self.move_panel.handle_event(event)

                # 5. Handle Chess Board Mouse Interactions
                self._handle_chessboard_interactions(event)

    def _handle_chessboard_interactions(self, event: pygame.event.Event):
        """Processes clicking, dragging, and dropping on the chess grid."""
        if self.game.game_over:
            return

        # Block human clicks if it is the AI's turn
        if self.game.opponent_type == "ai" and self.game.board.turn == self.game.ai_color:
            if self.settings.game_mode != Settings.MODE_TRAINING:
                return
                
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            sq = self.game.board_gui.coords_to_square(event.pos)
            if sq is not None:
                piece = self.game.board.piece_at(sq)
                
                # Case A: Clicking on a selected legal move target square
                if self.game.board_gui.selected_square is not None:
                    # Construct move
                    move = chess.Move(self.game.board_gui.selected_square, sq)
                    # Check for promotion
                    is_promotion = False
                    if self.game.board.piece_type_at(self.game.board_gui.selected_square) == chess.PAWN:
                        dest_rank = chess.square_rank(sq)
                        if (self.game.board.turn == chess.WHITE and dest_rank == 7) or \
                           (self.game.board.turn == chess.BLACK and dest_rank == 0):
                            is_promotion = move in self.game.board.generate_legal_moves(
                                from_mask=chess.SquareSet([self.game.board_gui.selected_square]),
                                to_mask=chess.SquareSet([sq])
                            ) or any(m.from_square == self.game.board_gui.selected_square and m.to_square == sq for m in self.game.board.legal_moves)
                            
                    if is_promotion:
                        # Open promotion modal
                        self.game.board_gui.dragging_square = self.game.board_gui.selected_square
                        self.game.board_gui.selected_square = sq
                        popup_w = 320
                        popup_h = 80
                        w, h = self.screen.get_size()
                        self.promotion_modal = PromotionModal(
                            pygame.Rect((w - popup_w) // 2, (h - popup_h) // 2, popup_w, popup_h),
                            self.assets, self.game.board.turn
                        )
                        return

                    if move in self.game.board.legal_moves:
                        self.game.make_move(move)
                        return
                    elif any(m.from_square == self.game.board_gui.selected_square and m.to_square == sq for m in self.game.board.legal_moves):
                        # Catch promotion move if promo piece omitted
                        promo_move = [m for m in self.game.board.legal_moves if m.from_square == self.game.board_gui.selected_square and m.to_square == sq][0]
                        self.game.make_move(promo_move)
                        return

                # Case B: Selecting own color piece for dragging/clicking
                if piece and piece.color == self.game.board.turn:
                    self.game.board_gui.selected_square = sq
                    self.game.board_gui.dragging_square = sq
                    self.game.board_gui.drag_pos = event.pos
                    # Offset calculation to drag piece centered
                    px, py = self.game.board_gui.square_to_coords(sq)
                    self.game.board_gui.drag_offset = (px - event.pos[0], py - event.pos[1])
                else:
                    self.game.board_gui.selected_square = None

        elif event.type == pygame.MOUSEMOTION:
            if self.game.board_gui.dragging_square is not None:
                self.game.board_gui.drag_pos = event.pos

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.game.board_gui.dragging_square is not None:
                sq = self.game.board_gui.coords_to_square(event.pos)
                from_sq = self.game.board_gui.dragging_square
                
                if sq is not None and sq != from_sq:
                    move = chess.Move(from_sq, sq)
                    # Check for promotion
                    is_promotion = False
                    if self.game.board.piece_type_at(from_sq) == chess.PAWN:
                        dest_rank = chess.square_rank(sq)
                        if (self.game.board.turn == chess.WHITE and dest_rank == 7) or \
                           (self.game.board.turn == chess.BLACK and dest_rank == 0):
                            is_promotion = any(m.from_square == from_sq and m.to_square == sq for m in self.game.board.legal_moves)
                            
                    if is_promotion:
                        # Open promotion modal
                        self.game.board_gui.selected_square = sq
                        popup_w = 320
                        popup_h = 80
                        w, h = self.screen.get_size()
                        self.promotion_modal = PromotionModal(
                            pygame.Rect((w - popup_w) // 2, (h - popup_h) // 2, popup_w, popup_h),
                            self.assets, self.game.board.turn
                        )
                        return

                    if move in self.game.board.legal_moves:
                        self.game.make_move(move)
                    elif any(m.from_square == from_sq and m.to_square == sq for m in self.game.board.legal_moves):
                        promo_move = [m for m in self.game.board.legal_moves if m.from_square == from_sq and m.to_square == sq][0]
                        self.game.make_move(promo_move)
                
                # Reset dragging state
                self.game.board_gui.dragging_square = None
                # Restore visual coordinates mapping
                self.game.board_gui.sync_pieces(self.game.board, animated=False)

    def _update_logic(self, dt: float):
        """Processes background actions: AI calculations, timer countdown ticks."""
        # 1. Process thread-safe AI moves
        self._process_ai_queue()
        
        # 2. Update piece slide animations
        self.game.board_gui.update()
        
        if self.state == self.STATE_GAME:
            if not self.is_paused and not self.game.game_over:
                # Tick clocks
                timeout = self.game.timer.update()
                if timeout:
                    self.game.handle_timeout(self.game.timer.active_color)
                    
                # Update widgets
                self.captured_widget.update_captured(self.game.board)
                self.move_panel.update_moves(self.game.move_log)
                
                # Trigger AI move calculation if turn matches AI
                if self.game.opponent_type == "ai" and not self.game.ai.is_thinking:
                    # In PVC, trigger if active color is the AI
                    # In CVC, trigger regardless of color
                    is_ai_turn = False
                    if self.settings.game_mode == Settings.MODE_CVC:
                        is_ai_turn = True
                    elif self.settings.game_mode == Settings.MODE_PVC:
                        is_ai_turn = (self.game.board.turn == self.game.ai_color)
                        
                    if is_ai_turn:
                        self.game.ai.get_best_move_async(
                            self.game.board, 
                            self.settings.difficulty, 
                            self.handle_ai_callback
                        )

            # Generate game over modal if game ended and modal not instantiated
            if self.game.game_over and not self.is_paused and self.game_over_modal is None:
                # Modal configuration
                w, h = self.screen.get_size()
                modal_w = 400
                modal_h = 220
                modal_rect = pygame.Rect((w - modal_w) // 2, (h - modal_h) // 2, modal_w, modal_h)
                
                title = f"{self.game.winner} Wins!" if self.game.winner != "Draw" else "Draw Match!"
                reason = f"by {self.game.termination_reason}"
                
                self.game_over_modal = GameOverModal(
                    modal_rect, self.assets, title, reason,
                    lambda: self.start_new_match(self.settings.game_mode),
                    lambda: self.set_state(self.STATE_MENU)
                )

    def _draw_screen(self):
        """Dispatches drawing calls depending on active screen state."""
        colors = self.settings.get_colors()
        self.screen.fill(colors["bg"])
        
        if self.state == self.STATE_MENU:
            self._draw_main_menu()
        elif self.state == self.STATE_SETTINGS:
            self._draw_settings_screen()
        elif self.state == self.STATE_STATS:
            self._draw_stats_screen()
        elif self.state == self.STATE_GAME:
            self._draw_game_screen()

    def _draw_main_menu(self):
        w, h = self.screen.get_size()
        
        # 1. Renders title header
        title_font = self.assets.get_font(64, bold=True)
        sub_font = self.assets.get_font(22)
        
        title_surf = title_font.render("CHESS SUPREME", True, (212, 163, 115))
        sub_surf = sub_font.render("A Premium Python Chess Experience", True, (160, 165, 170))
        
        self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, h // 2 - 250))
        self.screen.blit(sub_surf, (w // 2 - sub_surf.get_width() // 2, h // 2 - 180))
        
        # Draw buttons
        for btn in self.menu_buttons:
            btn.draw(self.screen)

    def _draw_settings_screen(self):
        w, h = self.screen.get_size()
        colors = self.settings.get_colors()
        
        # Title
        title_font = self.assets.get_font(36, bold=True)
        title_surf = title_font.render("Settings", True, colors["text"])
        self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, 60))
        
        # Labels and Current Value listings on the left
        label_font = self.assets.get_font(20, bold=True)
        val_font = self.assets.get_font(20)
        
        options = [
            ("Board Theme:", self.settings.theme.capitalize()),
            ("Sound Effects:", "Enabled" if self.settings.sound_enabled else "Disabled"),
            ("Difficulty:", self.settings.difficulty),
            ("Time Control:", f"{self.settings.time_limit // 60}m + {self.settings.time_increment}s" if self.settings.time_limit > 0 else "Infinite"),
            ("Fullscreen:", "On" if self.settings.fullscreen else "Off"),
            ("Stockfish Path:", "Configured" if self.settings.stockfish_path else "None (Fallback AI)")
        ]
        
        start_y = 155
        for i, (label, val) in enumerate(options):
            lbl_surf = label_font.render(label, True, colors["accent"])
            val_surf = val_font.render(val, True, colors["text"])
            
            # Align left relative to center line
            self.screen.blit(lbl_surf, (w // 2 - 280, start_y + (i * 60)))
            self.screen.blit(val_surf, (w // 2 - 70, start_y + (i * 60)))
            
        # Draw settings modification buttons
        for btn in self.settings_buttons:
            btn.draw(self.screen)

    def _draw_stats_screen(self):
        w, h = self.screen.get_size()
        colors = self.settings.get_colors()
        
        # Title
        title_font = self.assets.get_font(36, bold=True)
        title_surf = title_font.render("Player Statistics", True, colors["text"])
        self.screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, 60))
        
        # Retrieve SQLite Stats
        stats = self.db.get_statistics()
        
        # Layout metrics
        label_font = self.assets.get_font(20, bold=True)
        val_font = self.assets.get_font(20)
        
        rows = [
            ("Games Played:", str(stats["games_played"])),
            ("Wins:", str(stats["wins"])),
            ("Losses:", str(stats["losses"])),
            ("Draws:", str(stats["draws"])),
            ("Win Percentage:", f"{stats['win_percentage']}%"),
            ("Average Game Duration:", f"{stats['avg_duration'] // 60}m {stats['avg_duration'] % 60}s" if stats["avg_duration"] > 0 else "0s"),
            ("Best Winning Streak:", str(stats["best_streak"])),
            ("AI Opponent Victories:", str(stats["ai_victories"]))
        ]
        
        start_y = 150
        for i, (label, val) in enumerate(rows):
            # Draw double columns
            col = i % 2
            row = i // 2
            
            cx = w // 2 - 350 if col == 0 else w // 2 + 50
            cy = start_y + (row * 80)
            
            lbl_surf = label_font.render(label, True, colors["accent"])
            val_surf = val_font.render(val, True, colors["text"])
            
            self.screen.blit(lbl_surf, (cx, cy))
            self.screen.blit(val_surf, (cx, cy + 30))
            
        for btn in self.stats_buttons:
            btn.draw(self.screen)

    def _draw_game_screen(self):
        colors = self.settings.get_colors()
        
        # 1. Draw Board GUI and pieces
        last_mv = self.game.board.move_stack[-1] if self.game.board.move_stack else None
        self.game.board_gui.draw(self.screen, self.game.board, last_move=last_mv)
        
        # 2. Draw Evaluation Bar on the left
        if self.settings.eval_bar_enabled:
            self.eval_bar.draw(self.screen)

        # 3. Draw Side Control Panel items
        # Turn Indicator
        turn_font = self.assets.get_font(22, bold=True)
        active_turn_color = "White" if self.game.board.turn == chess.WHITE else "Black"
        indicator_text = f"{active_turn_color}'s Turn"
        
        turn_surf = turn_font.render(indicator_text, True, colors["text"])
        self.screen.blit(turn_surf, (760, 50))
        
        # Turn dot indicator
        dot_color = (245, 245, 245) if self.game.board.turn == chess.WHITE else (30, 30, 30)
        pygame.draw.circle(self.screen, dot_color, (760 + turn_surf.get_width() + 15, 62), 10)
        pygame.draw.circle(self.screen, colors["accent"], (760 + turn_surf.get_width() + 15, 62), 10, 2)
        
        # Draw Clocks (Digital Timers)
        time_font = self.assets.get_font(28, bold=True)
        w_time = self.game.timer.get_time_left(chess.WHITE)
        b_time = self.game.timer.get_time_left(chess.BLACK)
        
        w_time_str = self.game.timer.format_time(w_time)
        b_time_str = self.game.timer.format_time(b_time)
        
        # Red highlight if under 20s
        w_color = (231, 76, 60) if w_time < 20 and self.game.timer.time_limit > 0 else colors["text"]
        b_color = (231, 76, 60) if b_time < 20 and self.game.timer.time_limit > 0 else colors["text"]
        
        # Render timers side-by-side
        w_lbl = time_font.render(w_time_str, True, w_color)
        b_lbl = time_font.render(b_time_str, True, b_color)
        
        # Box containers for clock
        clock_w = 110
        clock_h = 42
        
        # White clock rect
        w_rect = pygame.Rect(960, 42, clock_w, clock_h)
        pygame.draw.rect(self.screen, colors["panel_bg"], w_rect, border_radius=5)
        # Highlight active clock border
        w_border = colors["selected"] if self.game.board.turn == chess.WHITE and not self.game.game_over else colors["accent"]
        pygame.draw.rect(self.screen, w_border, w_rect, width=2, border_radius=5)
        self.screen.blit(w_lbl, w_lbl.get_rect(center=w_rect.center))
        
        # Black clock rect
        b_rect = pygame.Rect(1080, 42, clock_w, clock_h)
        pygame.draw.rect(self.screen, colors["panel_bg"], b_rect, border_radius=5)
        b_border = colors["selected"] if self.game.board.turn == chess.BLACK and not self.game.game_over else colors["accent"]
        pygame.draw.rect(self.screen, b_border, b_rect, width=2, border_radius=5)
        self.screen.blit(b_lbl, b_lbl.get_rect(center=b_rect.center))

        # Renders Labels for clock
        lbl_font = self.assets.get_font(12, bold=True)
        w_txt = lbl_font.render("WHITE", True, colors["accent"])
        b_txt = lbl_font.render("BLACK", True, colors["accent"])
        self.screen.blit(w_txt, (w_rect.x, w_rect.y - 15))
        self.screen.blit(b_txt, (b_rect.x, b_rect.y - 15))
        
        # 4. Draw Captured Pieces Widget
        self.captured_widget.draw(self.screen, colors)
        
        # 5. Draw Move history panel list
        self.move_panel.draw(self.screen)
        
        # Draw side action panel buttons
        for btn in self.game_buttons:
            btn.draw(self.screen)

        # 6. Draw Pawn Promotion Modal (if active)
        if self.promotion_modal:
            self.promotion_modal.draw(self.screen)

        # 7. Draw Game Over Overlay (if game concluded)
        if self.game.game_over and self.game_over_modal:
            self.game_over_modal.draw(self.screen)

        # 8. Draw Pause Menu Modal (if active)
        if self.is_paused:
            # Translucent shadow background overlay
            pause_overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            pause_overlay.fill((0, 0, 0, 160))
            self.screen.blit(pause_overlay, (0, 0))
            
            # Modal container box
            w, h = self.screen.get_size()
            box_w, box_h = 300, 360
            box_rect = pygame.Rect((w - box_w) // 2, (h - box_h) // 2 - 50, box_w, box_h)
            pygame.draw.rect(self.screen, (34, 34, 34), box_rect, border_radius=10)
            pygame.draw.rect(self.screen, colors["accent"], box_rect, width=2, border_radius=10)
            
            # Title
            p_font = self.assets.get_font(28, bold=True)
            p_txt = p_font.render("Game Paused", True, (255, 255, 255))
            self.screen.blit(p_txt, p_txt.get_rect(centerx=box_rect.centerx, y=box_rect.y + 20))
            
            for btn in self.pause_buttons:
                btn.draw(self.screen)

if __name__ == "__main__":
    app = ChessApp()
    app.run()
