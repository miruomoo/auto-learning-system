class Solution:
    def longestIncreasingPath(self, matrix: List[List[int]]) -> int:
        rows = len(matrix)
        cols = len(matrix[0])

        dp = {} # (row, col) -> curLength

        def dfs(row, col, prev):
            if row < 0 or col < 0 or row == rows or col == cols or prev >= matrix[row][col]:
                return 0
            
            if (row, col) in dp:
                return dp[(row, col)]

            dirs = [[0, 1], [1, 0], [-1, 0], [0, -1]]
            res = 1
            for dr, dc in dirs:
                res = max(res, dfs(row + dr, col + dc, matrix[row][col]) + 1)

            dp[(row, col)] = res
            return res

        ans = 1
        for r in range(rows):
            for c in range(cols):
                ans = max(ans, dfs(r, c, -1))

        return ans
