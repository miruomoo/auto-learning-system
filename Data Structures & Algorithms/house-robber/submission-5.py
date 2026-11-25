class Solution:
    def rob(self, nums: List[int]) -> int:
        dp = {}
        
        def dfs(i, curSum):
            if i >= len(nums):
                return curSum

            if (i, curSum) in dp:
                return dp[(i, curSum)]

            dp[(i, curSum)] = max(dfs(i + 1, curSum), dfs(i + 2, curSum + nums[i]))

            return dp[(i, curSum)]

        return dfs(0, 0)