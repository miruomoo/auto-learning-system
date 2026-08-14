class Solution:
    def groupAnagrams(self, strs: List[str]) -> List[List[str]]:
        res = []
        hmap = collections.defaultdict(list)

        for s in strs:
            key = [0] * 26
            for c in s:
                key[(ord(c) - 97)] += 1
            hmap[tuple(key)].append(s)

        for val in hmap.values():
            res.append(val)

        return res