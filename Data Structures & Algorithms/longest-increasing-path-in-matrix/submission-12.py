class Solution:
    def longestIncreasingPath(self, matrix: List[List[int]]) -> int:
        rows, cols = len(matrix), len(matrix[0])
        dp = {}

        def dfs(r, c):
            if (r, c) in dp:
                return dp[(r, c)]

            dirs = [[0, 1], [1, 0], [0, -1], [-1, 0]]
            dp[(r, c)] = 1
            for dr, dc in dirs:
                newRow, newCol = dr + r, dc + c
                if newRow < 0 or newCol < 0 or newRow >= rows or newCol >= cols or matrix[newRow][newCol] <= matrix[r][c]:
                    continue
                dp[(r, c)] = max(dp[(r, c)], dfs(newRow, newCol) + 1)

            return dp[(r, c)]

        res = 1
        for r in range(rows):
            for c in range(cols):
                res = max(res, dfs(r, c))

        return res