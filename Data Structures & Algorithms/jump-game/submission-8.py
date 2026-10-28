class Solution:
    def canJump(self, nums: List[int]) -> bool:
        target = len(nums) - 1
        i = len(nums) - 1

        for i in range(len(nums) - 1, -1, -1):
            if nums[i] + i >= target:
                target = i
        
        return True if target == 0 else False

#T: O(n)
#S: O(n)