class Solution:
    def numIslands(self, grid: List[List[str]]) -> int:
        rows, cols = len(grid), len(grid[0])
        dirs = [[0, 1], [1, 0], [0, -1], [-1, 0]]

        def dfs(r, c):
            if r < 0 or c < 0 or r == rows or c == cols or grid[r][c] != "1":
                return
            
            grid[r][c] = "0"

            for dr, dc in dirs:
                dfs(r + dr, c + dc)

        res = 0
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == "1":
                    dfs(r, c)
                    res += 1

        return res