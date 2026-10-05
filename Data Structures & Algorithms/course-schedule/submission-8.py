class Solution:
    def canFinish(self, numCourses: int, prerequisites: List[List[int]]) -> bool:
        graph = defaultdict(list)

        for c, p in prerequisites:
            graph[c].append(p)

        path = set() # current path
        visit = set() # completed paths
        
        def dfs(c):
            if c in path:
                return False
            if c in visit:
                return True

            path.add(c)
            for p in graph[c]:
                if not dfs(p):
                    return False
            path.remove(c)
            visit.add(c)
            return True

        for num in range(numCourses):
            if not dfs(num):
                return False

        return True