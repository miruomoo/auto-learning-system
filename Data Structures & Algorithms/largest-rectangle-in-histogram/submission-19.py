class Solution:
    def largestRectangleArea(self, heights: List[int]) -> int:
        heights = heights + [0]
        stack = [] # [stackH, stackI]
        res = 0

        for i, h in enumerate(heights):
            start = i
            while stack and stack[-1][0] > h:
                stackH, stackI = stack.pop()
                res = max(res, stackH * (i - stackI))
                start = stackI
            stack.append([h, start])

        return res
