class Solution:
    def subsets(self, nums: List[int]) -> List[List[int]]:
        res = []

        def dfs(i, curSet):
            if i == len(nums):
                res.append(curSet.copy())
                return

            curSet.append(nums[i])
            dfs(i + 1, curSet)
            curSet.pop()
            dfs(i + 1, curSet)

        dfs(0, [])
        return res