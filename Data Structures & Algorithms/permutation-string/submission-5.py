class Solution:
    def checkInclusion(self, s1: str, s2: str) -> bool:
        if len(s1) > len(s2):
            return False

        c1 = Counter(s1)
        c2 = collections.defaultdict(int)

        for i in range(len(s1)):
            c2[s2[i]] += 1

        l = 0
        for r in range(len(s1), len(s2)):
            if c1 == c2:
                return True
            c2[s2[r]] += 1
            c2[s2[l]] -= 1
            if c2[s2[l]] == 0:
                del c2[s2[l]]
            l += 1

        return c1 == c2