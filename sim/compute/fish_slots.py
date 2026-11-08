"""All usable fishing slots per bundle fish: best hour per (spot, season, weather) at level 4, depth 4."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamedata as g, fishsim as fs
SPOTS = [("Mountain", None), ("Forest", "River"), ("Forest", "Lake"), ("Town", "River"), ("Beach", "Default"),
         ("Woods", None), ("Desert", "TopPond"), ("Backwoods", None), ("UndergroundMine", None)]
need = {i["name"] for b in g.bundles() for i in b["items"]}
out = {}
for loc, area in SPOTS:
    for season in g.SEASONS:
        for rain in (False, True):
            best = {}
            for t in range(600, 2600, 100):
                d = fs.dist(loc, season, t, rain, 4, 4, area, n=2000, seed=t)
                for f, p in d.items():
                    if f in need and p > best.get(f, (0,))[0]: best[f] = (p, t)
            for f, (p, t) in best.items():
                if p >= 0.03:
                    out.setdefault(f, []).append({"loc": loc, "area": area, "season": season, "weather": "rain" if rain else "sun", "p": round(p, 3), "hour": t})
json.dump(out, open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "fish_slots.json"), "w"), indent=0)
print({k: len(v) for k, v in out.items()})
