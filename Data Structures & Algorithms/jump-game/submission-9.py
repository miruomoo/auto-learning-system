class Solution:
    def canJump(self, nums: List[int]) -> bool:
        target = nums[-1]

        for i in range(len(nums) - 1, -1, -1):
            canJump = nums[i] + i
            if canJump >= target:
                target = i

        return True if target == 0 else False