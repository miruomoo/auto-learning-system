class Solution:
    def canFinish(self, numCourses: int, prerequisites: List[List[int]]) -> bool:
        graph = defaultdict(list)

        for c, p in prerequisites:
            graph[c].append(p)

        visit = set()
        path = set()

        def dfs(course):
            if course in path:
                return False

            if course in visit:
                return True

            path.add(course)

            for nei in graph[course]:
                if not dfs(nei):
                    return False

            path.remove(course)
            visit.add(course)

            return True

        for i in range(numCourses):
            if not dfs(i):
                return False

        return True