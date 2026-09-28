class Solution:
    def isValid(self, s: str) -> bool:
        pmap = {
            ")":"(",
            "]":"[",
            "}":"{"
        }
        stack = []
        for c in s:
            if c in pmap.values():
                stack.append(c)
            elif stack and stack[-1] == pmap[c]:
                stack.pop()
            else:
                return False

        return True if not stack else False