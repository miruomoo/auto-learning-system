class Solution:
    def maxProduct(self, nums: List[int]) -> int:
        curMin = 1
        curMax = 1
        res = max(nums)

        for n in nums:

            temp = curMin
            curMin = min(n, curMin * n, curMax * n)
            curMax = max(n, curMax * n, temp * n)

            res = max(curMin, curMax, res)

        return res