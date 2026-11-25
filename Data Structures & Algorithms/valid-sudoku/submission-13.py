class Solution:
    def isValidSudoku(self, board: List[List[str]]) -> bool:
        rows = defaultdict(set)
        cols = defaultdict(set)
        box = defaultdict(set)
 
        for r in range(9):
            for c in range(9):
                cell = board[r][c]
                if cell == ".":
                    continue
                if cell in rows[r] or cell in cols[c] or cell in box[(r // 3, c // 3)]:
                    return False
                rows[int(r)].add(cell)
                cols[int(c)].add(cell)
                box[(int(r) // 3, int(c) // 3)].add(cell)

        return True