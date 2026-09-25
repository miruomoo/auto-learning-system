class Solution:
    def checkInclusion(self, s1: str, s2: str) -> bool:
        if len(s1) > len(s2):
            return False

        count1 = defaultdict(int)
        count2 = defaultdict(int)

        for c in s1:
            count1[c] += 1

        for i in range(len(s1)):
            count2[s2[i]] += 1
        
        l = 0
        for r in range(len(s1), len(s2)):
            if count1 == count2:
                return True
            count2[s2[r]] += 1
            count2[s2[l]] -= 1
            if count2[s2[l]] == 0:
                del count2[s2[l]]
            l += 1

        return count1 == count2
