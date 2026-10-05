class Solution:
    def permute(self, nums: List[int]) -> List[List[int]]:
        res = []

        def dfs(used, perm):
            if len(perm) == len(nums):
                res.append(perm.copy())
                return
            
            for i in range(len(nums)):
                if not used[i]:
                    perm.append(nums[i])
                    used[i] = True
                    dfs(used, perm)
                    perm.pop()
                    used[i] = False

        dfs([False] * len(nums), [])
        return res

            

            
