class Solution:
    def permute(self, nums: List[int]) -> List[List[int]]:
        res = []
        
        def dfs(taken, perm):
            if len(perm) == len(nums):
                res.append(perm.copy())
                return

            for i in range(len(taken)):
                if taken[i]:
                    continue
                perm.append(nums[i])
                taken[i] = True
                dfs(taken, perm)
                taken[i] = False
                perm.pop()
                
            return

        dfs([False] * len(nums), [])
        return res
