class Solution:
    def change(self, amount: int, coins: List[int]) -> int:
        
        dp = {}

        def dfs(i, curSum):
            if curSum == amount:
                return 1
            if curSum > amount:
                return 0
            if i == len(coins):
                return 0

            if (i, curSum) in dp:
                return dp[(i, curSum)]

            dp[(i, curSum)] = dfs(i + 1, curSum) + dfs(i, curSum + coins[i])

            return dp[(i, curSum)]

        return dfs(0, 0)