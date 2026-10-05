class Solution:
    def maxProfit(self, prices: List[int]) -> int:
        dp = {}

        def dfs(i, canBuy):
            if i >= len(prices):
                return 0

            if (i, canBuy) in dp:
                return dp[(i, canBuy)]

            skip = dfs(i + 1, canBuy)
            if canBuy:
                dp[(i, canBuy)] = max(skip, dfs(i + 1, not canBuy) - prices[i])
            else:
                dp[(i, canBuy)] = max(skip, dfs(i + 2, not canBuy) + prices[i])

            return dp[(i, canBuy)]

        return dfs(0, True)