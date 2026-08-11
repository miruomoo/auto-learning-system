class Solution:
    def minEatingSpeed(self, piles: List[int], h: int) -> int:
        l = 1
        r = max(piles)

        while l < r:
            mid = (l + r) // 2
            time = 0
            
            for p in piles:
                time += math.ceil(p / mid)

            if time > h:
                l = mid + 1
            else:
                r = mid

        return r