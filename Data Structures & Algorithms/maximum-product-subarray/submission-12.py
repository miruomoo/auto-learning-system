class Solution:
    def maxProduct(self, nums: List[int]) -> int:
        if len(nums) == 1:
            return nums[0]
        curMin = 0
        curMax = 0
        res = 0

        for num in nums:
            temp = curMin
            curMin = min(num * curMin, num * curMax, num)
            curMax = max(num * temp, num * curMax, num)

            res = max(res, curMin, curMax)

        return res