class Solution:
    def orangesRotting(self, grid: List[List[int]]) -> int:
        rows = len(grid)
        cols = len(grid[0])
        q = deque()
        fresh = 0
        res = 0

        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == 2:
                    q.append((r, c))
                elif grid[r][c] == 1:
                    fresh += 1

        while q:
            oldFresh = fresh
            for _ in range(len(q)):
                row, col = q.popleft()
                dirs = [[0, 1], [0, -1], [1, 0], [-1, 0]]
                for dr, dc in dirs:
                    newRow, newCol = row + dr, col + dc
                    if newRow < 0 or newCol < 0 or newRow == rows or newCol == cols or grid[newRow][newCol] != 1:
                        continue
                    grid[newRow][newCol] = 2
                    fresh -= 1
                    q.append((newRow, newCol))
            if oldFresh != fresh:
                res += 1

        return res if fresh == 0 else -1
