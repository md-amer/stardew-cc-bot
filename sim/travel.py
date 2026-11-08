"""Walking times between places, from the game's own maps (sim/data/maps/*.json, tools/mapdump).
Graph: warp tiles + arrival tiles; inside a map, BFS over passable Back-layer tiles (Buildings layer blocks,
Passable property allowed, water blocked). Objects/trees/debris not included (paths slightly optimistic).
Speed: running 5 x 0.066 px/ms = 0.33 px/ms -> 64/0.33 ms per tile = 194 ms; 700 ms per game minute
-> 3.61 tiles per game minute (Farmer.getMovementSpeed, Game1.realMilliSecondsPerGameMinute).
Door hours come from LockedDoorWarp actions (e.g. SeedShop 900 2100).
"""
import json, os, heapq, collections, re
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, "data", "maps")
TILES_PER_MIN = 3.61
MAPS = {}
for f in os.listdir(MD):
    d = json.load(open(os.path.join(MD, f)))
    d["rows"] = d["grid"].split("\n")
    MAPS[d["name"]] = d
ALIAS = {"CommunityCenter_Ruins": "CommunityCenter"}

# extra links not in map data: farmhouse door (Farm 64,15 <-> FarmHouse 3,11), CC door handled by WarpCommunityCenter
EXTRA = [("Farm", 64, 15, "FarmHouse", 3, 11), ("FarmHouse", 3, 11, "Farm", 64, 16),
         ("Town", 52, 19, "CommunityCenter_Ruins", 32, 23), ("CommunityCenter_Ruins", 32, 23, "Town", 52, 20)]
HOURS = {}


def links():
    L = []
    for m, d in MAPS.items():
        for w in d["warps"]:
            x, y = int(w["x"]), int(w["y"])
            if w["kind"] == "edge":
                to = w["to"]
                if to not in MAPS and ALIAS.get(to) not in MAPS: continue
                L.append((m, x, y, to, int(w["tx"]), int(w["ty"])))
            else:
                p = w["action"].split()
                if p[0] in ("LockedDoorWarp", "Warp") and len(p) >= 4 and p[3] in MAPS:
                    L.append((m, x, y, p[3], int(p[1]), int(p[2])))
                    if p[0] == "LockedDoorWarp" and len(p) >= 6:
                        HOURS[p[3]] = (int(p[4]), int(p[5]))
    return L + EXTRA


LINKS = links()


def clamp(m, x, y):
    d = MAPS[m]
    return max(0, min(d["W"] - 1, x)), max(0, min(d["H"] - 1, y))


def bfs(m, sx, sy):
    d = MAPS[m]; rows = d["rows"]; W, H = d["W"], d["H"]
    sx, sy = clamp(m, sx, sy)
    dist = {(sx, sy): 0}; q = collections.deque([(sx, sy)])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in dist and ny < len(rows) and nx < len(rows[ny]) and rows[ny][nx] == ".":
                dist[(nx, ny)] = dist[(x, y)] + 1; q.append((nx, ny))
    return dist


@lru_cache(None)
def _bfs(m, x, y): return bfs(m, x, y)


def near(dist, x, y, m):
    """distance to tile (x,y), or to the nearest reached tile within 3 (warp tiles are often blocked)."""
    x, y = clamp(m, x, y)
    best = None
    for r in range(0, 4):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                v = dist.get((x + dx, y + dy))
                if v is not None and (best is None or v + r < best): best = v + r
        if best is not None: return best
    return None


def route(a, b):
    """a, b = (map, x, y). Returns tiles walked (Dijkstra over warps)."""
    start = (a[0], a[1], a[2])
    pq = [(0, start)]; seen = {}
    while pq:
        c, (m, x, y) = heapq.heappop(pq)
        if (m, x, y) in seen: continue
        seen[(m, x, y)] = c
        if m == "__END__": return c
        if m not in MAPS: continue
        dist = _bfs(m, x, y)
        if m == b[0]:
            v = near(dist, b[1], b[2], m)
            if v is not None: heapq.heappush(pq, (c + v, ("__END__", 0, 0)))
        for (fm, fx, fy, tm, tx, ty) in LINKS:
            if fm != m: continue
            v = near(dist, fx, fy, m)
            if v is None: continue
            heapq.heappush(pq, (c + v + 1, (tm, tx, ty)))
    return None


PLACES = {
    "bed": ("FarmHouse", 9, 9), "farm": ("Farm", 60, 25), "shipbin": ("Farm", 71, 14),
    "pierre": ("SeedShop", 4, 19), "clint": ("Blacksmith", 3, 15), "robin": ("ScienceHouse", 8, 18),
    "marnie": ("AnimalShop", 12, 16), "willy": ("FishShop", 5, 6), "gus": ("Saloon", 10, 18),
    "cc": ("CommunityCenter_Ruins", 32, 14), "mine": ("Mine", 18, 13), "beach": ("Beach", 30, 30),
    "mountain_lake": ("Mountain", 50, 26), "forest_river": ("Forest", 60, 50), "cart": ("Forest", 88, 101),
    "town_river": ("Town", 100, 95), "backwoods": ("Backwoods", 25, 25), "busstop": ("BusStop", 20, 23),
    "woods": ("Woods", 30, 15), "museum": ("ArchaeologyHouse", 5, 9),
}


def snap(pl):
    m, x, y = pl; rows = MAPS[m]["rows"]
    for r in range(0, 15):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                yy, xx = y + dy, x + dx
                if 0 <= yy < len(rows) and 0 <= xx < len(rows[yy]) and rows[yy][xx] == ".": return (m, xx, yy)
    return pl


@lru_cache(None)
def minutes(a, b, factor=1.0):
    t = route(snap(PLACES[a]), snap(PLACES[b]))
    return None if t is None else t / TILES_PER_MIN * factor


if __name__ == "__main__":
    names = list(PLACES)
    print("game minutes walking (human run speed):")
    for a in ("bed", "farm"):
        print(" ", a, {b: (round(minutes(a, b)) if minutes(a, b) is not None else None) for b in names if b != a})
    print("door hours:", HOURS)


FALLBACK = {"mine": ("mountain_lake", 8), "cart": ("forest_river", -15)}   # walk-grid gaps (decoration tiles)


def matrix():
    names = list(PLACES)
    M = {}
    for a in names:
        for b in names:
            if a == b: M[(a, b)] = 0; continue
            v = minutes(a, b)
            if v is None:
                fa = FALLBACK.get(a, (a, 0)); fb = FALLBACK.get(b, (b, 0))
                v = minutes(fa[0], fb[0]) if fa[0] != fb[0] else 0
                v = max(5, (v or 30) + fa[1] + fb[1])
            M[(a, b)] = round(v, 1)
    json.dump({f"{a}|{b}": v for (a, b), v in M.items()}, open(os.path.join(HERE, "data", "travel.json"), "w"))
    return M
