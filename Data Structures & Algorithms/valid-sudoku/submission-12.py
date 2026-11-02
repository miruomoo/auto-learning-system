class Solution:
    def isValidSudoku(self, board: List[List[str]]) -> bool:
        colSet = defaultdict(set)
        rowSet = defaultdict(set)
        boxSet = defaultdict(set)

        for r in range(9):
            for c in range(9):
                if board[r][c] == ".":
                    continue
                num = board[r][c]
                if num in rowSet[r] or num in colSet[c] or num in boxSet[(r // 3, c // 3)]:
                    return False
                rowSet[r].add(num)
                colSet[c].add(num)
                boxSet[(r // 3, c // 3)].add(num)

        return True

#T: O(N * M)
#S: O(N * M)