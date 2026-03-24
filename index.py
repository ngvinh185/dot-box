import pygame
import random
import math
import os
import json
from PIL import Image, ImageSequence
from gamelogic import GameState

# =========================
# CONFIG
# =========================
FPS = 60

PLAYER = 0
AI = 1
PLAYER2 = 2

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820

# ===== THEME SÁNG HƠN + DỊU HƠN =====
THEME = {
    "bg": (238, 244, 255),
    "grid": (214, 224, 244),
    "panel": (248, 251, 255),
    "panel2": (226, 236, 255),
    "text": (38, 48, 74),
    "subtext": (100, 114, 145),
    "player": (255, 120, 170),
    "ai": (95, 180, 255),
    "p2": (120, 200, 150),
    "accent": (125, 145, 255),
    "accent2": (255, 182, 220),
    "success": (88, 198, 145),
    "danger": (255, 112, 130),
    "shadow": (180, 194, 224),
    "board_line": (176, 194, 230),
    "overlay": (90, 110, 160),
    "input_bg": (255, 255, 255),
    "input_border": (180, 194, 224),
    "input_active": (125, 145, 255),
}

MAX_RIPPLES = 6
MAX_PARTICLES = 24
HIGHSCORE_FILE = "highscores.json"

# =========================
# HELPERS
# =========================
def clamp(v, a, b):
    return max(a, min(b, v))

def lerp(a, b, t):
    return a + (b - a) * t

def ease_out_quad(t):
    return 1 - (1 - t) * (1 - t)

def center_rect_in(parent_rect, w, h, offset_y=0):
    x = parent_rect.centerx - w // 2
    y = parent_rect.centery - h // 2 + offset_y
    return pygame.Rect(x, y, w, h)

def stack_center_rects(parent_rect, sizes, gap=18, offset_y=0):
    total_h = sum(h for _, h in sizes) + gap * (len(sizes) - 1 if len(sizes) > 1 else 0)
    start_y = parent_rect.centery - total_h // 2 + offset_y
    rects = []
    y = start_y
    for w, h in sizes:
        x = parent_rect.centerx - w // 2
        rects.append(pygame.Rect(x, y, w, h))
        y += h + gap
    return rects

# =========================
# TEXT CACHE
# =========================
_text_cache: dict = {}

def get_text_surface(font, text, color):
    key = (id(font), text, color)
    if key not in _text_cache:
        _text_cache[key] = font.render(text, True, color)
    return _text_cache[key]

def draw_text_center(surface, text, font, color, center, glow=False, glow_color=None):
    cx, cy = int(center[0]), int(center[1])
    if glow:
        gc = glow_color if glow_color else color
        glow_img = get_text_surface(font, text, gc)
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            rect = glow_img.get_rect(center=(cx + dx, cy + dy))
            surface.blit(glow_img, rect)
    img = get_text_surface(font, text, color)
    rect = img.get_rect(center=(cx, cy))
    surface.blit(img, rect)

def draw_text_left(surface, text, font, color, pos):
    img = get_text_surface(font, text, color)
    rect = img.get_rect(topleft=(int(pos[0]), int(pos[1])))
    surface.blit(img, rect)

def draw_round_rect(surface, rect, color, radius=20):
    pygame.draw.rect(surface, color, rect, border_radius=radius)

def draw_round_rect_outline(surface, rect, color, width=2, radius=20):
    pygame.draw.rect(surface, color, rect, width=width, border_radius=radius)

# =========================
# BUTTON
# =========================
class Button:
    def __init__(self, rect, text, action=None, base_color=None, hover_color=None, text_color=None, font=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.action = action
        self.base_color = base_color or THEME["panel2"]
        self.hover_color = hover_color or THEME["accent"]
        self.text_color = text_color or THEME["text"]
        self.font = font
        self.hovered = False
        self.scale_t = 0.0

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)
        target = 1.0 if self.hovered else 0.0
        self.scale_t = lerp(self.scale_t, target, 0.18)

    def draw(self, surface):
        inflate = int(6 * self.scale_t)
        r = self.rect.inflate(inflate, inflate)

        shadow = r.copy()
        shadow.y += 5
        pygame.draw.rect(surface, THEME["shadow"], shadow, border_radius=24)

        c = (
            int(lerp(self.base_color[0], self.hover_color[0], self.scale_t)),
            int(lerp(self.base_color[1], self.hover_color[1], self.scale_t)),
            int(lerp(self.base_color[2], self.hover_color[2], self.scale_t)),
        )

        draw_round_rect(surface, r, c, 24)
        draw_round_rect_outline(surface, r, (255, 255, 255), 2, 24)

        if self.font:
            draw_text_center(
                surface, self.text, self.font, self.text_color, r.center,
                glow=self.hovered, glow_color=THEME["accent2"]
            )

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.hovered:
            if self.action:
                self.action()
            return True
        return False

