class Solution:
    def longestIncreasingPath(self, matrix: List[List[int]]) -> int:
        rows, cols = len(matrix), len(matrix[0])

        dp = {}

        def dfs(r, c, prev):
            if r < 0 or r == rows or c < 0 or c == cols or prev >= matrix[r][c]:
                return 0

            if (r, c) in dp:
                return dp[(r, c)]

            dirs = [[0, 1], [1, 0], [0, -1], [-1, 0]]
            dp[(r, c)] = 0
            for dr, dc in dirs:
                newRow, newCol = r + dr, c + dc
                dp[(r, c)] = max(dp[(r, c)], dfs(newRow, newCol, matrix[r][c]) + 1)

            return dp[(r, c)]

        res = 1
        for r in range(rows):
            for c in range(cols):
                res = max(res, dfs(r, c, -1))

        return res