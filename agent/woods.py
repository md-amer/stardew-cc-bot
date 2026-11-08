"""Secret Woods (wiki): entrance NW Cindersap Forest, blocked by a Large Log (Steel Axe+).
Inside: seasonal forage (Fiddlehead Fern in summer -> Chef's; Morel/Common Mushroom/Red Mushroom),
6 Large Stumps that regrow daily (12 Hardwood/day -> Construction), Woodskip (fishing)."""
import time
import sv, act, town, farming, needs

def _prog():
    import play_day; return play_day.prog()

def _save(p):
    import play_day; play_day.save_prog(p)

def open_log():
    p = _prog()
    if p.get("woods_open"): return True
    import projects
    if projects.axe_tier() < 2: return False
    act.goto("Forest")
    a = sv.call("around", r=120)
    logs = [c for c in a["clumps"] if c.get("id") == 602]
    if not logs:
        act.log("woods: no Large Log in Forest (already gone?)")
        p = _prog(); p["woods_open"] = True; _save(p); return True
    c = min(logs, key=lambda c: c["x"] + c["y"])          # the NW one
    act.log(f"woods: chopping Large Log at {(c['x'], c['y'])}")
    for stand in ((c["x"] + 2, c["y"]), (c["x"] + 2, c["y"] + 1), (c["x"], c["y"] + 2), (c["x"] + 1, c["y"] + 2)):
        if act.walk(*stand) == "arrived": break
    for _ in range(30):
        a2 = sv.call("around", r=5)
        if not any(cc["x"] == c["x"] and cc["y"] == c["y"] for cc in a2["clumps"]): break
        _, me = act.here()
        tx = c["x"] + 1 if me[0] > c["x"] + 1 else c["x"]
        ty = c["y"] + 1 if me[1] > c["y"] + 1 else c["y"]
        act.use(tx, ty, tool="Axe")
        if sv.state()["player"]["stamina"] < 15: break
    farming.collect_debris(r=4)
    a2 = sv.call("around", r=5)
    if not any(cc["x"] == c["x"] and cc["y"] == c["y"] for cc in a2["clumps"]):
        p = _prog(); p["woods_open"] = True; _save(p); act.log("woods: Large Log cleared, Secret Woods open")
        return True
    act.log("woods: log still there")
    return False

def visit():
    s = sv.state()
    q = needs.quota()
    want = {"Fiddlehead Fern", "Morel", "Common Mushroom", "Red Mushroom", "Hardwood", "Woodskip"} & set(q)
    if not want or s["time"] >= 1700 or s["player"]["stamina"] < 50:
        return
    p = _prog()
    if p.get("woods_day") == [s["season"], s["day"]]: return
    if not open_log(): return
    p = _prog(); p["woods_day"] = [s["season"], s["day"]]; _save(p)
    act.goto("Woods")
    n = town.forage_nearby(r=60, max_items=20)
    act.log(f"woods: foraged {n}")
    if "Hardwood" in q:
        need = q["Hardwood"] - _prog().get("chest", {}).get("Hardwood", 0)
        a = sv.call("around", r=80)
        for c in sorted((c for c in a["clumps"] if c.get("id") == 600), key=lambda c: c["y"]):
            if sum(i["stack"] for i in act.inv() if i["name"] == "Hardwood") >= need: break
            if sv.state()["player"]["stamina"] < 30: break
            if act.walk(c["x"], c["y"] + 2) != "arrived" and act.walk(c["x"] - 1, c["y"]) != "arrived":
                continue
            for _ in range(15):
                a2 = sv.call("around", r=4)
                if not any(cc["x"] == c["x"] and cc["y"] == c["y"] for cc in a2["clumps"]): break
                act.use(c["x"], c["y"] + 1, tool="Axe")
            farming.collect_debris(r=4)
        act.log(f"woods: Hardwood held {sum(i['stack'] for i in act.inv() if i['name'] == 'Hardwood')}")