# =========================
# TEXT INPUT
# =========================
class TextInput:
    def __init__(self, rect, text="", placeholder="", font=None, max_len=14):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.placeholder = placeholder
        self.font = font
        self.max_len = max_len
        self.active = False
        self.cursor_timer = 0
        self.show_cursor = True

    def update(self, dt):
        self.cursor_timer += dt
        if self.cursor_timer >= 500:
            self.cursor_timer = 0
            self.show_cursor = not self.show_cursor

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)

        if self.active and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                return "submit"
            else:
                if len(self.text) < self.max_len:
                    ch = event.unicode
                    if ch.isprintable() and ch not in "\r\n\t":
                        self.text += ch
        return None

    def draw(self, surface):
        border = THEME["input_active"] if self.active else THEME["input_border"]
        draw_round_rect(surface, self.rect, THEME["input_bg"], 18)
        draw_round_rect_outline(surface, self.rect, border, 3 if self.active else 2, 18)

        display = self.text if self.text else self.placeholder
        color = THEME["text"] if self.text else THEME["subtext"]

        txt = get_text_surface(self.font, display, color)
        text_x = self.rect.x + 16
        text_y = self.rect.centery - txt.get_height() // 2
        surface.blit(txt, (text_x, text_y))

        if self.active and self.show_cursor:
            cursor_x = text_x + txt.get_width() + (0 if self.text else 0)
            cursor_y1 = self.rect.y + 12
            cursor_y2 = self.rect.bottom - 12
            pygame.draw.line(surface, THEME["accent"], (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)

# =========================
# UI
# =========================
class GameUI:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("DOTS & BOXES")

        self.width = WINDOW_WIDTH
        self.height = WINDOW_HEIGHT
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_title = pygame.font.SysFont("arial", max(42, self.width // 24), bold=True)
        self.font_big = pygame.font.SysFont("arial", max(30, self.width // 40), bold=True)
        self.font_mid = pygame.font.SysFont("arial", max(22, self.width // 60), bold=True)
        self.font_small = pygame.font.SysFont("arial", max(18, self.width // 80))
        self.font_tiny = pygame.font.SysFont("arial", max(16, self.width // 90))

        # State
        self.state = "LOADING"
        self.prev_state = None
        self.running = True
        self.buttons = []

        # Game
        self.game = None
        self.mode = None
        self.difficulty = "hard"
        self.game_over = False
        self.ai_thinking = False
        self.current_turn = PLAYER

        # NEW: game mode
        self.play_mode = "AI"  # "AI" or "PVP"

        # Player names
        self.player1_name = "PLAYER 1"
        self.player2_name = "PLAYER 2"

        # Input
        self.name_input_1 = None
        self.name_input_2 = None

        # CHỐNG CLICK BẨN / double click / click lúc AI turn
        self.input_locked = False

        # Board layout
        self.board_origin = (0, 0)
        self.cell = 110
        self.board_w = 0
        self.board_h = 0
        self.board_center_x = self.width // 2
        self.board_center_y = self.height // 2

        # Edge / box ownership
        self.h_owner = []
        self.v_owner = []
        self.box_owner = []

        # Effects
        self.click_ripples = []
        self.click_particles = []
        self.animating_edges = []
        self.animating_boxes = []

        # Cache
        self.bg_surface = None
        self.board_static_surface = None
        self.board_static_rect = None
        self.board_static_dirty = True

        self.board_dynamic_surface = None
        self.board_dynamic_dirty = True

        # Small reusable particle sprite
        self.particle_surface = pygame.Surface((8, 8), pygame.SRCALPHA)
        pygame.draw.circle(self.particle_surface, (255, 200, 240, 220), (4, 4), 3)

        # Loading
        self.loading_frames = []
        self.loading_frame_index = 0
        self.loading_frame_timer = 0
        self.loading_elapsed = 0
        self.loading_duration = 1200

        # Frame rects
        self.frame_loading = None
        self.frame_menu = None
        self.frame_diff = None
        self.frame_size = None
        self.frame_game = None
        self.frame_gameover = None
        self.frame_names = None

        # In-game back button
        self.back_button_game = None

        # High score
        self.highscores = self.load_highscores()

        self.build_bg_surface()
        self.build_frames()

        self.loading_gif = self.load_gif(
            "1.gif",
            max_size=(min(self.width * 0.35, 380), min(self.height * 0.35, 320))
        )
        if self.loading_gif:
            self.loading_frames = self.loading_gif

        self.change_state("LOADING")

    # =========================
    # HIGHSCORE
    # =========================
    def load_highscores(self):
        if not os.path.exists(HIGHSCORE_FILE):
            return {}
        try:
            with open(HIGHSCORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
        except Exception:
            return {}

    def save_highscores(self):
        try:
            with open(HIGHSCORE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.highscores, f, indent=2)
        except Exception:
            pass

    def get_score_key(self, mode=None, difficulty=None):
        if self.play_mode != "AI":
            return None
        if mode is None:
            mode = self.mode
        if difficulty is None:
            difficulty = self.difficulty
        if not mode:
            return None
        rows, cols = mode
        return f"{rows}x{cols}_{difficulty}"

    def get_highscore(self, mode=None, difficulty=None):
        key = self.get_score_key(mode, difficulty)
        if key is None:
            return 0
        return int(self.highscores.get(key, 0))

    def update_highscore(self):
        if self.play_mode != "AI":
            return
        if not self.mode or not self.game:
            return
        key = self.get_score_key()
        cur = self.game.score['player']
        old = self.highscores.get(key, 0)
        if cur > old:
            self.highscores[key] = cur
            self.save_highscores()

    # =========================
    # FRAME LAYOUTS
    # =========================
    def build_frames(self):
        W, H = self.width, self.height
        pad_x = 80
        pad_y = 80

        self.frame_loading = pygame.Rect(
            W // 2 - min(660, W - pad_x) // 2,
            H // 2 - min(480, H - pad_y) // 2,
            min(660, W - pad_x),
            min(480, H - pad_y)
        )

        self.frame_menu = pygame.Rect(
            W // 2 - min(760, W - pad_x) // 2,
            H // 2 - min(620, H - pad_y) // 2,
            min(760, W - pad_x),
            min(620, H - pad_y)
        )

        self.frame_diff = pygame.Rect(
            W // 2 - min(740, W - pad_x) // 2,
            H // 2 - min(620, H - pad_y) // 2,
            min(740, W - pad_x),
            min(620, H - pad_y)
        )

        self.frame_size = pygame.Rect(
            W // 2 - min(740, W - pad_x) // 2,
            H // 2 - min(680, H - pad_y) // 2,
            min(740, W - pad_x),
            min(680, H - pad_y)
        )

        self.frame_names = pygame.Rect(
            W // 2 - min(760, W - pad_x) // 2,
            H // 2 - min(640, H - pad_y) // 2,
            min(760, W - pad_x),
            min(640, H - pad_y)
        )

        game_w = min(1080, W - 120)
        game_h = min(620, H - 180)
        self.frame_game = pygame.Rect(
            W // 2 - game_w // 2,
            H // 2 - game_h // 2 + 45,
            game_w,
            game_h
        )

        self.frame_gameover = pygame.Rect(
            W // 2 - min(700, W - 120) // 2,
            H // 2 - min(470, H - 140) // 2,
            min(700, W - 120),
            min(470, H - 140)
        )

    # =========================
    # CACHE BUILDERS
    # =========================
    def build_bg_surface(self):
        self.bg_surface = pygame.Surface((self.width, self.height))
        self.bg_surface.fill(THEME["bg"])
        step = 60
        for x in range(0, self.width, step):
            pygame.draw.line(self.bg_surface, THEME["grid"], (x, 0), (x, self.height), 1)
        for y in range(0, self.height, step):
            pygame.draw.line(self.bg_surface, THEME["grid"], (0, y), (self.width, y), 1)

    def build_board_static_surface(self):
        if not self.mode:
            return
        rows, cols = self.mode
        ox, oy = self.board_origin
        bw = self.board_w
        bh = self.board_h

        panel = pygame.Rect(ox - 28, oy - 28, bw + 56, bh + 56)
        self.board_static_rect = panel.copy()
        surf = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)

        draw_round_rect(surf, pygame.Rect(0, 0, panel.w, panel.h), THEME["panel"], 28)
        draw_round_rect_outline(surf, pygame.Rect(0, 0, panel.w, panel.h), (255, 255, 255), 2, 28)

        for r in range(rows + 1):
            for c in range(cols):
                p1 = self.get_dot_pos(r, c)
                p2 = self.get_dot_pos(r, c + 1)
                pygame.draw.line(
                    surf, THEME["board_line"],
                    (p1[0] - panel.x, p1[1] - panel.y),
                    (p2[0] - panel.x, p2[1] - panel.y), 3
                )

        for r in range(rows):
            for c in range(cols + 1):
                p1 = self.get_dot_pos(r, c)
                p2 = self.get_dot_pos(r + 1, c)
                pygame.draw.line(
                    surf, THEME["board_line"],
                    (p1[0] - panel.x, p1[1] - panel.y),
                    (p2[0] - panel.x, p2[1] - panel.y), 3
                )

        for r in range(rows + 1):
            for c in range(cols + 1):
                x, y = self.get_dot_pos(r, c)
                lx = x - panel.x
                ly = y - panel.y
                pygame.draw.circle(surf, (255, 255, 255), (lx, ly), 8)
                pygame.draw.circle(surf, THEME["accent2"], (lx, ly), 6)

        self.board_static_surface = surf
        self.board_static_dirty = False

    def build_board_dynamic_surface(self):
        if not self.mode:
            return
        rows, cols = self.mode
        panel = self.board_static_rect

        surf = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)

        for r in range(rows):
            for c in range(cols):
                owner = self.box_owner[r][c]
                if owner != -1:
                    x, y = self.get_dot_pos(r, c)
                    rect = pygame.Rect(x - panel.x + 9, y - panel.y + 9, self.cell - 18, self.cell - 18)

                    if owner == PLAYER:
                        color = THEME["player"]
                    elif owner == AI:
                        color = THEME["ai"]
                    else:
                        color = THEME["p2"]

                    pygame.draw.rect(surf, color, rect, border_radius=16)

        for r in range(rows + 1):
            for c in range(cols):
                owner = self.h_owner[r][c]
                if owner != -1:
                    p1 = self.get_dot_pos(r, c)
                    p2 = self.get_dot_pos(r, c + 1)

                    if owner == PLAYER:
                        color = THEME["player"]
                    elif owner == AI:
                        color = THEME["ai"]
                    else:
                        color = THEME["p2"]

                    pygame.draw.line(
                        surf, color,
                        (p1[0] - panel.x, p1[1] - panel.y),
                        (p2[0] - panel.x, p2[1] - panel.y), 7
                    )

        for r in range(rows):
            for c in range(cols + 1):
                owner = self.v_owner[r][c]
                if owner != -1:
                    p1 = self.get_dot_pos(r, c)
                    p2 = self.get_dot_pos(r + 1, c)

                    if owner == PLAYER:
                        color = THEME["player"]
                    elif owner == AI:
                        color = THEME["ai"]
                    else:
                        color = THEME["p2"]

                    pygame.draw.line(
                        surf, color,
                        (p1[0] - panel.x, p1[1] - panel.y),
                        (p2[0] - panel.x, p2[1] - panel.y), 7
                    )

        self.board_dynamic_surface = surf
        self.board_dynamic_dirty = False

    # =========================
    # GIF LOADER
    # =========================
    def load_gif(self, path, max_size=(420, 420)):
        if not os.path.exists(path):
            return []
        frames = []
        try:
            gif = Image.open(path)
            for frame in ImageSequence.Iterator(gif):
                fr = frame.convert("RGBA")
                w, h = fr.size
                scale = min(max_size[0] / w, max_size[1] / h)
                nw = max(1, int(w * scale))
                nh = max(1, int(h * scale))
                fr = fr.resize((nw, nh), Image.LANCZOS)
                py_img = pygame.image.fromstring(fr.tobytes(), fr.size, fr.mode).convert_alpha()
                frames.append(py_img)
        except Exception:
            return []
        return frames

    # =========================
    # STATE
    # =========================
    def change_state(self, new_state):
        if self.state != "LOADING":
            self.prev_state = self.state

        self.state = new_state
        self.buttons.clear()
        self.back_button_game = None

        if new_state == "LOADING":
            return

        if new_state == "MENU":
            bw = min(360, self.frame_menu.w // 2)
            bh = 66
            gap = 22
            rects = stack_center_rects(self.frame_menu, [(bw, bh), (bw, bh), (bw, bh)], gap=gap, offset_y=100)
            self.buttons = [
                Button(rects[0], "PLAYER VS AI", self.goto_difficulty, font=self.font_mid),
                Button(rects[1], "PLAYER VS PLAYER", self.goto_names, font=self.font_mid),
                Button(rects[2], "EXIT", self.exit_game,
                       base_color=(255, 226, 232), hover_color=THEME["danger"], font=self.font_mid),
            ]

        elif new_state == "DIFFICULTY":
            bw = min(350, self.frame_diff.w // 2)
            bh = 62
            gap = 22
            rects = stack_center_rects(
                self.frame_diff,
                [(bw, bh), (bw, bh), (bw, bh), (160, 52)],
                gap=gap, offset_y=78
            )
            self.buttons = [
                Button(rects[0], "EASY", lambda: self.set_difficulty_and_goto_size("easy"), font=self.font_mid),
                Button(rects[1], "MEDIUM", lambda: self.set_difficulty_and_goto_size("medium"), font=self.font_mid),
                Button(rects[2], "HARD", lambda: self.set_difficulty_and_goto_size("hard"), font=self.font_mid),
                Button(rects[3], "BACK", self.go_back, font=self.font_small),
            ]

        elif new_state == "NAMES":
            self.play_mode = "PVP"

            input_w = 360
            input_h = 58
            cx = self.frame_names.centerx

            self.name_input_1 = TextInput(
                pygame.Rect(cx - input_w // 2, self.frame_names.y + 220, input_w, input_h),
                text=self.player1_name if self.player1_name != "PLAYER 1" else "",
                placeholder="Enter Player 1 name",
                font=self.font_small,
                max_len=14
            )
            self.name_input_2 = TextInput(
                pygame.Rect(cx - input_w // 2, self.frame_names.y + 320, input_w, input_h),
                text=self.player2_name if self.player2_name != "PLAYER 2" else "",
                placeholder="Enter Player 2 name",
                font=self.font_small,
                max_len=14
            )

            self.buttons = [
                Button(pygame.Rect(cx - 175, self.frame_names.bottom - 130, 350, 58),
                       "CONTINUE", self.goto_size_from_names, font=self.font_mid),
                Button(pygame.Rect(cx - 80, self.frame_names.bottom - 58, 160, 48),
                       "BACK", self.go_back, font=self.font_small),
            ]

        elif new_state == "SIZE":
            bw = min(350, self.frame_size.w // 2)
            bh = 60
            gap = 22
            rects = stack_center_rects(
                self.frame_size,
                [(bw, bh), (bw, bh), (bw, bh), (160, 52)],
                gap=gap, offset_y=86
            )
            self.buttons = [
                Button(rects[0], "3 x 4", lambda: self.start_game((3, 4)), font=self.font_mid),
                Button(rects[1], "4 x 5", lambda: self.start_game((4, 5)), font=self.font_mid),
                Button(rects[2], "5 x 6", lambda: self.start_game((5, 6)), font=self.font_mid),
                Button(rects[3], "BACK", self.go_back, font=self.font_small),
            ]

        elif new_state == "GAME":
            self.back_button_game = Button(
                pygame.Rect(self.width - 160, self.frame_game.bottom + 22, 125, 42),
                "BACK",
                self.go_back_from_game,
                font=self.font_small
            )

        elif new_state == "GAMEOVER":
            bw = min(310, self.frame_gameover.w // 2)
            bh = 60
            gap = 18
            rects = stack_center_rects(
                self.frame_gameover, [(bw, bh), (bw, bh), (160, 50)], gap=gap, offset_y=102
            )
            self.buttons = [
                Button(rects[0], "PLAY AGAIN", lambda: self.start_game(self.mode), font=self.font_mid),
                Button(rects[1], "MENU", self.goto_menu, font=self.font_mid),
                Button(rects[2], "BACK", self.go_back, font=self.font_small),
            ]

    def goto_menu(self):
        self.change_state("MENU")

    def goto_difficulty(self):
        self.play_mode = "AI"
        self.change_state("DIFFICULTY")

    def goto_names(self):
        self.change_state("NAMES")

    def goto_size(self):
        self.change_state("SIZE")

    def goto_size_from_names(self):
        n1 = self.name_input_1.text.strip() if self.name_input_1 else ""
        n2 = self.name_input_2.text.strip() if self.name_input_2 else ""

        self.player1_name = n1 if n1 else "PLAYER 1"
        self.player2_name = n2 if n2 else "PLAYER 2"

        self.change_state("SIZE")

    def set_difficulty_and_goto_size(self, diff):
        self.difficulty = diff
        self.change_state("SIZE")

    def go_back(self):
        if self.state == "GAMEOVER":
            self.state = "GAME"
            self.game_over = False
            self.ai_thinking = False
            self.input_locked = False
            self.change_state("GAME")
            return

        if self.state == "SIZE":
            if self.play_mode == "PVP":
                self.change_state("NAMES")
            else:
                self.change_state("DIFFICULTY")
            return

        if self.state == "NAMES":
            self.change_state("MENU")
            return

        if self.state == "DIFFICULTY":
            self.change_state("MENU")
            return

        if self.prev_state:
            self.change_state(self.prev_state)

    def go_back_from_game(self):
        self.game = None
        self.game_over = False
        self.ai_thinking = False
        self.input_locked = False

        if self.play_mode == "PVP":
            self.change_state("NAMES")
        else:
            self.change_state("SIZE")

    def exit_game(self):
        self.running = False

    # =========================
    # GAME START
    # =========================
    def start_game(self, mode):
        self.mode = mode
        rows, cols = mode
        self.game = GameState(rows, cols, self.difficulty)

        # reset score cho chắc
        self.game.score['player'] = 0
        self.game.score['AI'] = 0

        self.game_over = False
        self.ai_thinking = False
        self.current_turn = PLAYER
        self.input_locked = False

        self.animating_edges.clear()
        self.animating_boxes.clear()
        self.click_ripples.clear()
        self.click_particles.clear()

        self.h_owner = [[-1] * cols for _ in range(rows + 1)]
        self.v_owner = [[-1] * (cols + 1) for _ in range(rows)]
        self.box_owner = [[-1] * cols for _ in range(rows)]

        self.compute_board_layout()
        self.board_static_dirty = True
        self.board_dynamic_dirty = True
        self.board_dynamic_surface = None

        self.change_state("GAME")

    def compute_board_layout(self):
        rows, cols = self.mode

        content_margin_x = 60
        content_margin_y = 50

        usable = pygame.Rect(
            self.frame_game.x + content_margin_x,
            self.frame_game.y + content_margin_y,
            self.frame_game.w - content_margin_x * 2,
            self.frame_game.h - content_margin_y * 2
        )

        scale = 0.84

        max_cell_w = (usable.w * scale) / cols
        max_cell_h = (usable.h * scale) / rows

        self.cell = int(min(max_cell_w, max_cell_h))
        self.cell = clamp(self.cell, 58, 95)

        self.board_w = cols * self.cell
        self.board_h = rows * self.cell

        ox = usable.centerx - self.board_w // 2
        oy = usable.centery - self.board_h // 2

        self.board_origin = (ox, oy)
        self.board_center_x = usable.centerx
        self.board_center_y = usable.centery

    # =========================
    # BACKGROUND
    # =========================
    def draw_bg(self):
        self.screen.blit(self.bg_surface, (0, 0))

    # =========================
    # CLICK FX
    # =========================
    def add_click_effect(self, pos):
        if len(self.click_ripples) < MAX_RIPPLES:
            self.click_ripples.append({
                "x": pos[0], "y": pos[1],
                "r": 4, "max_r": random.randint(28, 48), "life": 12
            })
        if len(self.click_particles) < MAX_PARTICLES:
            for _ in range(4):
                angle = random.uniform(0, math.pi * 2)
                speed = random.uniform(1.2, 3.2)
                self.click_particles.append({
                    "x": pos[0], "y": pos[1],
                    "vx": math.cos(angle) * speed,
                    "vy": math.sin(angle) * speed,
                    "life": random.randint(10, 16),
                })

    def update_click_effects(self):
        for r in self.click_ripples:
            r["r"] += 4
            r["life"] -= 1
        self.click_ripples = [r for r in self.click_ripples if r["life"] > 0 and r["r"] <= r["max_r"]]

        for p in self.click_particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vx"] *= 0.94
            p["vy"] *= 0.94
            p["life"] -= 1
        self.click_particles = [p for p in self.click_particles if p["life"] > 0]

    def draw_click_effects(self):
        for r in self.click_ripples:
            pygame.draw.circle(self.screen, THEME["accent2"],
                               (int(r["x"]), int(r["y"])), int(r["r"]), 2)
        for p in self.click_particles:
            self.screen.blit(self.particle_surface, (p["x"] - 4, p["y"] - 4))

    # =========================
    # LOADING
    # =========================
    def update_loading(self, dt):
        self.loading_elapsed += dt
        if self.loading_frames:
            self.loading_frame_timer += dt
            if self.loading_frame_timer >= 70:
                self.loading_frame_timer = 0
                self.loading_frame_index = (self.loading_frame_index + 1) % len(self.loading_frames)
        if self.loading_elapsed >= self.loading_duration:
            self.change_state("MENU")

    def draw_loading(self):
        self.draw_bg()
        fr = self.frame_loading
        draw_round_rect(self.screen, fr, THEME["panel"], 30)
        draw_round_rect_outline(self.screen, fr, (255, 255, 255), 2, 30)

        cx = fr.centerx

        text1_h = self.font_big.get_height()
        text2_h = self.font_small.get_height()
        gap = 18

        if self.loading_frames:
            frame = self.loading_frames[self.loading_frame_index]
            gif_h = frame.get_height()
            total_h = gif_h + gap + text1_h + gap + text2_h
            block_y = fr.centery - total_h // 2

            gif_rect = frame.get_rect(centerx=cx, top=block_y)
            self.screen.blit(frame, gif_rect)
            text1_cy = gif_rect.bottom + gap + text1_h // 2
        else:
            total_h = text1_h + gap + text2_h
            block_y = fr.centery - total_h // 2
            text1_cy = block_y + text1_h // 2

        dots = "." * ((pygame.time.get_ticks() // 300) % 4)
        draw_text_center(self.screen, f"Loading{dots}", self.font_big,
                         THEME["accent"], (cx, text1_cy), glow=True, glow_color=THEME["accent2"])
        draw_text_center(self.screen, "Preparing the battlefield...", self.font_small,
                         THEME["subtext"], (cx, text1_cy + text1_h // 2 + gap + text2_h // 2))

    # =========================
    # MENU / DIFFICULTY / SIZE / NAMES
    # =========================
    def draw_menu(self):
        self.draw_bg()
        fr = self.frame_menu
        draw_round_rect(self.screen, fr, THEME["panel"], 30)
        draw_round_rect_outline(self.screen, fr, (255, 255, 255), 2, 30)

        cx = fr.centerx

        title_h = self.font_title.get_height()
        block_gap = 42

        btn_top = self.buttons[0].rect.top if self.buttons else fr.centery
        header_bottom = btn_top - block_gap
        title_cy = header_bottom - title_h // 2

        draw_text_center(self.screen, "DOTS & BOXES", self.font_title,
                         THEME["text"], (cx, title_cy), glow=True, glow_color=THEME["accent2"])

        draw_text_center(self.screen, "Choose game mode", self.font_small,
                         THEME["subtext"], (cx, title_cy + 58))

        for b in self.buttons:
            b.draw(self.screen)

    def draw_difficulty_menu(self):
        self.draw_bg()
        fr = self.frame_diff
        draw_round_rect(self.screen, fr, THEME["panel"], 30)
        draw_round_rect_outline(self.screen, fr, (255, 255, 255), 2, 30)

        cx = fr.centerx
        title_h = self.font_title.get_height()
        block_gap = 34

        btn_top = self.buttons[0].rect.top if self.buttons else fr.centery
        title_cy = btn_top - block_gap - title_h // 2

        draw_text_center(self.screen, "CHOOSE DIFFICULTY", self.font_title,
                         THEME["text"], (cx, title_cy), glow=True, glow_color=THEME["accent2"])

        draw_text_center(self.screen, f"Current: {self.difficulty.upper()}", self.font_small,
                         THEME["accent"], (cx, title_cy + 56))

        for b in self.buttons:
            b.draw(self.screen)

    def draw_names_menu(self):
        self.draw_bg()
        fr = self.frame_names
        draw_round_rect(self.screen, fr, THEME["panel"], 30)
        draw_round_rect_outline(self.screen, fr, (255, 255, 255), 2, 30)

        cx = fr.centerx

        draw_text_center(self.screen, "ENTER PLAYER NAMES", self.font_title,
                         THEME["text"], (cx, fr.y + 90), glow=True, glow_color=THEME["accent2"])

        draw_text_center(self.screen, "Player 1", self.font_small, THEME["player"], (cx, fr.y + 195))
        draw_text_center(self.screen, "Player 2", self.font_small, THEME["p2"], (cx, fr.y + 295))

        if self.name_input_1:
            self.name_input_1.draw(self.screen)
        if self.name_input_2:
            self.name_input_2.draw(self.screen)

        for b in self.buttons:
            b.draw(self.screen)

    def draw_size_menu(self):
        self.draw_bg()
        fr = self.frame_size
        draw_round_rect(self.screen, fr, THEME["panel"], 30)
        draw_round_rect_outline(self.screen, fr, (255, 255, 255), 2, 30)

        cx = fr.centerx
        title_h = self.font_title.get_height()
        block_gap = 34

        btn_top = self.buttons[0].rect.top if self.buttons else fr.centery
        title_cy = btn_top - block_gap - title_h // 2

        draw_text_center(self.screen, "CHOOSE BOARD SIZE", self.font_title,
                         THEME["text"], (cx, title_cy), glow=True, glow_color=THEME["accent2"])

        if self.play_mode == "AI":
            draw_text_center(self.screen, f"Difficulty: {self.difficulty.upper()}", self.font_small,
                             THEME["accent"], (cx, title_cy + 54))
        else:
            draw_text_center(self.screen, f"{self.player1_name} vs {self.player2_name}", self.font_small,
                             THEME["accent"], (cx, title_cy + 54))

        if self.play_mode == "AI":
            hs_34 = self.get_highscore((3, 4), self.difficulty)
            hs_45 = self.get_highscore((4, 5), self.difficulty)
            hs_56 = self.get_highscore((5, 6), self.difficulty)

            if len(self.buttons) >= 3:
                draw_text_center(self.screen, f"Best: {hs_34}", self.font_tiny, THEME["success"],
                                 (self.buttons[0].rect.centerx, self.buttons[0].rect.bottom + 20))
                draw_text_center(self.screen, f"Best: {hs_45}", self.font_tiny, THEME["success"],
                                 (self.buttons[1].rect.centerx, self.buttons[1].rect.bottom + 20))
                draw_text_center(self.screen, f"Best: {hs_56}", self.font_tiny, THEME["success"],
                                 (self.buttons[2].rect.centerx, self.buttons[2].rect.bottom + 20))

        for b in self.buttons:
            b.draw(self.screen)

    # =========================
    # BOARD
    # =========================
    def get_dot_pos(self, r, c):
        ox, oy = self.board_origin
        return (ox + c * self.cell, oy + r * self.cell)

    def draw_board(self):
        draw_round_rect(self.screen, self.frame_game, THEME["panel"], 30)
        draw_round_rect_outline(self.screen, self.frame_game, (255, 255, 255), 2, 30)

        if self.board_static_dirty or self.board_static_surface is None:
            self.build_board_static_surface()
        if self.board_static_surface and self.board_static_rect:
            self.screen.blit(self.board_static_surface, self.board_static_rect.topleft)

        if self.board_dynamic_dirty or self.board_dynamic_surface is None:
            self.build_board_dynamic_surface()
        if self.board_dynamic_surface and self.board_static_rect:
            self.screen.blit(self.board_dynamic_surface, self.board_static_rect.topleft)

        self.draw_animating_boxes()
        self.draw_animating_edges()

    def draw_animating_edges(self):
        keep = []
        for edge in self.animating_edges:
            edge["progress"] += 0.20
            t = clamp(edge["progress"], 0.0, 1.0)
            t2 = ease_out_quad(t)

            if edge["owner"] == PLAYER:
                color = THEME["player"]
            elif edge["owner"] == AI:
                color = THEME["ai"]
            else:
                color = THEME["p2"]

            if edge["type"] == "h":
                p1 = self.get_dot_pos(edge["i"], edge["j"])
                p2 = self.get_dot_pos(edge["i"], edge["j"] + 1)
            else:
                p1 = self.get_dot_pos(edge["i"], edge["j"])
                p2 = self.get_dot_pos(edge["i"] + 1, edge["j"])

            x = int(lerp(p1[0], p2[0], t2))
            y = int(lerp(p1[1], p2[1], t2))
            pygame.draw.line(self.screen, color, p1, (x, y), 7)

            if edge["progress"] < 1.0:
                keep.append(edge)
        self.animating_edges = keep

    def draw_animating_boxes(self):
        keep = []
        for box in self.animating_boxes:
            box["progress"] += 0.18
            t = clamp(box["progress"], 0.0, 1.0)
            x, y = self.get_dot_pos(box["r"], box["c"])
            pad = int(14 - 5 * t)
            rect = pygame.Rect(x + pad, y + pad, self.cell - pad * 2, self.cell - pad * 2)

            if box["owner"] == PLAYER:
                color = THEME["player"]
            elif box["owner"] == AI:
                color = THEME["ai"]
            else:
                color = THEME["p2"]

            pygame.draw.rect(self.screen, color, rect, border_radius=16)

            if box["progress"] < 1.0:
                keep.append(box)
        self.animating_boxes = keep

    # =========================
    # SCORE / BOX CHECK
    # =========================
    def count_edges_box(self, r, c):
        cnt = 0
        if self.game.horizon[r][c] != 0:
            cnt += 1
        if self.game.horizon[r + 1][c] != 0:
            cnt += 1
        if self.game.verti[r][c] != 0:
            cnt += 1
        if self.game.verti[r][c + 1] != 0:
            cnt += 1
        return cnt

    def add_score(self, owner, gained):
        if gained <= 0:
            return

        if owner == PLAYER:
            self.game.score['player'] += gained
        elif owner == AI:
            self.game.score['AI'] += gained
        elif owner == PLAYER2:
            self.game.score['AI'] += gained  # tái dùng cột AI làm điểm player2 trong PvP

    def check_new_boxes_and_score(self, owner):
        rows, cols = self.mode
        gained = 0

        for r in range(rows):
            for c in range(cols):
                if self.box_owner[r][c] == -1 and self.count_edges_box(r, c) == 4:
                    self.box_owner[r][c] = owner
                    self.animating_boxes.append({"r": r, "c": c, "owner": owner, "progress": 0.0})
                    gained += 1

        self.add_score(owner, gained)

        self.board_dynamic_dirty = True
        return gained

    def is_game_over(self):
        return len(self.game.edges_move()) == 0

    # =========================
    # HUD
    # =========================
    def draw_hud(self):
        panel = pygame.Rect(20, 14, self.width - 40, 108)
        draw_round_rect(self.screen, panel, THEME["panel"], 24)
        draw_round_rect_outline(self.screen, panel, (255, 255, 255), 2, 24)

        cx = panel.centerx
        left_x = panel.x + panel.w // 4
        right_x = panel.x + panel.w * 3 // 4

        score_y = panel.y + 28
        turn_y = panel.y + 64
        hint_y = panel.y + 88

        if self.play_mode == "AI":
            left_name = self.player1_name
            right_name = "AI"
            right_color = THEME["ai"]
        else:
            left_name = self.player1_name
            right_name = self.player2_name
            right_color = THEME["p2"]

        draw_text_center(self.screen, f"{left_name}: {self.game.score['player']}", self.font_mid,
                         THEME["player"], (left_x, score_y), glow=True, glow_color=THEME["accent2"])
        draw_text_center(self.screen, f"{right_name}: {self.game.score['AI']}", self.font_mid,
                         right_color, (right_x, score_y), glow=True, glow_color=right_color)

        if self.play_mode == "AI":
            turn = f"{self.player1_name} TURN" if self.current_turn == PLAYER else "AI TURN"
            turn_color = THEME["player"] if self.current_turn == PLAYER else THEME["ai"]
        else:
            turn = f"{self.player1_name} TURN" if self.current_turn == PLAYER else f"{self.player2_name} TURN"
            turn_color = THEME["player"] if self.current_turn == PLAYER else THEME["p2"]

        draw_text_center(self.screen, turn, self.font_small, turn_color, (cx, turn_y))
        draw_text_center(self.screen, "Click lines to play", self.font_tiny, THEME["subtext"], (cx, hint_y))

        if self.play_mode == "AI":
            hs = self.get_highscore()
            draw_text_left(
                self.screen,
                f"Mode: {self.mode[0]}x{self.mode[1]} | {self.difficulty.upper()} | Best: {hs}",
                self.font_tiny,
                THEME["success"],
                (28, self.frame_game.bottom + 16)
            )
        else:
            draw_text_left(
                self.screen,
                f"Mode: {self.mode[0]}x{self.mode[1]} | PvP",
                self.font_tiny,
                THEME["success"],
                (28, self.frame_game.bottom + 16)
            )

        if self.back_button_game:
            self.back_button_game.draw(self.screen)

    # =========================
    # GAME DRAW
    # =========================
    def draw_game(self):
        self.draw_bg()
        self.draw_hud()
        self.draw_board()
        self.draw_click_effects()

    # =========================
    # GAME OVER
    # =========================
    def finish_game(self):
        self.update_highscore()
        self.game_over = True
        self.ai_thinking = False
        self.input_locked = True
        self.change_state("GAMEOVER")

    def draw_game_over(self):
        self.draw_game()

        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((THEME["overlay"][0], THEME["overlay"][1], THEME["overlay"][2], 70))
        self.screen.blit(overlay, (0, 0))

        fr = self.frame_gameover
        draw_round_rect(self.screen, fr, THEME["panel"], 30)
        draw_round_rect_outline(self.screen, fr, (255, 255, 255), 2, 30)

        cx = fr.centerx

        result_h = self.font_title.get_height()
        score_h = self.font_big.get_height()
        small_h = self.font_small.get_height()
        gap = 18
        block_gap = 26

        btn_top = self.buttons[0].rect.top if self.buttons else fr.centery
        text_bottom = btn_top - block_gap
        total_text_h = result_h + gap + score_h + gap + small_h
        result_cy = text_bottom - total_text_h + result_h // 2
        score_cy = result_cy + result_h // 2 + gap + score_h // 2
        best_cy = score_cy + score_h // 2 + gap + small_h // 2

        left_score = self.game.score['player']
        right_score = self.game.score['AI']

        if self.play_mode == "AI":
            if left_score > right_score:
                result, color = "YOU WIN!", THEME["success"]
            elif left_score < right_score:
                result, color = "YOU LOSE!", THEME["danger"]
            else:
                result, color = "DRAW!", THEME["accent"]

            draw_text_center(self.screen, result, self.font_title, color,
                             (cx, result_cy), glow=True, glow_color=THEME["accent2"])
            draw_text_center(self.screen,
                             f"{self.player1_name} {left_score}  -  {right_score} AI",
                             self.font_big, THEME["text"], (cx, score_cy))
            draw_text_center(self.screen,
                             f"BEST ({self.mode[0]}x{self.mode[1]} - {self.difficulty.upper()}): {self.get_highscore()}",
                             self.font_small, THEME["success"], (cx, best_cy))
        else:
            if left_score > right_score:
                result, color = f"{self.player1_name} WINS!", THEME["player"]
            elif left_score < right_score:
                result, color = f"{self.player2_name} WINS!", THEME["p2"]
            else:
                result, color = "DRAW!", THEME["accent"]

            draw_text_center(self.screen, result, self.font_title, color,
                             (cx, result_cy), glow=True, glow_color=THEME["accent2"])
            draw_text_center(self.screen,
                             f"{self.player1_name} {left_score}  -  {right_score} {self.player2_name}",
                             self.font_big, THEME["text"], (cx, score_cy))
            draw_text_center(self.screen,
                             f"PVP MODE ({self.mode[0]}x{self.mode[1]})",
                             self.font_small, THEME["success"], (cx, best_cy))

        for b in self.buttons:
            b.draw(self.screen)

    # =========================
    # INPUT
    # =========================
    def get_edge_at_pos(self, pos):
        if not self.game:
            return None
        mx, my = pos
        rows, cols = self.mode
        threshold = 18

        for r in range(rows + 1):
            y = self.board_origin[1] + r * self.cell
            if abs(my - y) <= threshold:
                for c in range(cols):
                    x1 = self.board_origin[0] + c * self.cell
                    x2 = x1 + self.cell
                    if x1 - threshold <= mx <= x2 + threshold:
                        return ("h", r, c)

        for c in range(cols + 1):
            x = self.board_origin[0] + c * self.cell
            if abs(mx - x) <= threshold:
                for r in range(rows):
                    y1 = self.board_origin[1] + r * self.cell
                    y2 = y1 + self.cell
                    if y1 - threshold <= my <= y2 + threshold:
                        return ("v", r, c)
        return None

    def handle_game_click(self, pos):
        if self.state != "GAME":
            return
        if self.game_over:
            return
        if self.input_locked:
            return
        if self.ai_thinking:
            return

        if self.play_mode == "AI" and self.current_turn != PLAYER:
            return

        edge = self.get_edge_at_pos(pos)
        if edge is None:
            return

        move_type, i, j = edge

        if move_type == "h":
            if self.game.horizon[i][j] != 0:
                return
        else:
            if self.game.verti[i][j] != 0:
                return

        self.input_locked = True

        owner = self.current_turn

        if move_type == "h":
            self.game.horizon[i][j] = 1
            self.h_owner[i][j] = owner
        else:
            self.game.verti[i][j] = 1
            self.v_owner[i][j] = owner

        self.game.edges_deactive -= 1

        self.animating_edges.append({
            "type": move_type, "i": i, "j": j,
            "progress": 0.0, "owner": owner
        })

        self.board_dynamic_dirty = True
        gained = self.check_new_boxes_and_score(owner)

        if self.is_game_over():
            self.finish_game()
            return

        if self.play_mode == "AI":
            if gained == 0:
                self.current_turn = AI
                self.ai_thinking = True
                pygame.time.set_timer(pygame.USEREVENT + 1, 350, loops=1)
            else:
                self.current_turn = PLAYER
                self.ai_thinking = False
                self.input_locked = False
        else:
            if gained == 0:
                self.current_turn = PLAYER2 if self.current_turn == PLAYER else PLAYER
            self.ai_thinking = False
            self.input_locked = False

    # =========================
    # AI
    # =========================
    def ai_play(self):
        if self.play_mode != "AI":
            self.ai_thinking = False
            self.input_locked = False
            return

        if self.state != "GAME" or self.game_over or self.current_turn != AI:
            self.ai_thinking = False
            self.input_locked = False
            return

        move = self.game.game(AI)
        if move is None:
            self.ai_thinking = False
            self.input_locked = False
            return

        move_type, i, j = move
        if move_type == "h":
            self.h_owner[i][j] = AI
        else:
            self.v_owner[i][j] = AI

        self.board_dynamic_dirty = True

        self.animating_edges.append({
            "type": move_type, "i": i, "j": j,
            "progress": 0.0, "owner": AI
        })

        gained = self.check_new_boxes_and_score(AI)

        if self.is_game_over():
            self.finish_game()
            self.ai_thinking = False
            return

        if gained > 0:
            self.current_turn = AI
            self.ai_thinking = True
            self.input_locked = True
            pygame.time.set_timer(pygame.USEREVENT + 1, 300, loops=1)
        else:
            self.current_turn = PLAYER
            self.ai_thinking = False
            self.input_locked = False

    # =========================
    # UPDATE
    # =========================
    def update(self, dt):
        mouse_pos = pygame.mouse.get_pos()
        for b in self.buttons:
            b.update(mouse_pos)
        if self.back_button_game:
            self.back_button_game.update(mouse_pos)

        if self.name_input_1:
            self.name_input_1.update(dt)
        if self.name_input_2:
            self.name_input_2.update(dt)

        self.update_click_effects()

        if self.state == "LOADING":
            self.update_loading(dt)

    # =========================
    # DRAW
    # =========================
    def draw(self):
        if self.state == "LOADING":
            self.draw_loading()
        elif self.state == "MENU":
            self.draw_menu()
        elif self.state == "DIFFICULTY":
            self.draw_difficulty_menu()
        elif self.state == "NAMES":
            self.draw_names_menu()
        elif self.state == "SIZE":
            self.draw_size_menu()
        elif self.state == "GAME":
            self.draw_game()
        elif self.state == "GAMEOVER":
            self.draw_game_over()
        pygame.display.flip()

    # =========================
    # RUN
    # =========================
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self.state == "GAME":
                        self.go_back_from_game()
                    elif self.state in ["SIZE", "DIFFICULTY", "GAMEOVER", "NAMES"]:
                        self.go_back()
                    else:
                        self.running = False

                elif event.type == pygame.USEREVENT + 1:
                    self.ai_play()

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.add_click_effect(event.pos)

                # text input
                if self.state == "NAMES":
                    if self.name_input_1:
                        res1 = self.name_input_1.handle_event(event)
                        if res1 == "submit":
                            self.goto_size_from_names()
                    if self.name_input_2:
                        res2 = self.name_input_2.handle_event(event)
                        if res2 == "submit":
                            self.goto_size_from_names()

                button_clicked = False

                for b in self.buttons:
                    if b.handle_event(event):
                        button_clicked = True
                        break

                if not button_clicked and self.back_button_game:
                    if self.back_button_game.handle_event(event):
                        button_clicked = True

                if (
                    self.state == "GAME"
                    and event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1
                    and not button_clicked
                    and not self.game_over
                    and not self.input_locked
                    and not self.ai_thinking
                ):
                    if self.play_mode == "AI":
                        if self.current_turn == PLAYER:
                            self.handle_game_click(event.pos)
                    else:
                        self.handle_game_click(event.pos)

            self.update(dt)
            self.draw()

        pygame.quit()

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    GameUI().run()