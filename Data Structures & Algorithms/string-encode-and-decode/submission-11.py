class Solution:

    def encode(self, strs: List[str]) -> str:
        res = []
        for s in strs:
            res.append(str(len(s)))
            res.append("#")
            res.append(s)
        print("".join(res))
        return "".join(res)

    def decode(self, s: str) -> List[str]:
        res = []
        l = 0
        r = 0
        while r < len(s):
            if s[r] == "#":
                length = int(s[l:r])
                res.append(s[r + 1:r + length + 1])
                r += (length + 1)
                l = r
            else:
                r += 1

        return res
