class Solution:
    def orangesRotting(self, grid: List[List[int]]) -> int:
        rows, cols = len(grid), len(grid[0])
        fresh = 0
        q = deque()
        time = 0

        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == 1:
                    fresh += 1
                if grid[r][c] == 2:
                    q.append((r, c))

        dirs = [[0, 1], [1, 0], [-1, 0], [0, -1]]
        while fresh > 0 and q:
            for _ in range(len(q)):
                r, c = q.popleft()
                
                for dr, dc in dirs:
                    newRow, newCol = r + dr, c + dc
                    if newRow < 0 or newRow == rows or newCol < 0 or newCol == cols or grid[newRow][newCol] != 1:
                        continue
                    grid[newRow][newCol] = 2
                    fresh -= 1
                    q.append((newRow, newCol))
            time += 1

        return time if fresh == 0 else -1
                


            