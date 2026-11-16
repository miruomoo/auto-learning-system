class Solution:
    def longestIncreasingPath(self, matrix: List[List[int]]) -> int:
        row, col = len(matrix), len(matrix[0])
        dirs = [[0, 1], [1, 0], [-1, 0], [0, -1]]
        dp = {}

        def dfs(r, c, prev):
            if r < 0 or c < 0 or r == row or c == col or matrix[r][c] <= prev:
                return 0

            if (r, c) in dp:
                return dp[(r, c)]

            dp[(r, c)] = 0
            for dr, dc in dirs:
                newRow, newCol = r + dr, c + dc
                dp[(r, c)] = max(dp[(r, c)], dfs(newRow, newCol, matrix[r][c]) + 1)

            return dp[(r, c)]

        res = 0
        for r in range(row):
            for c in range(col):
                res = max(res, dfs(r, c, -1))

        return res

#T: O(M * N)
#S: O(M * N)

            