"""
# Definition for a Node.
class Node:
    def __init__(self, val = 0, neighbors = None):
        self.val = val
        self.neighbors = neighbors if neighbors is not None else []
"""

class Solution:
    def cloneGraph(self, node: Optional['Node']) -> Optional['Node']:
        if not node:
            return None

        graph = {}

        def dfs(node):
            if node in graph:
                return graph[node]

            graph[node] = Node(node.val)
            for nei in node.neighbors:
                graph[node].neighbors.append(dfs(nei))

            return graph[node]

        return dfs(node)