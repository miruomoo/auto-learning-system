class Solution:
    def isValid(self, s: str) -> bool:
        bmap = {
            "}":"{",
            ")":"(",
            "]":"["
        }

        stack = []

        for b in s:
            if stack and b in bmap.keys() and stack[-1] == bmap[b]:
                stack.pop()
            elif b in bmap.values():
                stack.append(b)
            else:
                return False

        return True if not stack else False
            