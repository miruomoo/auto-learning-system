class Solution:
    def carFleet(self, target: int, position: List[int], speed: List[int]) -> int:
        cars = [[p, s] for p, s in zip(position, speed)]
        stack = [] # time to reach target

        for p, s in sorted(cars)[::-1]:
            stack.append((target - p) / s)
            if stack and len(stack) >= 2:
                if stack[-1] <= stack[-2]:
                    stack.pop()

        return len(stack)

