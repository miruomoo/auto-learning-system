class Solution:
    def isValidSudoku(self, board: List[List[str]]) -> bool:
        rows, cols = 9, 9
        rowDict = defaultdict(set)
        colDict = defaultdict(set)
        boxDict = defaultdict(set) #(r, c)

        for r in range(rows):
            for c in range(cols):
                val = board[r][c]
                if val == ".":
                    continue
                if val in rowDict[r] or val in colDict[c] or val in boxDict[(r // 3, c // 3)]:
                    return False
                rowDict[r].add(val)
                colDict[c].add(val)
                boxDict[(r // 3, c // 3)].add(val)

        return True