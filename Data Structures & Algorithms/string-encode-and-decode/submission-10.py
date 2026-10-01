class Solution:

    def encode(self, strs: List[str]) -> str:
        res = []
        for s in strs:
            code = str(len(s)) + "#"
            res.append(code)
            res.append(s)
        return "".join(res)

    def decode(self, s: str) -> List[str]:
        res = []
        l = 0
        r = 0
        while r < len(s):
            if s[r] == "#":
                length = int(s[l:r])
                res.append(s[r + 1: r + length + 1])
                r += length + 1
                l = r
            r += 1

        return res
                

