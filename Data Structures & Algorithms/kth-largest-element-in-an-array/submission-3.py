class Solution:
    def findKthLargest(self, nums: List[int], k: int) -> int:
        heapq.heapify_max(nums)

        while k:
            res = heapq.heappop_max(nums)
            k -= 1

        return res