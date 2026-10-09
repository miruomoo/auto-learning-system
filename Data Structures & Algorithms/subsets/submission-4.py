class Solution:
    def subsets(self, nums: List[int]) -> List[List[int]]:
        res = []

        def dfs(i, curSub):
            if i == len(nums):
                res.append(curSub.copy())
                return

            curSub.append(nums[i])
            dfs(i + 1, curSub)
            curSub.pop()
            dfs(i + 1, curSub)
            return

        dfs(0, [])
        return res

            