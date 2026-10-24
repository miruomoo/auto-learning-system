class Solution:
    def maxAreaOfIsland(self, grid: List[List[int]]) -> int:
        rows, cols = len(grid), len(grid[0])
        dirs = [[0, 1], [1, 0], [0, -1], [-1, 0]]
        res = 0

        def dfs(r, c):
            if r < 0 or c < 0 or r == rows or c == cols or grid[r][c] != 1:
                return 0
            
            grid[r][c] = 0
            curSum = 1

            for dr, dc in dirs:
                curSum += dfs(r + dr, c + dc)

            return curSum

        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == 1:
                    res = max(res, dfs(r, c))

        return res