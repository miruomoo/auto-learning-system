class Solution:
    def networkDelayTime(self, times: List[List[int]], n: int, k: int) -> int:
        graph = collections.defaultdict(list)

        for start, end, time in times:
            graph[start].append([time, end])

        minHeap = [[0, k]]
        res = 0
        visit = set()

        while minHeap:
            time, end = heapq.heappop(minHeap)
            if end in visit:
                continue
            visit.add(end)
            res = time

            for nei in graph[end]:
                newTime, newEnd = nei
                if newEnd not in visit:
                    heapq.heappush(minHeap, [newTime + time, newEnd])

        return res if len(visit) == n else -1