class Solution:
    def isValid(self, s: str) -> bool:
        bmap = {
            "}":"{",
            "]":"[",
            ")":"("
        }

        stack = []

        for c in s:
            if c in bmap.values():
                stack.append(c)
            elif stack and stack[-1] == bmap[c]:
                stack.pop()
            else:
                return False

        return True if not stack else False
