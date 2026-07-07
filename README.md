# Chess Supreme 👑

A professional, production-quality desktop Chess Game written in Python 3.12+ using Pygame and python-chess.

This project delivers a feature-rich, high-performance, and visually stunning chess game that implements all official FIDE rules, persists player metrics to an SQLite database, integrates Stockfish UCI engines (with built-in Minimax fallback), and features smooth move animations, custom UI controls, and procedural audio synthesis.

---

## Features

### 🎮 Gameplay Modes
*   **Player vs Player (Local):** Share a screen and challenge a friend with digital clocks.
*   **Player vs Computer (AI):** Train against Stockfish or our custom Minimax AI engine with adjustable difficulties.
*   **Computer vs Computer:** Sit back and observe two AI engines play against each other in real-time.
*   **Training Mode:** Play with interactive tools such as position evaluations, move suggestion hints, and infinite undos/redos.

### ⚙️ AI Engine Options
*   **UCI Stockfish Integration:** Enter the path to your local Stockfish executable in Settings to run the industry-standard engine in a background thread.
*   **Fallback Minimax AI:** Works 100% out of the box with zero setup. Built on a multithreaded Minimax search algorithm featuring alpha-beta pruning, move ordering heuristics, and Piece-Square Tables (PST).
*   **Difficulty Settings:**
    *   *Easy:* Low search depth and minor randomized variance.
    *   *Medium:* Balanced tactical search.
    *   *Hard:* Higher tactical depth (10+ ply or depth 3 minimax).
    *   *Expert:* Full computational strength (15+ ply or depth 4 minimax).

### 🎨 Visuals & Themes
*   **Modern Aesthetics:** Rounded corners, sleek button highlights, responsive screen sizing, and dark-panel overlays.
*   **Board Themes:**
    *   *Wood (Default):* Classic cream & brown squares.
    *   *Glass:* Neon-cyan overlays and sleek metallic dark squares.
    *   *Modern Flat:* High-contrast flat-design blue/green theme.
    *   *Classic:* Ultra-minimalist dark gray & white theme.
*   **Smooth Animations:** Renders sliding piece animations between cells using linear interpolation (`lerp`) with a `smoothstep` envelope.
*   **Move & Status Overlays:** Displays check warnings, captured pieces, numerical material advantages, checkmate modal outcomes, and legal move dots (with hollow circles for capturable cells).

### 📀 Persistence & Files
*   **SQLite Database:** Keeps logs of all games played, wins, losses, draws, streaks, AI victories, and average game durations.
*   **JSON Saves:** Save your progress and reload games in progress later.
*   **PGN Import/Export:** Import and analyze third-party games or export your games as standard `.pgn` files.
*   **FEN Support:** Full integration of Board states represented as FEN strings.

---

## Project Structure

```
chess_game/
│
├── assets/
│   ├── images/         # Cached 128x128px "Cburnett" style chess piece PNGs
│   ├── sounds/         # Move, check, capture, and game-over WAV files
│   └── fonts/          # Typography assets
│
├── src/
│   ├── settings.py     # Configuration options, theme definitions, and JSON loading
│   ├── database.py     # SQLite schema management and statistical aggregations
│   ├── timer.py        # White/Black player chess timers (Fischer delays, intervals)
│   ├── utils.py        # Path resolution, asset downloaders, and WAV synthesizers
│   ├── piece.py        # Interpolated piece coordinates and visual animations
│   ├── board.py        # Square grid coordinate mapping and legal highlights
│   ├── ai.py           # Stockfish wrapper and fallback Alpha-Beta Minimax algorithm
│   ├── ui.py           # Modular UI widgets (Buttons, History Panels, Evaluation Bars)
│   ├── game.py         # Main engine rules controller, PGN loader, and state loggers
│   └── main.py         # App entry, Pygame frame loops, and event handlers
│
├── database/           # Persistent SQLite database storage path
├── saves/              # JSON game saves and PGN exports path
├── tests/
│   └── test_game.py    # Unittest suite validating timers, AI, and DB queries
├── requirements.txt    # Package dependencies
└── README.md           # Getting started manual
```

---

## Installation & Setup

### Prerequisites
Make sure you have **Python 3.12+** installed on your system.

### 1. Install Dependencies
Navigate to the root directory and install requirements:
```bash
pip install -r requirements.txt
```
*Note: This project uses `pygame-ce` (Pygame Community Edition) for premium performance and native support on newer Python runtimes.*

### 2. Launch the Game
Run the main script to start:
```bash
python src/main.py
```
*Upon launching, the game will automatically connect to Wikimedia Commons to download the high-quality piece images and procedurally synthesize all needed game sound effects. An internet connection is only needed on the very first run.*

### 3. Run Unit Tests (Optional)
To verify the engine rules and database integrity:
```bash
python -m unittest tests/test_game.py
```

---

## How to Play & Controls

### Board Interactions
*   **Drag-and-Drop:** Left-click a piece and hold down the mouse to drag it to a valid highlighted square, then release to execute the move.
*   **Click-to-Move:** Left-click a piece to select it, then left-click any of the highlighted legal squares to move it.
*   **Pawn Promotion:** Moving a pawn to the eighth rank triggers a modal pop-up overlay. Click on the Queen, Rook, Bishop, or Knight icon to complete the promotion.

### Control Panel Buttons
*   **Undo / Redo:** Backtrack or fast-forward through past moves. In *Player vs AI* mode, Undo automatically rolls back two steps to restore play to the human player's turn.
*   **Flip Board:** Rotate the grid 180 degrees (swapping perspective between White and Black).
*   **Pause Menu:** Brings up the pause menu where you can:
    *   *Save Game / Load Game:* Saves state to an auto-save JSON slot.
    *   *Export PGN / Import PGN:* Saves or loads standard PGN files.
*   **Draw Offer / Resign:** Claims a draw by consensus or resigns immediately.

---

## SQLite Database Metrics
The statistics page queries raw match records stored in `database/chess_stats.db` to calculate:
*   **Win/Loss/Draw Ratio:** Percentage of total games won.
*   **AI Victories:** Number of matches won against an AI opponent.
*   **Winning Streak:** Highest consecutive victories achieved by the user.
*   **Average Duration:** Troughs and peaks of match lengths.
