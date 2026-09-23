class Solution:
    def carFleet(self, target: int, position: List[int], speed: List[int]) -> int:
        stack = []

        cars = [[p, s] for p, s in zip(position, speed)]

        for p, s in sorted(cars)[::-1]:
            stack.append((target - p) / s) # how long it will take
            # fleet is formed
            if len(stack) >= 2 and stack[-1] <= stack[-2]:
                stack.pop()

        return len(stack)

