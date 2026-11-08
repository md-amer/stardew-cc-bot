"""For every bundle fish: best (location, area, season, time, weather) per cast, at fishing level 2/6.
Expected game minutes = casts x 20 (our bot's measured median per cast)."""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gamedata as g, fishsim as fs

SPOTS = [("Mountain", None), ("Forest", "River"), ("Forest", "Lake"), ("Town", "River"), ("Beach", "Default"),
         ("Woods", None), ("Desert", "TopPond"), ("Backwoods", None), ("Sewer", None)]
need = sorted({i["name"] for b in g.bundles() if b["room"] == "Fish Tank" or b["name"] in ("Field Research",)
               for i in b["items"] if g.id_by_name().get(i["name"]) in fs.FISH and not fs.FISH[g.id_by_name()[i["name"]]]["trap"]})
TIMES = list(range(600, 2600, 100))
res = {}
for level in (2, 6):
    best = {f: [] for f in need}
    for loc, area in SPOTS:
        for season in g.SEASONS:
            for rain in (False, True):
                for t in TIMES:
                    d = fs.dist(loc, season, t, rain, level, 4, area, n=3000, seed=t)
                    for f in need:
                        if d.get(f, 0) > 0:
                            best[f].append((d[f], loc, area, season, t, "rain" if rain else "sun"))
    res[level] = {}
    for f in need:
        rows = sorted(best[f], reverse=True)
        if not rows:
            res[level][f] = None; continue
        p, loc, area, season, t, w = rows[0]
        seasons = sorted({r[3] for r in rows if r[0] > 0.02})
        res[level][f] = {"p": round(p, 3), "where": f"{loc}/{area or '-'}", "season": season, "time": t, "weather": w,
                         "casts": round(1 / p, 1), "game_min": round(20 / p), "ok_seasons": seasons}
json.dump(res, open(os.path.join(os.path.dirname(__file__), "fish_timetable.json"), "w"), indent=1)
for f in need:
    a, b = res[2][f], res[6][f]
    if not a: print(f"{f:18} NOT IN LOCATION DATA (code-driven or trap)"); continue
    print(f"{f:18} L2 p={a['p']:.3f} ~{a['game_min']:4d} min | L6 p={b['p']:.3f} ~{b['game_min']:4d} min | {b['where']:16} {b['season']:6} {b['time']} {b['weather']} | seasons {a['ok_seasons']}")
