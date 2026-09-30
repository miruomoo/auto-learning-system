class Solution:
    def carFleet(self, target: int, position: List[int], speed: List[int]) -> int:
        cars = [[p, s] for p, s in zip(position, speed)]

        stack = [] # speeed

        for p, s in sorted(cars)[::-1]:
            stack.append((target - p) / s)
            while len(stack) >= 2 and stack[-2] >= stack[-1]:
                stack.pop()

        return len(stack)

