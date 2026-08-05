class Solution:
    def findTargetSumWays(self, nums: List[int], target: int) -> int:
        dp = collections.defaultdict(int)
        dp[0] = 1

        for num in nums:
            nextDp = collections.defaultdict(int)

            for i, count in dp.items():
                nextDp[i + num] += count
                nextDp[i - num] += count

            dp = nextDp

        return dp[target]