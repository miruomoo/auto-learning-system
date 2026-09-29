class Solution:
    def networkDelayTime(self, times: List[List[int]], n: int, k: int) -> int:
        graph = defaultdict(list)
        for s, t, c in times:
            graph[s].append([c, t])

        minHeap = [[0, k]]
        visit = set()
        res = 0

        while minHeap:
            cost, tgt = heapq.heappop(minHeap)

            if tgt in visit:
                continue
            visit.add(tgt)
            res = cost

            for newC, newT in graph[tgt]:
                if newT not in visit:
                    heapq.heappush(minHeap, [newC + cost, newT])

        return res if len(visit) == n else -1