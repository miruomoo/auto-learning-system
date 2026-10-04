class Solution:
    def numIslands(self, grid: List[List[str]]) -> int:
        rows, cols = len(grid), len(grid[0])
        visit = set()
        dirs = [[0, 1], [1, 0], [0, -1], [-1, 0]]

        def dfs(r, c):
            if r < 0 or r == rows or c < 0 or c == cols or (r, c) in visit or grid[r][c] != "1":
                return

            visit.add((r, c))

            for dr, dc in dirs:
                newRow, newCol = dr + r, dc + c
                dfs(newRow, newCol)
        
        res = 0
        for r in range(rows):
            for c in range(cols):
                if (r, c) not in visit and grid[r][c] == "1":
                    dfs(r, c)
                    res += 1

        return res
                

            

            