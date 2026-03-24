import pygame
import random
import math
import os
from PIL import Image, ImageSequence
from gamelogic import GameState

# =========================
# CONFIG
# =========================
FPS = 60

PLAYER = 0
AI = 1

THEME = {
    "bg": (14, 16, 26),
    "grid": (28, 32, 48),
    "panel": (22, 24, 36),
    "panel2": (30, 34, 50),
    "text": (245, 245, 255),
    "subtext": (180, 185, 210),
    "player": (255, 105, 180),
    "ai": (80, 200, 255),
    "accent": (180, 120, 255),
    "accent2": (255, 180, 220),
    "success": (120, 255, 180),
    "danger": (255, 90, 120),
}

MAX_RIPPLES   = 6
MAX_PARTICLES = 24

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
        pygame.draw.rect(surface, (8, 8, 16), shadow, border_radius=24)
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
# UI
# =========================
class GameUI:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("DOTS & BOXES - NEON")

        info = pygame.display.Info()
        self.width = info.current_w
        self.height = info.current_h

        self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN)
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_title = pygame.font.SysFont("arial", max(42, self.width // 24), bold=True)
        self.font_big   = pygame.font.SysFont("arial", max(30, self.width // 40), bold=True)
        self.font_mid   = pygame.font.SysFont("arial", max(22, self.width // 60), bold=True)
        self.font_small = pygame.font.SysFont("arial", max(18, self.width // 80))

        # State
        self.state   = "LOADING"
        self.running = True
        self.buttons = []

        # Game
        self.game         = None
        self.mode         = None
        self.game_over    = False
        self.ai_thinking  = False
        self.current_turn = PLAYER

        # Board layout
        self.board_origin   = (0, 0)
        self.cell           = 110
        self.board_w        = 0
        self.board_h        = 0
        self.board_center_x = self.width  // 2
        self.board_center_y = self.height // 2

        # Edge / box ownership
        self.h_owner   = []
        self.v_owner   = []
        self.box_owner = []

        # Effects
        self.click_ripples    = []
        self.click_particles  = []
        self.animating_edges  = []
        self.animating_boxes  = []

        # ── Cached surfaces ───────────────────────────────────────────────
        self.bg_surface           = None   # static grid background
        self.board_static_surface = None   # dots + empty lines (rebuilt on new game)
        self.board_static_rect    = None
        self.board_static_dirty   = True

        # NEW: caches owned edges + filled boxes; rebuilt only on each move
        self.board_dynamic_surface = None
        self.board_dynamic_dirty   = True  # set True after every move
        # ─────────────────────────────────────────────────────────────────

        # Small reusable particle sprite
        self.particle_surface = pygame.Surface((8, 8), pygame.SRCALPHA)
        pygame.draw.circle(self.particle_surface, (255, 200, 240, 220), (4, 4), 3)

        # Loading
        self.loading_frames      = []
        self.loading_frame_index = 0
        self.loading_frame_timer = 0
        self.loading_elapsed     = 0
        self.loading_duration    = 1600

        # Frame rects
        self.frame_loading  = None
        self.frame_menu     = None
        self.frame_size     = None
        self.frame_game     = None
        self.frame_gameover = None

        self.build_bg_surface()
        self.build_frames()

        self.loading_gif = self.load_gif(
            "1.gif",
            max_size=(min(self.width * 0.42, 500), min(self.height * 0.45, 420))
        )
        if self.loading_gif:
            self.loading_frames = self.loading_gif

        self.change_state("LOADING")

    # =========================
    # FRAME LAYOUTS
    # =========================
    def build_frames(self):
        W, H = self.width, self.height
        pad_x = 120
        pad_y = 120

        self.frame_loading = pygame.Rect(
            W // 2 - min(720, W - pad_x) // 2,
            H // 2 - min(540, H - pad_y) // 2,
            min(720, W - pad_x),
            min(540, H - pad_y)
        )
        self.frame_menu = pygame.Rect(
            W // 2 - min(760, W - pad_x) // 2,
            H // 2 - min(560, H - pad_y) // 2,
            min(760, W - pad_x),
            min(560, H - pad_y)
        )
        self.frame_size = pygame.Rect(
            W // 2 - min(760, W - pad_x) // 2,
            H // 2 - min(620, H - pad_y) // 2,
            min(760, W - pad_x),
            min(620, H - pad_y)
        )
        self.frame_game = pygame.Rect(70, 140, W - 140, H - 230)
        self.frame_gameover = pygame.Rect(
            W // 2 - min(760, W - 160) // 2,
            H // 2 - min(460, H - 180) // 2,
            min(760, W - 160),
            min(460, H - 180)
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
        """Dots + dim empty line grid — rebuilt once per new game."""
        if not self.mode:
            return
        rows, cols = self.mode
        ox, oy = self.board_origin
        bw = self.board_w
        bh = self.board_h

        panel = pygame.Rect(ox - 34, oy - 34, bw + 68, bh + 68)
        self.board_static_rect = panel.copy()
        surf = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)

        draw_round_rect(surf, pygame.Rect(0, 0, panel.w, panel.h), (18, 20, 30), 28)
        draw_round_rect_outline(surf, pygame.Rect(0, 0, panel.w, panel.h), (255, 255, 255), 2, 28)

        # dim background lines
        for r in range(rows + 1):
            for c in range(cols):
                p1 = self.get_dot_pos(r, c)
                p2 = self.get_dot_pos(r, c + 1)
                pygame.draw.line(surf, (50, 55, 75),
                    (p1[0] - panel.x, p1[1] - panel.y),
                    (p2[0] - panel.x, p2[1] - panel.y), 3)
        for r in range(rows):
            for c in range(cols + 1):
                p1 = self.get_dot_pos(r, c)
                p2 = self.get_dot_pos(r + 1, c)
                pygame.draw.line(surf, (50, 55, 75),
                    (p1[0] - panel.x, p1[1] - panel.y),
                    (p2[0] - panel.x, p2[1] - panel.y), 3)

        # dots
        for r in range(rows + 1):
            for c in range(cols + 1):
                x, y = self.get_dot_pos(r, c)
                lx = x - panel.x
                ly = y - panel.y
                pygame.draw.circle(surf, (255, 255, 255), (lx, ly), 8)
                pygame.draw.circle(surf, THEME["accent2"], (lx, ly), 6)

        self.board_static_surface = surf
        self.board_static_dirty   = False

    def build_board_dynamic_surface(self):
        """
        Owned (coloured) edges + filled boxes — rebuilt only after a move,
        NOT every frame.
        """
        if not self.mode:
            return
        rows, cols = self.mode
        panel = self.board_static_rect

        surf = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)

        # filled boxes
        for r in range(rows):
            for c in range(cols):
                owner = self.box_owner[r][c]
                if owner != -1:
                    x, y = self.get_dot_pos(r, c)
                    rect = pygame.Rect(x - panel.x + 9, y - panel.y + 9,
                                       self.cell - 18, self.cell - 18)
                    color = THEME["player"] if owner == PLAYER else THEME["ai"]
                    pygame.draw.rect(surf, color, rect, border_radius=16)

        # owned horizontal edges
        for r in range(rows + 1):
            for c in range(cols):
                owner = self.h_owner[r][c]
                if owner != -1:
                    p1 = self.get_dot_pos(r, c)
                    p2 = self.get_dot_pos(r, c + 1)
                    color = THEME["player"] if owner == PLAYER else THEME["ai"]
                    pygame.draw.line(surf, color,
                        (p1[0] - panel.x, p1[1] - panel.y),
                        (p2[0] - panel.x, p2[1] - panel.y), 7)

        # owned vertical edges
        for r in range(rows):
            for c in range(cols + 1):
                owner = self.v_owner[r][c]
                if owner != -1:
                    p1 = self.get_dot_pos(r, c)
                    p2 = self.get_dot_pos(r + 1, c)
                    color = THEME["player"] if owner == PLAYER else THEME["ai"]
                    pygame.draw.line(surf, color,
                        (p1[0] - panel.x, p1[1] - panel.y),
                        (p2[0] - panel.x, p2[1] - panel.y), 7)

        self.board_dynamic_surface = surf
        self.board_dynamic_dirty   = False

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
        self.state = new_state
        self.buttons.clear()

        if new_state == "LOADING":
            return

        if new_state == "MENU":
            bw = min(360, self.frame_menu.w // 2)
            bh = 72
            gap = 24
            # Center buttons as a group in the lower half of the frame
            rects = stack_center_rects(self.frame_menu, [(bw, bh), (bw, bh)], gap=gap, offset_y=80)
            self.buttons = [
                Button(rects[0], "PLAY VS AI", self.goto_size, font=self.font_mid),
                Button(rects[1], "EXIT",        self.exit_game,
                       base_color=(70, 40, 50), hover_color=THEME["danger"], font=self.font_mid),
            ]

        elif new_state == "SIZE":
            bw = min(380, self.frame_size.w // 2)
            bh = 70
            gap = 18
            rects = stack_center_rects(
                self.frame_size,
                [(bw, bh), (bw, bh), (bw, bh), (160, 54)],
                gap=gap, offset_y=50
            )
            self.buttons = [
                Button(rects[0], "3 x 4", lambda: self.start_game((3, 4)), font=self.font_mid),
                Button(rects[1], "4 x 5", lambda: self.start_game((4, 5)), font=self.font_mid),
                Button(rects[2], "5 x 6", lambda: self.start_game((5, 6)), font=self.font_mid),
                Button(rects[3], "BACK",  self.goto_menu,                  font=self.font_small),
            ]

        elif new_state == "GAMEOVER":
            bw = min(320, self.frame_gameover.w // 2)
            bh = 68
            gap = 20
            rects = stack_center_rects(
                self.frame_gameover, [(bw, bh), (bw, bh)], gap=gap, offset_y=90
            )
            self.buttons = [
                Button(rects[0], "PLAY AGAIN", lambda: self.start_game(self.mode), font=self.font_mid),
                Button(rects[1], "MENU",        self.goto_menu,                     font=self.font_mid),
            ]

    def goto_menu(self):  self.change_state("MENU")
    def goto_size(self):  self.change_state("SIZE")
    def exit_game(self):  self.running = False

    # =========================
    # GAME START
    # =========================
    def start_game(self, mode):
        self.mode = mode
        rows, cols = mode
        self.game = GameState(rows, cols, 'hard')

        self.game_over   = False
        self.ai_thinking = False
        self.current_turn = PLAYER

        self.animating_edges.clear()
        self.animating_boxes.clear()
        self.click_ripples.clear()
        self.click_particles.clear()

        self.h_owner   = [[-1] * cols       for _ in range(rows + 1)]
        self.v_owner   = [[-1] * (cols + 1) for _ in range(rows)]
        self.box_owner = [[-1] * cols       for _ in range(rows)]

        self.compute_board_layout()
        self.board_static_dirty  = True
        self.board_dynamic_dirty = True
        self.board_dynamic_surface = None

        self.state = "GAME"
        self.buttons.clear()

    def compute_board_layout(self):
        rows, cols = self.mode
        content_margin_x = 90
        content_margin_y = 55

        usable = pygame.Rect(
            self.frame_game.x + content_margin_x,
            self.frame_game.y + content_margin_y,
            self.frame_game.w - content_margin_x * 2,
            self.frame_game.h - content_margin_y * 2
        )

        scale = 0.78
        max_cell_w = (usable.w * scale) / cols
        max_cell_h = (usable.h * scale) / rows

        self.cell = int(min(max_cell_w, max_cell_h))
        self.cell = clamp(self.cell, 58, 105)

        self.board_w = cols * self.cell
        self.board_h = rows * self.cell

        ox = usable.centerx - self.board_w // 2
        oy = usable.centery - self.board_h // 2

        self.board_origin   = (ox, oy)
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
            r["r"]    += 4
            r["life"] -= 1
        self.click_ripples = [r for r in self.click_ripples if r["life"] > 0 and r["r"] <= r["max_r"]]

        for p in self.click_particles:
            p["x"]  += p["vx"]
            p["y"]  += p["vy"]
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
        draw_round_rect(self.screen, fr, (18, 20, 30), 30)
        draw_round_rect_outline(self.screen, fr, (255, 255, 255), 2, 30)

        cx = fr.centerx

        # Measure content height to vertically centre the whole block
        text1_h = self.font_big.get_height()
        text2_h = self.font_small.get_height()
        gap     = 14

        if self.loading_frames:
            frame   = self.loading_frames[self.loading_frame_index]
            gif_h   = frame.get_height()
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
                         THEME["accent2"], (cx, text1_cy), glow=True, glow_color=THEME["accent"])
        draw_text_center(self.screen, "Preparing the neon battlefield...", self.font_small,
                         THEME["subtext"], (cx, text1_cy + text1_h // 2 + gap + text2_h // 2))

    # =========================
    # MENU / SIZE
    # =========================
    def draw_menu(self):
        self.draw_bg()
        fr = self.frame_menu
        draw_round_rect(self.screen, fr, (18, 20, 30), 30)
        draw_round_rect_outline(self.screen, fr, (255, 255, 255), 2, 30)

        cx = fr.centerx

        # Measure title block height so we can centre everything together
        title_h    = self.font_title.get_height()
        sub_h      = self.font_mid.get_height()
        btn_h      = 72
        title_gap  = 14
        block_gap  = 36

        # Buttons are centred at offset_y=80 via stack_center_rects → accept that
        # Just derive title position from where buttons start
        btn_top = self.buttons[0].rect.top if self.buttons else fr.centery
        header_bottom = btn_top - block_gap
        header_h = title_h + title_gap + sub_h
        title_cy = header_bottom - header_h + title_h // 2
        sub_cy   = title_cy + title_h // 2 + title_gap + sub_h // 2

        draw_text_center(self.screen, "DOTS & BOXES", self.font_title,
                         THEME["text"], (cx, title_cy), glow=True, glow_color=THEME["accent"])
        draw_text_center(self.screen, "NEON EDITION", self.font_mid,
                         THEME["accent2"], (cx, sub_cy))

        for b in self.buttons:
            b.draw(self.screen)

    def draw_size_menu(self):
        self.draw_bg()
        fr = self.frame_size
        draw_round_rect(self.screen, fr, (18, 20, 30), 30)
        draw_round_rect_outline(self.screen, fr, (255, 255, 255), 2, 30)

        cx = fr.centerx
        title_h   = self.font_title.get_height()
        block_gap = 32

        btn_top  = self.buttons[0].rect.top if self.buttons else fr.centery
        title_cy = btn_top - block_gap - title_h // 2

        draw_text_center(self.screen, "CHOOSE BOARD SIZE", self.font_title,
                         THEME["text"], (cx, title_cy), glow=True, glow_color=THEME["accent"])

        for b in self.buttons:
            b.draw(self.screen)

    # =========================
    # BOARD
    # =========================
    def get_dot_pos(self, r, c):
        ox, oy = self.board_origin
        return (ox + c * self.cell, oy + r * self.cell)

    def draw_board(self):
        draw_round_rect(self.screen, self.frame_game, (18, 20, 30), 30)
        draw_round_rect_outline(self.screen, self.frame_game, (255, 255, 255), 2, 30)

        # ── Static layer (dots + dim grid) ───────────────────────────────
        if self.board_static_dirty or self.board_static_surface is None:
            self.build_board_static_surface()
        if self.board_static_surface and self.board_static_rect:
            self.screen.blit(self.board_static_surface, self.board_static_rect.topleft)

        # ── Dynamic layer (owned edges + filled boxes) ───────────────────
        # Rebuild only when a move has been made, not every frame
        if self.board_dynamic_dirty or self.board_dynamic_surface is None:
            self.build_board_dynamic_surface()
        if self.board_dynamic_surface and self.board_static_rect:
            self.screen.blit(self.board_dynamic_surface, self.board_static_rect.topleft)

        # ── Animation overlays (small, short-lived) ───────────────────────
        self.draw_animating_boxes()
        self.draw_animating_edges()

    # kept for animation pass only – no longer called every frame for static data
    def draw_animating_edges(self):
        keep = []
        for edge in self.animating_edges:
            edge["progress"] += 0.20
            t  = clamp(edge["progress"], 0.0, 1.0)
            t2 = ease_out_quad(t)
            color = THEME["player"] if edge["owner"] == PLAYER else THEME["ai"]
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
            t   = clamp(box["progress"], 0.0, 1.0)
            x, y = self.get_dot_pos(box["r"], box["c"])
            pad  = int(14 - 5 * t)
            rect = pygame.Rect(x + pad, y + pad, self.cell - pad * 2, self.cell - pad * 2)
            color = THEME["player"] if box["owner"] == PLAYER else THEME["ai"]
            pygame.draw.rect(self.screen, color, rect, border_radius=16)
            if box["progress"] < 1.0:
                keep.append(box)
        self.animating_boxes = keep

    # =========================
    # SCORE / BOX CHECK
    # =========================
    def count_edges_box(self, r, c):
        cnt = 0
        if self.game.horizon[r][c]     != 0: cnt += 1
        if self.game.horizon[r + 1][c] != 0: cnt += 1
        if self.game.verti[r][c]       != 0: cnt += 1
        if self.game.verti[r][c + 1]   != 0: cnt += 1
        return cnt

    def check_new_boxes_and_score(self, owner):
        rows, cols = self.mode
        gained = 0
        for r in range(rows):
            for c in range(cols):
                if self.box_owner[r][c] == -1 and self.count_edges_box(r, c) == 4:
                    self.box_owner[r][c] = owner
                    self.animating_boxes.append({"r": r, "c": c, "owner": owner, "progress": 0.0})
                    gained += 1
        if gained > 0:
            if owner == PLAYER:
                self.game.score['player'] += gained
            else:
                self.game.score['AI'] += gained
        # Mark dynamic surface dirty so it will be rebuilt next frame
        self.board_dynamic_dirty = True
        return gained

    def is_game_over(self):
        return len(self.game.edges_move()) == 0

    # =========================
    # HUD
    # =========================
    def draw_hud(self):
        panel = pygame.Rect(30, 20, self.width - 60, 100)
        draw_round_rect(self.screen, panel, (20, 22, 34), 26)
        draw_round_rect_outline(self.screen, panel, (255, 255, 255), 2, 26)

        cx      = panel.centerx
        left_x  = panel.x + panel.w // 4
        right_x = panel.x + panel.w * 3 // 4
        mid_y   = panel.y + panel.h // 2 - 10
        hint_y  = panel.y + panel.h // 2 + 20

        draw_text_center(self.screen, f"PLAYER: {self.game.score['player']}", self.font_mid,
                         THEME["player"], (left_x, mid_y), glow=True, glow_color=THEME["accent2"])
        draw_text_center(self.screen, f"AI: {self.game.score['AI']}", self.font_mid,
                         THEME["ai"],     (right_x, mid_y), glow=True, glow_color=THEME["ai"])

        turn       = "PLAYER TURN" if self.current_turn == PLAYER else "AI TURN"
        turn_color = THEME["player"] if self.current_turn == PLAYER else THEME["ai"]
        draw_text_center(self.screen, turn, self.font_small, turn_color, (cx, hint_y))

        draw_text_center(self.screen, "ESC: Exit  |  Click lines to play",
                         self.font_small, THEME["subtext"], (cx, self.height - 24))

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
        self.game_over   = True
        self.ai_thinking = False
        self.change_state("GAMEOVER")

    def draw_game_over(self):
        self.draw_game()

        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        fr = self.frame_gameover
        draw_round_rect(self.screen, fr, (18, 20, 30), 30)
        draw_round_rect_outline(self.screen, fr, (255, 255, 255), 2, 30)

        cx = fr.centerx

        # Measure and centre the text block above the buttons
        result_h = self.font_title.get_height()
        score_h  = self.font_big.get_height()
        gap      = 16
        block_gap = 28

        btn_top    = self.buttons[0].rect.top if self.buttons else fr.centery
        text_bottom = btn_top - block_gap
        total_text_h = result_h + gap + score_h
        result_cy = text_bottom - total_text_h + result_h // 2
        score_cy  = result_cy + result_h // 2 + gap + score_h // 2

        if self.game.score['player'] > self.game.score['AI']:
            result, color = "YOU WIN!",  THEME["success"]
        elif self.game.score['player'] < self.game.score['AI']:
            result, color = "YOU LOSE!", THEME["danger"]
        else:
            result, color = "DRAW!",     THEME["accent2"]

        draw_text_center(self.screen, result, self.font_title, color,
                         (cx, result_cy), glow=True, glow_color=THEME["accent"])
        draw_text_center(self.screen,
                         f"PLAYER {self.game.score['player']}  -  {self.game.score['AI']} AI",
                         self.font_big, THEME["text"], (cx, score_cy))

        for b in self.buttons:
            b.draw(self.screen)

    # =========================
    # INPUT
    # =========================
    def get_edge_at_pos(self, pos):
        if not self.game:
            return None
        mx, my    = pos
        rows, cols = self.mode
        threshold  = 20

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
        if self.state != "GAME": return
        if self.game_over:        return
        if self.ai_thinking:      return
        if self.current_turn != PLAYER: return

        edge = self.get_edge_at_pos(pos)
        if edge is None:
            return

        move_type, i, j = edge
        if move_type == "h":
            if self.game.horizon[i][j] != 0: return
            self.game.horizon[i][j] = 1
            self.h_owner[i][j] = PLAYER
        else:
            if self.game.verti[i][j] != 0: return
            self.game.verti[i][j] = 1
            self.v_owner[i][j] = PLAYER

        self.game.edges_deactive -= 1

        self.animating_edges.append({
            "type": move_type, "i": i, "j": j,
            "progress": 0.0, "owner": PLAYER
        })
        # dynamic surface will be marked dirty inside check_new_boxes_and_score
        # but we also need it dirty for the edge itself
        self.board_dynamic_dirty = True

        gained = self.check_new_boxes_and_score(PLAYER)

        if self.is_game_over():
            self.finish_game()
            return

        if gained == 0:
            self.current_turn = AI
            self.ai_thinking  = True
            pygame.time.set_timer(pygame.USEREVENT + 1, 350, loops=1)

    # =========================
    # AI
    # =========================
    def ai_play(self):
        if self.state != "GAME" or self.game_over or self.current_turn != AI:
            self.ai_thinking = False
            return

        move = self.game.game(AI)
        if move is None:
            self.ai_thinking = False
            return

        move_type, i, j = move
        if move_type == "h":
            self.h_owner[i][j] = AI
        else:
            self.v_owner[i][j] = AI

        self.board_dynamic_dirty = True   # ← mark dirty on AI move too

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
            self.ai_thinking  = True
            pygame.time.set_timer(pygame.USEREVENT + 1, 300, loops=1)
        else:
            self.current_turn = PLAYER
            self.ai_thinking  = False

    # =========================
    # UPDATE
    # =========================
    def update(self, dt):
        mouse_pos = pygame.mouse.get_pos()
        for b in self.buttons:
            b.update(mouse_pos)
        self.update_click_effects()
        if self.state == "LOADING":
            self.update_loading(dt)

    # =========================
    # DRAW
    # =========================
    def draw(self):
        if   self.state == "LOADING":  self.draw_loading()
        elif self.state == "MENU":     self.draw_menu()
        elif self.state == "SIZE":     self.draw_size_menu()
        elif self.state == "GAME":     self.draw_game()
        elif self.state == "GAMEOVER": self.draw_game_over()
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
                    self.running = False
                elif event.type == pygame.USEREVENT + 1:
                    self.ai_play()

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.add_click_effect(event.pos)

                button_clicked = False
                for b in self.buttons:
                    if b.handle_event(event):
                        button_clicked = True
                        break

                if (self.state == "GAME"
                        and event.type == pygame.MOUSEBUTTONDOWN
                        and event.button == 1
                        and not button_clicked):
                    self.handle_game_click(event.pos)

            self.update(dt)
            self.draw()

        pygame.quit()

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    GameUI().run()