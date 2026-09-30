class Solution:
    def isValidSudoku(self, board: List[List[str]]) -> bool:
        rowSet = defaultdict(set)
        colSet = defaultdict(set)
        boxSet = defaultdict(set)

        rows, cols = 9, 9

        for r in range(rows):
            for c in range(cols):
                if board[r][c] == ".":
                    continue
                if board[r][c] in rowSet[r] or board[r][c] in colSet[c] or board[r][c] in boxSet[(r // 3) * 3 + (c // 3)]:
                    return False
                else:
                    rowSet[r].add(board[r][c])
                    colSet[c].add(board[r][c])
                    boxSet[(r // 3) * 3 + (c // 3)].add(board[r][c])

        return True

                