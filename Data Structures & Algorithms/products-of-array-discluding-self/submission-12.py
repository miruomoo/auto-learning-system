class Solution:
    def productExceptSelf(self, nums: List[int]) -> List[int]:
        prefix = [1] * len(nums)
        suffix = [1] * len(nums)
        res = []

        prefix[0] = nums[0]
        suffix[-1] = nums[-1]

        for i in range(1, len(nums)):
            prefix[i] = prefix[i - 1] * nums[i]

        for i in range(len(nums) - 2, -1, -1):
            suffix[i] = suffix[i + 1] * nums[i]

        for i in range(len(nums)):
            pre = prefix[i - 1] if i - 1 >= 0 else 1
            suf = suffix[i + 1] if i + 1 < len(nums) else 1
            res.append(pre * suf)

        return res