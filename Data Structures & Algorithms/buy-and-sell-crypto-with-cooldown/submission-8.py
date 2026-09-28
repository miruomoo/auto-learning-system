class Solution:
    def maxProfit(self, prices: List[int]) -> int:
        dp = {}

        def dfs(i, buy):
            if i >= len(prices):
                return 0

            if (i, buy) in dp:
                return dp[(i, buy)]

            skip = dfs(i + 1, buy)
            if buy:
                dp[(i, buy)] = max(dfs(i + 1, not buy) - prices[i], skip)
            else:
                dp[(i, buy)] = max(dfs(i + 2, not buy) + prices[i], skip)

            return dp[(i, buy)]

        return dfs(0, True)