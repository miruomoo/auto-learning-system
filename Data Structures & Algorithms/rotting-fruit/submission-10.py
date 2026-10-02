class Solution:
    def orangesRotting(self, grid: List[List[int]]) -> int:
        rows, cols = len(grid), len(grid[0])
        q = deque()
        fresh = 0
        res = 0
        
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == 1:
                    fresh += 1
                if grid[r][c] == 2:
                    q.append((r, c))

        dirs = [[0, 1], [1, 0], [0, -1], [-1, 0]]

        while fresh and q:
            for _ in range(len(q)):
                row, col = q.popleft()
                for dr, dc in dirs:
                    newRow, newCol = row + dr, col + dc
                    if newRow < 0 or newCol < 0 or newRow == rows or newCol == cols or grid[newRow][newCol] != 1:
                        continue
                    fresh -= 1
                    grid[newRow][newCol] = 2
                    q.append((newRow, newCol))

            res += 1

        return res if fresh == 0 else -1
                    
                    