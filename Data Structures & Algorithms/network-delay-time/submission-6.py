class Solution:
    def networkDelayTime(self, times: List[List[int]], n: int, k: int) -> int:
        graph = defaultdict(list)

        for node, nei, time in times:
            graph[node].append([time, nei])

        minHeap = [[0, k]]
        visit = set()
        res = 0

        while minHeap:
            time, node = heapq.heappop(minHeap)
            if node in visit:
                continue
            visit.add(node)
            res = time
            for neiTime, nei in graph[node]:
                heapq.heappush(minHeap, [neiTime + time, nei])

        return res if len(visit) == n else -1

