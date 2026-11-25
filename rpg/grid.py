"""Shared deterministic 4-neighbour geometry, independent of terminal IO."""
from collections import deque
DIRECTIONS = {'UP': (0,-1), 'DOWN': (0,1), 'LEFT': (-1,0), 'RIGHT': (1,0)}

def add(a,b): return a[0]+b[0], a[1]+b[1]
def distance(a,b): return abs(a[0]-b[0])+abs(a[1]-b[1])
def neighbors(p): return [add(p,d) for d in DIRECTIONS.values()]
def shortest(start, goal, allowed):
    """Return path excluding start, or None if unreachable."""
    queue=deque([start]); prev={start:None}
    while queue:
        p=queue.popleft()
        if goal(p):
            path=[]
            while prev[p] is not None: path.append(p); p=prev[p]
            return path[::-1]
        for n in neighbors(p):
            if n not in prev and allowed(n): prev[n]=p; queue.append(n)
    return None
