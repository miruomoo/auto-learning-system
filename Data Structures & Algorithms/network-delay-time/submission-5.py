class Solution:
    def networkDelayTime(self, times: List[List[int]], n: int, k: int) -> int:
        graph = defaultdict(list)
        for src, tar, cost in times:
            graph[src].append([cost, tar])

        minHeap = [[0, k]]
        visit = set()
        res = 0

        while minHeap:
            cost, node = heapq.heappop(minHeap)

            if node in visit:
                continue

            visit.add(node)
            res = cost

            for c, nei in graph[node]:
                if nei in visit:
                    continue
                heapq.heappush(minHeap, [c + cost, nei])

        return res if len(visit) == n else -1
            