class Solution:
    def largestRectangleArea(self, heights: List[int]) -> int:
        stack = [] #[index, height]
        res = 0

        for i, h in enumerate(heights):
            start = i
            while stack and stack[-1][1] > h:
                stackI, stackH = stack.pop()
                area = stackH * (i - stackI)
                res = max(res, area)
                start = stackI
            stack.append([start, h])

        for i, h in stack:
            res = max(res, h * (len(heights) - i))

        return res