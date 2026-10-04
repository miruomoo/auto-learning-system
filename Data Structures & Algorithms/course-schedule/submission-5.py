class Solution:
    def canFinish(self, numCourses: int, prerequisites: List[List[int]]) -> bool:
        graph = defaultdict(list)

        for c, p in prerequisites:
            graph[c].append(p)

        visit = set()

        def dfs(c):
            if c in visit:
                return False
            if graph[course] == []:
                return True
            
            visit.add(c)

            for nei in graph[c]:
                if not dfs(nei):
                    return False

            visit.remove(c)
            graph[c] = []
            return True

        for course in range(numCourses):
            if not dfs(course):
                return False
        return True
