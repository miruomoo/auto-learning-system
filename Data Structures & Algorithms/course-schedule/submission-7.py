class Solution:
    def canFinish(self, numCourses: int, prerequisites: List[List[int]]) -> bool:
        graph = defaultdict(list)

        for c, p in prerequisites:
            graph[c].append(p)

        path = set()
        visit = set()

        def dfs(c):
            if c in path:
                return False
            if c in visit:
                return True
            
            path.add(c)

            for nei in graph[c]:
                if not dfs(nei):
                    return False

            path.remove(c)
            visit.add(c)
            return True

        for course in range(numCourses):
            if not dfs(course):
                return False
        return True
