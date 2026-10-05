class Solution:
    def maxProduct(self, nums: List[int]) -> int:
        res = max(nums)
        curMax = 1
        curMin = 1

        for n in nums:

            temp = curMax
            curMax = max(n, curMax * n, curMin * n)
            curMin = min(n, temp * n, curMin * n)

            res = max(res, curMax, curMin)

        return res