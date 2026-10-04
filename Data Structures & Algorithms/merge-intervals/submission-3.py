class Solution:
    def merge(self, intervals: List[List[int]]) -> List[List[int]]:
        intervals.sort()

        res = [intervals[0]]

        for start, end in intervals[1:]:
            if start > res[-1][1]:
                res.append([start, end])
            elif start <= res[-1][1]:
                res[-1][1] = max(end, res[-1][1])

        return res
