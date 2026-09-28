class Solution:
    def carFleet(self, target: int, position: List[int], speed: List[int]) -> int:
        cars = [[pos, speed] for pos, speed in zip(position, speed)]
        stack = []
        
        for p, s in sorted(cars)[::-1]:
            stack.append((target - p) / s) # time of car BEHIND
            while len(stack) >= 2 and stack[-1] <= stack[-2]:
                stack.pop()

        return len(stack)