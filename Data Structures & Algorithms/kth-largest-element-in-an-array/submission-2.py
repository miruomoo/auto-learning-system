class Solution:
    def findKthLargest(self, nums: List[int], k: int) -> int:
        minHeap = nums
        heapq.heapify_max(minHeap)

        while k:
            res = heapq.heappop_max(minHeap)
            k -= 1
        
        return res