class Solution:
    def networkDelayTime(self, times: List[List[int]], n: int, k: int) -> int:
        graph = defaultdict(list)

        for time in times:
            start, end, cost = time
            graph[start].append([cost, end])

        minHeap = [[0, k]]
        res = 0
        visit = set()

        while minHeap:
            cost, end = heapq.heappop(minHeap)
            if end in visit:
                continue
            visit.add(end)
            res = cost

            for nei in graph[end]:
                newCost, newEnd = nei
                if newEnd not in visit:
                    heapq.heappush(minHeap, [newCost + cost, newEnd])

        return res if len(visit) == n else -1