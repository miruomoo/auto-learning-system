class Solution:
    def largestRectangleArea(self, heights: List[int]) -> int:
        stack = [] # index, height
        res = 0

        for i, h in enumerate(heights):
            start = i
            
            while stack and h < stack[-1][1]:
                stackI, stackH = stack.pop()
                start = stackI
                area = stackH * (i - stackI)
                res = max(area, res)

            stack.append([start, h])

        for i, h in stack:
            res = max(res, h * (len(heights) - i))

        return res
