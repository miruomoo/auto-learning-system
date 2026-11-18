class Solution:
    def networkDelayTime(self, times: List[List[int]], n: int, k: int) -> int:
        graph = defaultdict(list)

        for u, v, t in times:
            graph[u].append([t, v])

        visit = set()
        minHeap = [[0, k]]
        res = 0

        while minHeap:
            time, node = heapq.heappop(minHeap)
            if node in visit:
                continue
            visit.add(node)
            res = time
            for neiTime, nei in graph[node]:
                heapq.heappush(minHeap, [neiTime + time, nei])

        print(len(visit))
        return res if len(visit) == n else -1
