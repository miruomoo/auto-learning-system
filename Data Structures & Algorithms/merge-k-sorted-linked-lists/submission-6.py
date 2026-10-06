# Definition for singly-linked list.
# class ListNode:
#     def __init__(self, val=0, next=None):
#         self.val = val
#         self.next = next

class Solution:    
    def mergeKLists(self, lists: List[Optional[ListNode]]) -> Optional[ListNode]:
        minHeap = []
        res = []
        counter = 0

        for l in lists:
            if l:
                heapq.heappush(minHeap, (l.val, counter, l))
                counter += 1

        res = ListNode(0)
        cur = res

        while minHeap:
            val, counter, node = heapq.heappop(minHeap)
            cur.next = node
            cur = cur.next
            if node.next:
                heapq.heappush(minHeap, (node.next.val, counter, node.next))
                counter += 1

        return res.next
            

