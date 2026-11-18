class Solution:
    def subsets(self, nums: List[int]) -> List[List[int]]:
        res = []
        
        def dfs(i, cur):
            if i == len(nums):
                res.append(cur.copy())
                return

            cur.append(nums[i])
            dfs(i + 1, cur)
            cur.pop()
            dfs(i + 1, cur)

            return

        dfs(0, [])
        return res
                