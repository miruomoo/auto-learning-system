class Solution:
    def largestRectangleArea(self, heights: List[int]) -> int:
        stack = [] # height, index
        res = 0

        for i, h in enumerate(heights):
            start = i
            while stack and stack[-1][0] > h:
                stackH, stackI = stack.pop()
                start = stackI
                area = stackH * (i - stackI)
                res = max(area, res)
            stack.append([h, start])

        for h, i in stack:
            res = max(res, h * (len(heights) - i))

        return res