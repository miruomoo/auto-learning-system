class Solution:
    def orangesRotting(self, grid: List[List[int]]) -> int:
        rows, cols = len(grid), len(grid[0])
        fresh = 0
        q = deque()

        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == 1:
                    fresh += 1
                if grid[r][c] == 2:
                    q.append((r, c))

        res = 0
        dirs = [[0, 1], [1, 0], [-1, 0], [0, -1]]
        while q and fresh:
            for _ in range(len(q)):
                r, c = q.popleft()

                for dr, dc in dirs:
                    newRow, newCol = dr + r, dc + c
                    if newRow < 0 or newCol < 0 or newRow == rows or newCol == cols or grid[newRow][newCol] != 1:
                        continue
                    q.append((newRow, newCol))
                    grid[newRow][newCol] = 2
                    fresh -= 1
            res += 1

        return res if fresh == 0 else -1

                

