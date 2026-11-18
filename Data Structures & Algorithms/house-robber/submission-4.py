class Solution:
    def rob(self, nums: List[int]) -> int:
        dp = {}

        def dfs(i):
            if i >= len(nums):
                return 0

            if i in dp:
                return dp[i]

            dp[i] = max(dfs(i + 1), dfs(i + 2) + nums[i])

            return dp[i]

        return dfs(0)

#T: O(N)
#S: O(N)