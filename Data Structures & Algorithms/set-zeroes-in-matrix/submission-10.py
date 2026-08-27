class Solution:
    def setZeroes(self, matrix: List[List[int]]) -> None:
        rows = len(matrix)
        cols = len(matrix[0])

        for r in range(rows):
            for c in range(cols):
                if matrix[r][c] == 0:
                    for i in range(rows):
                        if matrix[i][c] != 0:
                            matrix[i][c] = "Z"
                    for i in range(cols):
                        if matrix[r][i] != 0:
                            matrix[r][i] = "Z"

        for r in range(rows):
            for c in range(cols):
                if matrix[r][c] == "Z":
                    matrix[r][c] = 0