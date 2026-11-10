# Definition for singly-linked list.
# class ListNode:
#     def __init__(self, val=0, next=None):
#         self.val = val
#         self.next = next

class Solution:
    def reorderList(self, head: Optional[ListNode]) -> None:
        # find the middle and seperate the lists
        slow = head
        fast = head
        
        while fast.next and fast.next.next:
            slow = slow.next
            fast = fast.next.next

        l2 = slow.next
        slow.next = None
        # reverse the second half
        prev = None
        cur = l2

        while cur:
            temp = cur.next
            cur.next = prev
            prev = cur
            cur = temp
        l2 = prev
        # merge the two lists
        l1 = head
        while l2:
            temp1 = l1.next
            temp2 = l2.next
            l1.next = l2
            l2.next = temp1
            l1 = temp1
            l2 = temp2