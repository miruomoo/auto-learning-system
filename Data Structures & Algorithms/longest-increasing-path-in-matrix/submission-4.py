class Solution:
    def longestIncreasingPath(self, matrix: List[List[int]]) -> int:
        rows = len(matrix)
        cols = len(matrix[0])
        
        dp = {} # r, c, -> length

        def dfs(r, c, prev):
            if r < 0 or c < 0 or r == rows or c == cols or matrix[r][c] <= prev:
                return 0
            
            if (r, c) in dp:
                return dp[(r, c)]

            dirs = [[0, 1], [1, 0], [-1, 0], [0, -1]]
            res = 1
            for dr, dc in dirs:
                res = max(res, dfs(r + dr, c + dc, matrix[r][c]) + 1)

            dp[(r, c)] = res
            return res

        ans = 1
        for r in range(rows):
            for c in range(cols):
                ans = max(ans, dfs(r, c, -1))

        return ans

        
