import random
import string


DIRS_EASY   = [(0, 1), (1, 0)]
DIRS_MEDIUM = [(0, 1), (1, 0), (0, -1), (-1, 0)]
DIRS_HARD   = [(0,1),(1,0),(1,1),(-1,1),(0,-1),(-1,0),(-1,-1),(1,-1)]


def generate_word_search(words, size=12, difficulty="Medium"):
    """
    Place words in a grid, fill blanks with random letters.
    Returns (grid, placed, failed, positions).
    positions = list of (word, row, col, dr, dc) — used for answer-page highlights.
    """
    cleaned = [w.upper().replace(" ", "").replace("-", "") for w in words if w.strip()]
    cleaned = [w for w in cleaned if 2 <= len(w) <= size]

    dirs = {"Easy": DIRS_EASY, "Medium": DIRS_MEDIUM, "Hard": DIRS_HARD}.get(difficulty, DIRS_MEDIUM)

    best = None

    for _attempt in range(6):
        grid      = [[""] * size for _ in range(size)]
        placed, failed, positions = [], [], []

        for word in sorted(cleaned, key=len, reverse=True):
            result = _try_place(grid, word, dirs, size)
            if result is not None:
                r, c, dr, dc = result
                placed.append(word)
                positions.append((word, r, c, dr, dc))
            else:
                failed.append(word)

        if best is None or len(placed) > len(best[1]):
            best = ([row[:] for row in grid], placed[:], failed[:], positions[:])

        if not failed:
            break

    grid, placed, failed, positions = best

    for r in range(size):
        for c in range(size):
            if grid[r][c] == "":
                grid[r][c] = random.choice(string.ascii_uppercase)

    return grid, placed, failed, positions


def _try_place(grid, word, dirs, size):
    positions = [(r, c) for r in range(size) for c in range(size)]
    random.shuffle(positions)
    shuffled_dirs = dirs[:]
    random.shuffle(shuffled_dirs)

    for row, col in positions:
        for dr, dc in shuffled_dirs:
            end_r = row + dr * (len(word) - 1)
            end_c = col + dc * (len(word) - 1)
            if not (0 <= end_r < size and 0 <= end_c < size):
                continue
            if _can_place(grid, word, row, col, dr, dc):
                for i, letter in enumerate(word):
                    grid[row + dr * i][col + dc * i] = letter
                return row, col, dr, dc
    return None


def _can_place(grid, word, row, col, dr, dc):
    for i, letter in enumerate(word):
        cell = grid[row + dr * i][col + dc * i]
        if cell != "" and cell != letter:
            return False
    return True
