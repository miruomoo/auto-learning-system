class LRUCache:

    def __init__(self, capacity: int):
        self.cap = capacity
        self.cache = {}
        self.l = ListNode(0, 0) # least frequent
        self.r = ListNode(0, 0) # most frequent
        self.l.next = self.r
        self.r.prev = self.l

    def remove(self, node) -> None:
        prev = node.prev
        nxt = node.next
        prev.next = nxt
        nxt.prev = prev
    
    def add(self, node):
        mru = self.r.prev
        mru.next = node
        self.r.prev = node
        node.next = self.r
        node.prev = mru

    def get(self, key: int) -> int:
        if key in self.cache:
            node = self.cache[key]
            self.remove(node)
            self.add(node)
            return node.val
        else:
            return -1

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            node = self.cache[key]
            self.remove(node)
        self.cache[key] = ListNode(key, value)
        self.add(self.cache[key])
        if len(self.cache) > self.cap:
            lru = self.l.next
            del self.cache[lru.key]
            self.remove(lru)



class ListNode:

    def __init__(self, key, val):
        self.key = key
        self.val = val
        self.next = None
        self.prev = None