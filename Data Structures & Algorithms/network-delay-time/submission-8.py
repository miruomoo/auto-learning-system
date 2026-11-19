class Solution:
    def networkDelayTime(self, times: List[List[int]], n: int, k: int) -> int:
        graph = defaultdict(list)
        for u, v, t in times:
            graph[u].append([t, v])

        minHeap = [[0, k]]
        visit = set()
        res = 0

        while minHeap:
            time, node = heapq.heappop(minHeap)
            if node in visit:
                continue
            visit.add(node)
            res = time

            for neiTime, neiNode in graph[node]:
                if neiNode not in visit:
                    heapq.heappush(minHeap, [neiTime + time, neiNode])

        return res if len(visit) == n else -1
