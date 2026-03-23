AI = 1
PLAYER = 0
import random
class GameState:
    def __init__(self, ROWS, COLS, difficults):
        self.horizon = [[0] * COLS for _ in range(ROWS + 1)]
        self.verti = [[0] * (COLS + 1) for _ in range(ROWS)]
        self.boxes = [[0] * COLS for _ in range(ROWS)]
        self.ROWS = ROWS
        self.COLS = COLS
        self.score = {'player': 0, 'AI': 0}
        self.edges_deactive = (self.ROWS + 1) * self.COLS + (self.COLS + 1) * self.ROWS
        self.difficults = difficults
    def edges_move(self):
        edges_equal_3 = []
        edges_equal_2 = []
        edges_normal = []
        for i in range(self.ROWS + 1):
            for j in range(self.COLS):
                if self.horizon[i][j] == 0:
                    if (i < self.ROWS and self.box_has_3_edges(i, j)) or (i - 1 >= 0 and self.box_has_3_edges(i - 1, j)):
                        edges_equal_3.append(['h', i, j])
                    elif (i < self.ROWS and self.box_has_2_edges(i, j)) or (i - 1 >= 0 and self.box_has_2_edges(i - 1, j)):
                        edges_equal_2.append(['h', i, j])
                    
                    else:
                        edges_normal.append(['h', i, j])
        for i in range(self.ROWS):
            for j in range(self.COLS + 1):
                if self.verti[i][j] == 0:
                    if (j < self.COLS and self.box_has_3_edges(i, j)) or (j - 1 >= 0 and self.box_has_3_edges(i, j - 1)):
                        edges_equal_3.append(['v', i, j])
                    elif (j < self.COLS and self.box_has_2_edges(i, j)) or (j - 1 >= 0 and self.box_has_2_edges(i, j - 1)):
                        edges_equal_2.append(['v', i, j])  
                    else:
                        edges_normal.append(['v', i, j])
        random.shuffle(edges_equal_3)
        random.shuffle(edges_equal_2)
        random.shuffle(edges_normal)
        
        edges = (edges_equal_3 + edges_normal + edges_equal_2)
        # print(edges)
        return edges
    
    def box_has_3_edges(self, r, c):
        cnt = 0

        # trên
        if self.horizon[r][c] != 0:
            cnt += 1
        # dưới
        if self.horizon[r + 1][c] != 0:
            cnt += 1
        # trái
        if self.verti[r][c] != 0:
            cnt += 1
        # phải
        if self.verti[r][c + 1] != 0:
            cnt += 1

        return cnt == 3
    def box_has_2_edges(self, r, c):
        cnt = 0

        # trên
        if self.horizon[r][c] != 0:
            cnt += 1
        # dưới
        if self.horizon[r + 1][c] != 0:
            cnt += 1
        # trái
        if self.verti[r][c] != 0:
            cnt += 1
        # phải
        if self.verti[r][c + 1] != 0:
            cnt += 1

        return cnt == 2
    def box_has_4_edges(self, r, c):
        cnt = 0

        # trên
        if self.horizon[r][c] != 0:
            cnt += 1
        # dưới
        if self.horizon[r + 1][c] != 0:
            cnt += 1
        # trái
        if self.verti[r][c] != 0:
            cnt += 1
        # phải
        if self.verti[r][c + 1] != 0:
            cnt += 1

        return cnt == 4

    def game(self, player):
        if self.difficults == 'hard':
            if self.edges_deactive > self.edges_deactive / 3:
                self.edges_deactive -= 1
                return self.normal_move()
            else: 
                _, move = self.minimax(10000, -10000, player, 0, 0)
                dir, i, j = move
                if dir == 'h': self.horizon[i][j] = 1
                else: self.verti[i][j] = 1
                self.edges_deactive -= 1
                return move
        else:
          return self.normal_move()
        
    def normal_move(self):
        moves = self.edges_move()
        dir, i, j = moves[0]
        if dir == 'h': self.horizon[i][j] = 1
        else: self.verti[i][j] = 1
        return moves[0]
    def count_box(self):
        cnt = 0
        for i in range(self.ROWS):
            for j in range(self.COLS):
                if self.box_has_4_edges(i, j): cnt += 1
        return cnt      
        
      
    def minimax(self, beta, alpha, player, player_score, AI_score):
        moves = self.edges_move()
        if len(moves) == 0:
            return (AI_score - player_score, -1)
        
        if player == AI: 
            ans = -10000009
            save_move = -1
            for move in moves:
                dir, i, j = move
                cnt_box = self.count_box()
                if dir == 'h':
                    self.horizon[i][j] = 1
                else: self.verti[i][j] = 1
                delta = self.count_box() - cnt_box
                if delta == 0: new_player = (player + 1) % 2
                else:
                    AI_score += delta
                    new_player = player
                res, _ = self.minimax(beta, alpha, new_player, player_score, AI_score)
                if ans < res:
                    ans = res
                    save_move = move
                alpha = max(alpha, ans)
                if dir == 'h':
                    self.horizon[i][j] = 0
                else: self.verti[i][j] = 0
                if delta != 0: AI_score -= delta
                if beta < alpha: 
                    break
            return (ans, save_move)
        else:
            ans = 1000009
            save_move = -1
            for move in moves:
                cnt_box = self.count_box()
                dir, i, j = move
                if dir == 'h':
                    self.horizon[i][j] = 1
                else: self.verti[i][j] = 1
                delta = self.count_box() - cnt_box
                if delta == 0: new_player = (player + 1) % 2
                else:
                    player_score +=delta
                    new_player = player
                res, _ = self.minimax(beta, alpha, new_player, player_score, AI_score)
                
                if ans > res:
                    ans = res
                    save_move = move
                beta = min(beta, ans)
                if delta != 0: player_score -= delta
                if dir == 'h':
                    self.horizon[i][j] = 0
                else: self.verti[i][j] = 0
                if beta < alpha: 
                    break
            return (ans, save_move)   