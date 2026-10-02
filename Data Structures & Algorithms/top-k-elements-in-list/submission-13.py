class Solution:
    def topKFrequent(self, nums: List[int], k: int) -> List[int]:
        count = Counter(nums)
        buckets = [[] for i in range(len(nums) + 1)]
        res = []

        for key, val in count.items():
            buckets[val].append(key)

        for i in range(len(nums), -1, -1):
            for n in buckets[i]:
                res.append(n)
            if len(res) == k:
                return res

        