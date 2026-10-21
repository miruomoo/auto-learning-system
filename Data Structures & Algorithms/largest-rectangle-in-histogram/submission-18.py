class Solution:
    def largestRectangleArea(self, heights: List[int]) -> int:
        heights.append(0)
        stack = [] # (i, height)
        res = 0

        for i, h in enumerate(heights):
            start = i
            while stack and stack[-1][1] > h:
                stackI, stackH = stack.pop()
                area = stackH * (i - stackI)
                res = max(area, res)
                start = stackI

            stack.append([start, h])

        return res