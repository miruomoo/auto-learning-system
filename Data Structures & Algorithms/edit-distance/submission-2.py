class Solution:
    def minDistance(self, word1: str, word2: str) -> int:
        dp = {}

        def dfs(i, j):
            if i == len(word1):
                return len(word2) - j
            if j == len(word2):
                return len(word1) - i

            if (i, j) in dp:
                return dp[(i, j)]

            if word1[i] == word2[j]:
                # skip
                dp[(i, j)] = dfs(i + 1, j + 1)
            else:
                # add / remove
                res = min(dfs(i, j + 1), dfs(i + 1, j))
                # replace
                dp[(i, j)] = min(res, dfs(i + 1, j + 1)) + 1

            return dp[(i, j)]

        return dfs(0, 0)