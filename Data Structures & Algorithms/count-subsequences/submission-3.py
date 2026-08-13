class Solution:
    def numDistinct(self, s: str, t: str) -> int:
        if len(t) > len(s):
            return 0

        dp = {}

        def dfs(i, j):
            if i == len(s):
                return 1 if j == len(t) else 0
            if j == len(t):
                return 1

            if (i, j) in dp:
                return dp[(i, j)]

            if s[i] == t[j]:
                dp[(i, j)] = dfs(i + 1, j + 1) + dfs(i + 1, j)
            else:
                dp[(i, j)] = dfs(i + 1, j)

            return dp[(i, j)]

        return dfs(0, 0)