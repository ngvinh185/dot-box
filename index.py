import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageSequence
import sys
import json
import os

# Thử import và kiểm tra lỗi Circular Import
try:
    from gamelogic import GameState
except ImportError as e:
    print(f"Lỗi: Không thể import GameState. Chi tiết: {e}")
    sys.exit()

# ================= THEME =================
THEME = {
    "bg": "#FFFFFF",
    "accent": "#1ABC9C",
    "player": "#ED1F08",  # Đỏ
    'AI_active': "#5C0E06", 
    "ai": "#6695B4",      # Xanh
    "dot": "#2C3E50",
    "line_empty": "#C0CAD5",
    "text": "#F1F8F9",
    'text_black': '#000'
}

MARGIN, CELL = 60, 80

class GameGUI:
    def __init__(self, root):
        self.root = root
        self.root.geometry("900x900") 
        self.root.title("Dots & Boxes - AI Edition")
        
        # --- Khởi tạo Stats Hệ thống ---
        self.stats_file = "game_stats.json"
        self.all_stats = self.load_all_stats()
        
        self.rows, self.cols = 3, 4
        self.diff = "easy" # Mặc định
        self.after_id = None
        
        self.setup_menu_canvas()
        self.load_gif("1.gif")
        self.show_start()

    # ================= QUẢN LÝ KỶ LỤC THEO CHẾ ĐỘ =================
    def load_all_stats(self):
        """Tải toàn bộ dữ liệu từ file JSON"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r") as f:
                    return json.load(f)
            except: pass
        return {}

    def get_current_stats(self):
        """Lấy stats riêng cho Size và Độ khó hiện tại"""
        size_key = f"{self.rows}x{self.cols}"
        diff_key = self.diff
        
        # Tạo cấu trúc nếu chưa tồn tại
        if size_key not in self.all_stats:
            self.all_stats[size_key] = {}
        if diff_key not in self.all_stats[size_key]:
            self.all_stats[size_key][diff_key] = {"wins": 0, "high_score": 0}
            
        return self.all_stats[size_key][diff_key]

    def save_all_stats(self):
        """Lưu toàn bộ dữ liệu vào file JSON"""
        with open(self.stats_file, "w") as f:
            json.dump(self.all_stats, f, indent=4)

    # ================= UI HELPERS =================
    def setup_menu_canvas(self):
        self.canvas = tk.Canvas(self.root, width=900, height=900, highlightthickness=0, bg=THEME["bg"])
        self.canvas.pack(fill="both", expand=True)

    def load_gif(self, path):
        self.frames = []
        try:
            img = Image.open(path)
            for f in ImageSequence.Iterator(img):
                self.frames.append(ImageTk.PhotoImage(f.resize((900,900))))
            if self.frames:
                self.bg_img = self.canvas.create_image(0,0,anchor="nw",image=self.frames[0])
                self.frame_idx = 0
                self.animate()
        except:
            self.canvas.config(bg=THEME["bg"])

    def animate(self):
        if hasattr(self, 'canvas') and self.canvas.winfo_exists() and self.frames:
            self.frame_idx = (self.frame_idx + 1) % len(self.frames)
            self.canvas.itemconfig(self.bg_img, image=self.frames[self.frame_idx])
            self.after_id = self.root.after(50, self.animate)

    def stop_animate(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def clear_ui(self):
        self.canvas.delete("ui")

    def create_button(self, y, text, command, color):
        w, h = 260, 60
        x = 450 - w//2
        rect = self.canvas.create_rectangle(x, y, x+w, y+h, fill=color, outline="", tags="ui")
        txt = self.canvas.create_text(450, y+h//2, text=text, font=("Segoe UI", 13, "bold"), fill=THEME["text"], tags="ui")
        def on_e(e): self.canvas.itemconfig(rect, fill=THEME["accent"])
        def on_l(e): self.canvas.itemconfig(rect, fill=color)
        for item in (rect, txt):
            self.canvas.tag_bind(item, "<Enter>", on_e)
            self.canvas.tag_bind(item, "<Leave>", on_l)
            self.canvas.tag_bind(item, "<Button-1>", lambda e: command())

    # ================= SCREENS =================
    def show_start(self):
        self.clear_ui()
        self.canvas.create_text(450, 250, text="DOTS & BOXES", font=("Impact", 85), fill=THEME["accent"], tags="ui")
        self.create_button(520, "START GAME", self.show_size, "#2C3E50")

    def show_size(self):
        self.clear_ui()
        self.canvas.create_text(450, 180, text="SELECT GRID", font=("Impact", 60), fill=THEME["accent"], tags="ui")
        self.create_button(350, "3 x 4 (Tiny)", lambda: self.set_size(3, 4), "#2C3E50")
        self.create_button(430, "4 x 5 (Classic)", lambda: self.set_size(4, 5), "#34495E")
        self.create_button(510, "5 x 6 (Expert)", lambda: self.set_size(5, 6), "#3B4A5A")
        self.create_button(620, "BACK", self.show_start, "#7F8C8D")

    def set_size(self, r, c):
        self.rows, self.cols = r, c
        self.show_diff()

    def show_diff(self):
        self.clear_ui()
        self.canvas.create_text(450, 180, text="DIFFICULTY", font=("Impact", 60), fill=THEME["accent"], tags="ui")
        self.create_button(400, "EASY (Normal)", lambda: self.start_game("easy"), "#27AE60")
        self.create_button(480, "HARD (Minimax)", lambda: self.start_game("hard"), "#E74C3C")
        self.create_button(600, "BACK", self.show_size, "#7F8C8D")

    # ================= GAMEPLAY =================
    def start_game(self, diff):
        self.diff = diff
        self.stop_animate()
        self.canvas.destroy()
        
        self.game_frame = tk.Frame(self.root, bg=THEME["bg"])
        self.game_frame.pack(fill="both", expand=True)
        
        self.state = GameState(self.rows, self.cols, self.diff)
        self.turn = 1 
        
        header = tk.Frame(self.game_frame, bg=THEME["bg"])
        header.pack(fill="x", padx=20, pady=15)
        
        tk.Button(header, text="⬅ EXIT", command=self.exit_game, bg="#C0392B", fg="white", 
                  font=("Arial", 10, "bold"), relief="flat", padx=10).pack(side="left")
        
        self.score_lbl = tk.Label(header, text="", font=("Segoe UI", 18, "bold"), fg="#000", bg=THEME["bg"])
        self.score_lbl.pack(side="right")
        
        cv_w = 2*MARGIN + self.cols*CELL
        cv_h = 2*MARGIN + self.rows*CELL + 100 
        self.cv = tk.Canvas(self.game_frame, width=cv_w, height=cv_h, bg=THEME["bg"], highlightthickness=0)
        self.cv.pack(pady=10)
        self.cv.bind("<Button-1>", self.on_click)
        
        self.update_board()

    def exit_game(self):
        if hasattr(self, 'game_frame'): self.game_frame.destroy()
        self.setup_menu_canvas()
        self.load_gif("1.gif")
        self.show_start()

    def update_board(self):
        self.cv.delete("all")
        self.score_lbl.config(text=f"YOU: {self.state.score['player']}  |  AI: {self.state.score['AI']}")
        
        # --- HIỂN THỊ KỶ LỤC RIÊNG CHO CHẾ ĐỘ NÀY ---
        current_s = self.get_current_stats()
        board_bottom = 2*MARGIN + self.rows*CELL
        
        mode_txt = f"CHẾ ĐỘ: {self.rows}x{self.cols} ({self.diff.upper()})"
        stats_txt = f"Ván thắng: {current_s['wins']}   ★   Điểm cao nhất: {current_s['high_score']}"
        
        # Vẽ tên chế độ màu xám nhẹ
        self.cv.create_text((2*MARGIN + self.cols*CELL)/2, board_bottom + 40, 
                            text=mode_txt, font=("Segoe UI", 10, "italic"), fill="#7F8C8D")
        # Vẽ thông số chính màu đen
        self.cv.create_text((2*MARGIN + self.cols*CELL)/2, board_bottom + 65, 
                            text=stats_txt, font=("Segoe UI", 13, "bold"), fill="#000000")

        # Vẽ Box, Cạnh, Chấm (Giữ nguyên logic của bạn)
        for i in range(self.rows):
            for j in range(self.cols):
                owner = self.state.boxes[i][j]
                if owner:
                    color = "#FADBD8" if owner == 1 else "#D6EAF8" 
                    self.cv.create_rectangle(MARGIN+j*CELL, MARGIN+i*CELL, 
                                           MARGIN+(j+1)*CELL, MARGIN+(i+1)*CELL, fill=color, outline="")
                    txt = "P" if owner == 1 else "AI"
                    self.cv.create_text(MARGIN+j*CELL+CELL/2, MARGIN+i*CELL+CELL/2, 
                                        text=txt, fill=THEME["player"] if owner==1 else THEME["ai"], font=("Arial", 14, "bold"))

        for i in range(self.rows + 1):
            for j in range(self.cols):
                val = self.state.horizon[i][j]
                color = THEME["player"] if val == 1 else (THEME["ai"] if val == 2 else THEME["line_empty"])
                self.cv.create_line(MARGIN+j*CELL, MARGIN+i*CELL, MARGIN+(j+1)*CELL, MARGIN+i*CELL, fill=color, width=5)
        
        for i in range(self.rows):
            for j in range(self.cols + 1):
                val = self.state.verti[i][j]
                color = THEME["player"] if val == 1 else (THEME["ai"] if val == 2 else THEME["line_empty"])
                self.cv.create_line(MARGIN+j*CELL, MARGIN+i*CELL, MARGIN+j*CELL, MARGIN+(i+1)*CELL, fill=color, width=5)

        for i in range(self.rows+1):
            for j in range(self.cols+1):
                x, y = MARGIN+j*CELL, MARGIN+i*CELL
                self.cv.create_oval(x-4, y-4, x+4, y+4, fill=THEME["dot"], outline="")
                
    def on_click(self, e):
        if self.turn != 1: return
        edge = self.find_edge(e.x, e.y)
        if not edge: return
        d, i, j = edge
        if (d == 'h' and self.state.horizon[i][j] == 0) or (d == 'v' and self.state.verti[i][j] == 0):
            if d == 'h': self.state.horizon[i][j] = 1
            else: self.state.verti[i][j] = 1   
            scored = self.check_scoring(1)
            self.update_board()    
            if self.is_over(): return
            if not scored:
                self.turn = 2
                self.root.after(600, self.ai_play)

    def ai_play(self):
        self.state.game(2)
        scored = self.check_scoring(2)
        self.update_board()
        if self.is_over(): return
        if scored:
            self.root.after(600, self.ai_play)
        else:
            self.turn = 1

    def check_scoring(self, owner_id):
        scored = False
        for i in range(self.rows):
            for j in range(self.cols):
                if self.state.boxes[i][j] == 0 and self.state.box_has_4_edges(i, j):
                    self.state.boxes[i][j] = owner_id
                    scored = True
        self.state.score['player'] = sum(x == 1 for row in self.state.boxes for x in row)
        self.state.score['AI'] = sum(x == 2 for row in self.state.boxes for x in row)
        return scored

    def is_over(self):
        total_boxes = self.rows * self.cols
        current_boxes = self.state.score['player'] + self.state.score['AI']
        if current_boxes == total_boxes:
            p, a = self.state.score['player'], self.state.score['AI']
            
            # Lấy stats của chế độ hiện tại để cập nhật
            current_s = self.get_current_stats()
            
            is_new_high = False
            if p > current_s["high_score"]:
                current_s["high_score"] = p
                is_new_high = True
            
            if p > a:
                current_s["wins"] += 1
                msg = f"CHÚC MỪNG! Bạn thắng {p}-{a}"
                if is_new_high: msg += f"\n🏆 KỶ LỤC MỚI TRONG CHẾ ĐỘ NÀY: {p}!"
            elif a > p: msg = f"AI THẮNG! Tỉ số {a}-{p}"
            else: msg = f"HÒA! Tỉ số {p}-{p}"
            
            self.save_all_stats()
            messagebox.showinfo("Kết thúc", msg)
            self.exit_game()
            return True
        return False

    def find_edge(self, x, y):
        for i in range(self.rows + 1):
            for j in range(self.cols):
                x1, y1 = MARGIN+j*CELL, MARGIN+i*CELL
                if x1+5 < x < x1+CELL-5 and abs(y - y1) < 15: return ('h', i, j)
        for i in range(self.rows):
            for j in range(self.cols + 1):
                x1, y1 = MARGIN+j*CELL, MARGIN+i*CELL
                if abs(x - x1) < 15 and y1+5 < y < y1+CELL-5: return ('v', i, j)
        return None

if __name__ == "__main__":
    root = tk.Tk()
    app = GameGUI(root)
    root.mainloop()