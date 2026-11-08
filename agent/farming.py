"""Farm routines: clear debris, hoe, plant, water, harvest."""
import time
import sv, act

TOOL_FOR = {"Weeds": "Scythe", "Stone": "Pickaxe", "Twig": "Axe"}

def tile_info(r=25):
    a = sv.call("around", r=r)
    objs = {(o["x"], o["y"]): o for o in a["objects"]}
    feats = {(f["x"], f["y"]): f for f in a["features"]}
    blocked = set()
    for c in a["clumps"]:
        for dx in range(c["w"]):
            for dy in range(c["h"]):
                blocked.add((c["x"] + dx, c["y"] + dy))
    return objs, feats, blocked

import json as _json, os as _os
_BAD = _os.path.join(_os.path.dirname(__file__), "bad_tiles.json")

def _bad_tiles():
    try: return {tuple(t) for t in _json.load(open(_BAD))}
    except Exception: return set()

def _bad_tiles_add(t):
    b = _bad_tiles(); b.add(tuple(t)); _json.dump(sorted(b), open(_BAD, "w"))

def choose_plot(n, x0, x1, y0, y1, w=5):
    """Pick a w x ceil(n/w) block with the fewest obstacles (debris counts 1, trees/clumps forbidden)."""
    objs, feats, blocked = tile_info(r=40)
    blocked = blocked | _bad_tiles()               # tiles where the hoe failed before (paths, porch)
    grid = sv.call("grid")["rows"]
    h = -(-n // w)
    best = None
    for y in range(y0, y1 - h + 2):
        for x in range(x0, x1 - w + 2):
            cost, ok = 0, True
            for dy in range(h):
                for dx in range(w):
                    t = (x + dx, y + dy)
                    f = feats.get(t)
                    if t in blocked or (f and (f["type"] in ("Tree", "FruitTree") or "crop" in f)):
                        ok = False; break
                    if t in objs:
                        if objs[t]["name"] not in TOOL_FOR: ok = False; break
                        cost += 1
                    elif grid[t[1]][t[0]] == "#":
                        ok = False; break
                if not ok: break
            if ok:
                cost += 0.08 * (abs(x - 64) + abs(y - 20))      # prefer plots near the house/chest
            if ok and (best is None or cost < best[0]):
                best = (cost, x, y)
    if not best:
        raise RuntimeError("no plot found")
    _, x, y = best
    tiles = []
    for dy in range(h):
        row = [(x + dx, y + dy) for dx in range(w)]
        tiles += row if dy % 2 == 0 else row[::-1]
    return tiles[:n]

def clear(t):
    for _ in range(4):
        objs, feats, _ = tile_info(r=3)
        o = objs.get(t)
        if o and o["name"] in TOOL_FOR:
            act.use(*t, tool=TOOL_FOR[o["name"]]); continue
        f = feats.get(t)
        if f and f["type"] == "Grass":
            act.use(*t, tool="Scythe"); continue
        if f and f["type"] == "Tree":           # tree then stump: several axe swings (wood counts toward builds)
            for _ in range(15):
                act.use(*t, tool="Axe")
                if t not in tile_info(r=3)[1] or tile_info(r=3)[1][t]["type"] != "Tree": break
            collect_debris(r=3); continue
        return True
    return False

def approach(t):
    loc, me = act.here()
    if abs(me[0] - t[0]) + abs(me[1] - t[1]) == 1:
        return "arrived"
    return act.walk(*t, adjacent=True)

@act.slow
def hoe_plant_water(tiles, seed, fertilizer=None):
    done = 0
    for t in tiles:
        if approach(t) != "arrived":
            act.log(f"cannot reach {t}"); continue
        clear(t)
        _, feats, _ = tile_info(r=2)
        if feats.get(t, {}).get("type") != "HoeDirt":
            act.use(*t, tool="Hoe")
        _, feats, _ = tile_info(r=2)
        f = feats.get(t, {})
        if f.get("type") != "HoeDirt":
            act.log(f"hoe failed at {t}"); _bad_tiles_add(t); continue
        if fertilizer and "crop" not in f and not f.get("fertilizer") and act.slot_of(fertilizer) is not None:
            act.use(*t, tool=fertilizer)           # fertilizer goes on before the seed (wiki: Fertilizer)
        if "crop" not in f and act.slot_of(seed) is not None:
            act.use(*t, tool=seed)
            _, feats, _ = tile_info(r=2)
            if "crop" not in feats.get(t, {}):
                act.log(f"planting failed at {t}"); continue
        act.use(*t, tool="Watering Can")
        done += 1
    return done

def _plan_water_route(dry, start, g, feats):
    """Greedy stops covering the most dry tiles among the 8 neighbours (same rule as _water_pass), simulated."""
    dry = set(dry); me = start; route = []
    def standable(t):
        x, y = t
        return 0 <= y < len(g) and 0 <= x < len(g[0]) and (g[y][x] == "." or t in feats and feats[t]["type"] == "HoeDirt")
    while dry:
        best = None
        for t in dry:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    sp = (t[0] + dx, t[1] + dy)
                    if not standable(sp): continue
                    cov = [u for u in dry if u != sp and abs(u[0] - sp[0]) <= 1 and abs(u[1] - sp[1]) <= 1]
                    if not cov: continue
                    score = len(cov) * 4 - (abs(sp[0] - me[0]) + abs(sp[1] - me[1])) * 0.5
                    if best is None or score > best[0]: best = (score, sp, cov)
        if not best: break
        _, sp, cov = best
        route.append((sp, sorted(cov))); dry -= set(cov); me = sp
    return route

def water_seq(r=28, with_status=False):
    """Whole watering route as one mod-side batch (SeqTask): no Python round trip per tile, and the can
    animation is cancelled once the tile is wet (RShift+R+Delete, wiki Tools § Bugs). Refills planned in."""
    _, feats, _ = tile_info(r=r)
    dry = [t for t, f in feats.items() if f["type"] == "HoeDirt" and "crop" in f and not f["watered"] and not f.get("ready")]
    if not dry: return (0, {}) if with_status else 0
    slot = act.slot_of("Watering Can")
    if slot is None: return (0, {}) if with_status else 0
    if slot >= 12: slot = act.to_hotbar("Watering Can")
    g = sv.call("grid")["rows"]
    _, me = act.here()
    route = _plan_water_route(dry, me, g, feats)
    water = sv.call("water", r=40) or []
    w = can_water() or (40, 40)
    left, cap = w
    ops = []
    for sp, cov in route:
        ops.append({"op": "walk", "x": sp[0], "y": sp[1]})
        for u in cov:
            if left <= 0 and water:
                wt = min(water, key=lambda t: abs(t[0] - sp[0]) + abs(t[1] - sp[1]))
                ops += [{"op": "walk", "x": wt[0], "y": wt[1], "adjacent": True},
                        {"op": "use", "x": wt[0], "y": wt[1], "slot": slot},
                        {"op": "walk", "x": sp[0], "y": sp[1]}]
                left = cap
            ops.append({"op": "use", "x": u[0], "y": u[1], "slot": slot, "cancel": "water"})
            left -= 1
    r0 = sv.call("seq", ops=ops)
    for _ in range(3000):
        st = sv.call("seq_status")
        if st["status"] != "busy": break
        time.sleep(0.2)
    left_dry = dry_tiles(r)
    act.log(f"water_seq: {len(dry)} dry, {len(route)} stops, {len(ops)} ops -> {st}; still dry {len(left_dry)}")
    return (len(dry) - len(left_dry), st) if with_status else len(dry) - len(left_dry)
def water_all(r=20, _retry=True):
    """Water all dry crops; refill the can and retry if any stay dry."""
    try:
        import mining; mining.eat_if_tired(60)          # eat before a big watering run if low (food in pack)
    except Exception:
        pass
    if sv.state()["player"]["stamina"] < 20:
        act.log("water: too tired to water"); return 0
    n = 0
    for _ in range(4):                          # the batch stops with "done:empty" when the can runs dry
        try:
            k, st = water_seq(r, with_status=True)
        except Exception as e:
            act.log(f"water_seq unavailable ({e!r}): Python watering"); break
        n += k
        if st.get("status") != "done:empty" or not dry_tiles(r): break
        if not refill(): break
    if sv.state()["player"]["stamina"] < 40 and dry_tiles(r):
        try:
            import mining
            for _ in range(4):                                   # food restores energy (Amer): eat, keep watering
                if sv.state()["player"]["stamina"] >= 80: break
                mining.eat_if_tired(80)
        except Exception:
            pass
        if dry_tiles(r) and sv.state()["player"]["stamina"] >= 30:
            try: n += water_seq(r)
            except Exception: pass
    if sv.state()["player"]["stamina"] < 15:
        act.log(f"water: stopped, stamina {sv.state()['player']['stamina']} (Su 18 pass-out)"); return n
    n += _water_pass(r)
    left = dry_tiles(r)
    if _retry and left and sv.state()["player"]["stamina"] >= 15:
        act.log(f"water: {len(left)} still dry after pass 1 (e.g. {left[:3]})")
        refill(); n += _water_pass(r)
        left = dry_tiles(r)
        if left: act.log(f"water: {len(left)} still dry after pass 2")
    return n

@act.slow
def _water_pass(r=20):
    """Stand on spots that cover the most dry crops among the 8 neighbours (crops are walkable; the own
    tile is not counted, to be safe), nearest first. Cuts walking ~5x versus one approach per tile."""
    _, feats, _ = tile_info(r=r)
    dry = {t for t, f in feats.items() if f["type"] == "HoeDirt" and "crop" in f and not f["watered"] and not f.get("ready")}
    total = len(dry)
    g = sv.call("grid")["rows"]
    def standable(t):
        x, y = t
        return 0 <= y < len(g) and 0 <= x < len(g[0]) and (g[y][x] == "." or t in feats and feats[t]["type"] == "HoeDirt")
    failed_spots = set()
    for _ in range(total + 10):
        if not dry: break
        _, me = act.here()
        best = None
        for t in dry:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    sp = (t[0] + dx, t[1] + dy)
                    if sp in failed_spots or not standable(sp): continue
                    cov = sum(1 for u in dry if u != sp and abs(u[0] - sp[0]) <= 1 and abs(u[1] - sp[1]) <= 1)
                    if cov == 0: continue
                    d = abs(sp[0] - me[0]) + abs(sp[1] - me[1])
                    score = cov * 4 - d * 0.5
                    if best is None or score > best[0]: best = (score, sp)
        if not best: break
        sp = best[1]
        if sp != me and act.walk(*sp) != "arrived":
            failed_spots.add(sp)
            if len(failed_spots) > 30: break
            continue
        _, me = act.here()
        if sv.state()["player"]["stamina"] < 15:
            act.log("water pass: stamina low, stopping"); return total - len(dry)
        for u in sorted(u for u in dry if u != me and abs(u[0] - me[0]) <= 1 and abs(u[1] - me[1]) <= 1):
            w = can_water()
            if w is not None and w[0] <= 0:
                act.log(f"watering can empty ({w[0]}/{w[1]}): refilling")
                if not refill():
                    return total - len(dry)
                if act.walk(*me) != "arrived":
                    break
            act.use(*u, tool="Watering Can")
            dry.discard(u)
    return total - len(dry)

def can_water():
    """(left, max) as shown on the can's toolbar bar; None if the mod build doesn't report it."""
    c = next((i for i in act.inv() if i["name"] == "Watering Can"), None)
    if not c or c.get("water") is None:
        return None
    return c["water"], c["water_max"]

def clear_debris(r=14, min_stamina=40, until_time=1800, center=None):
    """Clear nearest weeds/stones/twigs for resources until tired or late."""
    n = 0
    while True:
        s = sv.state()
        if s["player"]["stamina"] < min_stamina or s["time"] >= until_time:
            break
        objs, _, _ = tile_info(r=r)
        _, me = act.here()
        c = center or me
        cand = [t for t, o in objs.items() if o["name"] in TOOL_FOR]
        if not cand:
            break
        cand.sort(key=lambda t: abs(t[0] - me[0]) + abs(t[1] - me[1]) + 0.5 * (abs(t[0] - c[0]) + abs(t[1] - c[1])))
        t = cand[0]
        if approach(t) != "arrived":
            objs.pop(t); continue
        clear(t); n += 1
    return n

def refill():
    """Fill the watering can at the nearest open water."""
    w = sv.call("water", r=30)
    if not w:
        act.log("no water nearby to refill"); return False
    _, me = act.here()
    w.sort(key=lambda t: abs(t[0] - me[0]) + abs(t[1] - me[1]))
    for t in w[:15]:
        if act.walk(t[0], t[1], adjacent=True) == "arrived":
            act.use(t[0], t[1], tool="Watering Can")
            act.log(f"refilled can at {tuple(t)}: {can_water()}")
            return True
    return False

def dry_tiles(r=25):
    _, feats, _ = tile_info(r=r)
    return sorted(t for t, f in feats.items() if f["type"] == "HoeDirt" and "crop" in f and not f["watered"] and not f.get("ready"))

def collect_debris(r=6):
    """Walk over dropped items nearby so they get picked up."""
    for _ in range(10):
        a = sv.call("around", r=r)
        d = [x for x in a["debris"] if x["x"] > 0]
        if not d:
            return
        _, me = act.here()
        d.sort(key=lambda x: abs(x["x"] - me[0]) + abs(x["y"] - me[1]))
        t = (d[0]["x"], d[0]["y"])
        if act.walk(*t) != "arrived" and act.walk(*t, adjacent=True) != "arrived":
            return

def chop_trees(wood_target=50, min_stamina=30, r=20):
    """Chop mature trees (and their stumps) until wood_target wood is held."""
    def wood():
        return sum(i["stack"] for i in act.inv() if i["name"] == "Wood")
    skip = set()
    while wood() < wood_target and sv.state()["player"]["stamina"] > min_stamina and sv.state()["time"] < 2300:
        _, feats, _ = tile_info(r=r)
        _, me = act.here()
        trees = [t for t, f in feats.items() if f["type"] == "Tree" and f.get("stage", 0) >= 5 and t not in skip]
        if not trees:
            act.log("no mature trees nearby"); break
        trees.sort(key=lambda t: abs(t[0] - me[0]) + abs(t[1] - me[1]))
        t = trees[0]
        if approach(t) != "arrived":
            act.log(f"cannot reach tree {t}"); skip.add(t); continue
        for _ in range(40):                       # tree then stump
            _, feats, _ = tile_info(r=2)
            if t not in feats or feats[t]["type"] != "Tree":
                break
            act.use(*t, tool="Axe")
            if sv.state()["player"]["stamina"] <= min_stamina:
                break
        collect_debris()
        act.log(f"tree {t} down, wood {wood()}")
    return wood()

def clear_path_to(goal, r=60, debris_cost=4):
    """When no free path exists: A* where weeds/stones/twigs/grass count as passable (cost 4),
    then walk it, clearing each blocking tile with the right tool."""
    import heapq
    g = sv.call("grid")["rows"]
    objs, feats, blocked = tile_info(r=r)
    _, start = act.here()
    def cost(t):
        x, y = t
        if y < 0 or y >= len(g) or x < 0 or x >= len(g[0]): return None
        if g[y][x] == ".": return 1
        o = objs.get(t)
        if o and o["name"] in TOOL_FOR: return debris_cost
        f = feats.get(t)
        if f and f["type"] == "Grass": return 2
        if f and f["type"] == "Tree": return 12     # Fa 19 Y2: wild trees walled off the farm exit and the chests
        return None
    openq = [(0, start)]; came = {start: None}; gs = {start: 0}
    while openq:
        _, c = heapq.heappop(openq)
        if c == goal: break
        for d in ((1,0),(-1,0),(0,1),(0,-1)):
            n = (c[0]+d[0], c[1]+d[1]); k = cost(n)
            if k is None: continue
            ng = gs[c] + k
            if n not in gs or ng < gs[n]:
                gs[n] = ng; came[n] = c
                heapq.heappush(openq, (ng + abs(n[0]-goal[0]) + abs(n[1]-goal[1]), n))
    if goal not in came:
        return False
    path = []; n = goal
    while n: path.append(n); n = came[n]
    path.reverse()
    for t in path[1:]:
        if g[t[1]][t[0]] != ".":
            clear(t)
        if act.walk(*t) != "arrived":
            if act.walk(*t) != "arrived":
                return False
    return True

SCYTHE_CROPS = {"262", "300"}   # Wheat, Amaranth: "harvested using a Scythe" (wiki Wheat / Amaranth)

@act.slow
def harvest_all(r=40):
    """Right-click every ready crop (like a player picking it); scythe crops get a scythe swing.
    Fa 27-28: r=25 around (64,20) missed the south rows (a Yam for Fall Crops, 5 Pumpkins), and 15 ripe
    Wheat were right-clicked, which does nothing."""
    _, feats, _ = tile_info(r=r)
    ready = sorted(t for t, f in feats.items() if f["type"] == "HoeDirt" and f.get("ready"))
    # Su 23 Y2: 80 Blueberries took ~5 game hours (about 20 Python round trips per crop at 1x). Batch them in the mod.
    st = sv.state()
    if ready and st.get("backpack", 12) - len(st["inventory"]) >= 2:
        try:
            return _harvest_seq(ready, feats)
        except Exception as e:
            act.log(f"harvest_seq failed ({e!r}); per-crop fallback")
            _, feats, _ = tile_info(r=r)
            ready = sorted(t for t, f in feats.items() if f["type"] == "HoeDirt" and f.get("ready"))
    n = 0
    for t in ready[:80]:
        st = sv.state()
        if len(st["inventory"]) >= st.get("backpack", 12):
            act.log("harvest: backpack full, stopping (Su 17 Y2)"); break
        if approach(t) == "arrived":
            if str(feats[t].get("crop")) in SCYTHE_CROPS and act.slot_of("Scythe") is not None:
                act.use(*t, tool="Scythe")
            else:
                act.use(*t, right=True)
            act.dismiss(); n += 1
    collect_debris()
    return n

def _harvest_seq(ready, feats):
    """One SeqTask: walk next to each ripe crop (nearest first) and right-click it (scythe for scythe crops)."""
    ax = act.slot_of("Axe"); sc = act.slot_of("Scythe")
    if ax is not None and ax >= 12: ax = act.to_hotbar("Axe")
    if sc is not None and sc >= 12: sc = act.to_hotbar("Scythe", target=10)
    _, me = act.here()
    todo, ops, cur = set(ready), [], me
    while todo:
        t = min(todo, key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1])); todo.discard(t); cur = t
        ops.append({"op": "walk", "x": t[0], "y": t[1], "adjacent": True})
        if str(feats[t].get("crop")) in SCYTHE_CROPS and sc is not None:
            ops.append({"op": "use", "x": t[0], "y": t[1], "slot": sc})
        else:
            ops.append({"op": "use", "x": t[0], "y": t[1], "slot": ax if ax is not None else -1, "right": True})
    sv.call("seq", ops=ops)
    st = {}
    for _ in range(6000):
        st = sv.call("seq_status")
        if st["status"] != "busy": break
        time.sleep(0.1)
    act.dismiss()
    collect_debris()
    _, f2, _ = tile_info(r=40)
    left = sum(1 for t in ready if f2.get(t, {}).get("ready"))
    act.log(f"harvest_seq: {len(ready) - left}/{len(ready)} picked, {st}")
    return len(ready) - left

def empty_dirt(r=25):
    _, feats, _ = tile_info(r=r)
    return sorted(t for t, f in feats.items() if f["type"] == "HoeDirt" and "crop" not in f)

def plant_seq(tiles, seed, fertilizer=None):
    """Batch planting inside the mod (SeqTask): clear debris, hoe (animation cancelled once tilled),
    fertilize, plant. Watering follows via water_all. Returns tiles that got a crop."""
    if act.slot_of(seed) is None: return 0
    sslot = act.to_hotbar(seed, target=11)
    fslot = act.to_hotbar(fertilizer, target=10) if fertilizer and act.slot_of(fertilizer) is not None else None
    slot = {n: act.slot_of(n) for n in ("Hoe", "Scythe", "Pickaxe", "Axe")}
    if None in (sslot, slot["Hoe"]) or sslot >= 12 or slot["Hoe"] >= 12: return 0
    objs, feats, _ = tile_info(r=40)
    ops = []
    for t in tiles:
        ops.append({"op": "walk", "x": t[0], "y": t[1], "adjacent": True})
        o = objs.get(t)
        if o and o["name"] in TOOL_FOR and slot.get(TOOL_FOR[o["name"]]) is not None:
            k = 3 if TOOL_FOR[o["name"]] == "Pickaxe" else 1
            ops += [{"op": "use", "x": t[0], "y": t[1], "slot": slot[TOOL_FOR[o["name"]]]}] * k
        f = feats.get(t)
        if f and f["type"] == "Grass" and slot["Scythe"] is not None:
            ops.append({"op": "use", "x": t[0], "y": t[1], "slot": slot["Scythe"]})
        if not f or f["type"] != "HoeDirt":
            ops.append({"op": "use", "x": t[0], "y": t[1], "slot": slot["Hoe"], "cancel": "hoe"})
        if fslot is not None and fslot < 12:
            ops.append({"op": "use", "x": t[0], "y": t[1], "slot": fslot})
        ops.append({"op": "use", "x": t[0], "y": t[1], "slot": sslot})
    sv.call("seq", ops=ops)
    st = {}
    for _ in range(3000):
        st = sv.call("seq_status")
        if st["status"] != "busy": break
        time.sleep(0.2)
    _, feats, _ = tile_info(r=40)
    got = sum(1 for t in tiles if "crop" in feats.get(t, {}))
    act.log(f"plant_seq {seed}: {got}/{len(tiles)} planted, {st}")
    return got

def plant_fertilized(seed, fertilizer, n):
    """New plot: hoe, fertilize, plant, water (gold-quality crops for the Quality Crops bundle)."""
    tiles = choose_plot(n, 48, 78, 19, 45)
    try:
        got = plant_seq(tiles, seed, fertilizer)
    except Exception as e:
        act.log(f"plant_seq failed: {e!r}"); got = 0
    left = sum(i["stack"] for i in act.inv() if i["name"] == seed)
    if left:
        got += hoe_plant_water([t for t in tiles if t not in {k for k, f in tile_info(r=40)[1].items() if "crop" in f}][:left], seed, fertilizer=fertilizer)
    return got

@act.slow
def _plant_existing(seed, r):
    n = 0
    for t in empty_dirt(r):
        if act.slot_of(seed) is None: break
        if approach(t) == "arrived":
            act.use(*t, tool=seed); n += 1
    return n

def _plant_existing_seq(seed, r):
    """Batch: stand on coverage spots over empty hoed dirt and plant the 8 neighbours (SeqTask)."""
    tiles = empty_dirt(r)
    if len(tiles) < 6 or act.slot_of(seed) is None: return 0
    sslot = act.to_hotbar(seed, target=11)
    if sslot is None or sslot >= 12: return 0
    n_seed = sum(i["stack"] for i in act.inv() if i["name"] == seed)
    _, feats, _ = tile_info(r=40)
    g = sv.call("grid")["rows"]
    _, me = act.here()
    ops, k = [], 0
    for sp, cov in _plan_water_route(tiles, me, g, feats):
        if k >= n_seed: break
        ops.append({"op": "walk", "x": sp[0], "y": sp[1]})
        for u in cov:
            if k >= n_seed: break
            ops.append({"op": "use", "x": u[0], "y": u[1], "slot": sslot}); k += 1
    sv.call("seq", ops=ops)
    st = {}
    for _ in range(3000):
        st = sv.call("seq_status")
        if st["status"] != "busy": break
        time.sleep(0.2)
    left = sum(i["stack"] for i in act.inv() if i["name"] == seed)
    act.log(f"plant existing (batch) {seed}: {n_seed - left} planted, {st['status']}")
    return n_seed - left

def replant(seed, r=25):
    """Plant seed into empty hoed dirt first, then new plot tiles; water what was planted."""
    act.goto("Farm", 64, 24)
    try:
        n = _plant_existing_seq(seed, 30)
    except Exception as e:
        act.log(f"plant existing batch failed: {e!r}"); n = 0
    n += _plant_existing(seed, r)
    left = sum(i["stack"] for i in act.inv() if i["name"] == seed)
    # Sp 2 Y2: 146 seeds -> a 5 x 30 block never fit ("no plot found"); plant in chunks of <= 40 on 8-wide blocks
    for _chunk in range(8):
        if not left: break
        k = min(left, 40)
        try:
            tiles = choose_plot(k, 40, 78, 17, 50, w=8)
        except RuntimeError:
            try: tiles = choose_plot(min(k, 15), 40, 78, 17, 50, w=5)
            except RuntimeError:
                act.log(f"replant {seed}: no plot for {left} seeds"); break
        try:
            n += plant_seq(tiles, seed)
        except Exception as e:
            act.log(f"plant_seq failed: {e!r}")
        left2 = sum(i["stack"] for i in act.inv() if i["name"] == seed)
        if left2 == left:
            n += hoe_plant_water(tiles, seed)
            left2 = sum(i["stack"] for i in act.inv() if i["name"] == seed)
            if left2 == left: break
        left = left2
    if n and sv.state()["weather"] not in ("rain", "storm"):
        act.goto("Farm", 64, 24); water_all(r=28)            # new seeds grow only if watered today
    return n

def clear_dead(r=30):
    """Season change kills last season's crops: scythe them so the dirt can be replanted.
    Batch first (SeqTask: stand on coverage spots, scythe the 8 neighbours), Python fallback after."""
    act.goto("Farm", 64, 24)
    _, feats, _ = tile_info(r=r)
    dead = sorted(t for t, f in feats.items() if f["type"] == "HoeDirt" and f.get("dead"))
    sc = act.slot_of("Scythe")
    if len(dead) > 5 and sc is not None and sc < 12:
        g = sv.call("grid")["rows"]
        _, me = act.here()
        ops = []
        for sp, cov in _plan_water_route(dead, me, g, feats):
            ops.append({"op": "walk", "x": sp[0], "y": sp[1]})
            ops += [{"op": "use", "x": u[0], "y": u[1], "slot": sc} for u in cov]
        try:
            sv.call("seq", ops=ops)
            for _ in range(3000):
                st = sv.call("seq_status")
                if st["status"] != "busy": break
                time.sleep(0.2)
            act.log(f"clear_dead batch: {st}")
        except Exception as e:
            act.log(f"clear_dead batch failed: {e!r}")
    return _clear_dead_py(r)

@act.slow
def _clear_dead_py(r=30):
    _, feats, _ = tile_info(r=r)
    dead = sorted(t for t, f in feats.items() if f["type"] == "HoeDirt" and f.get("dead"))
    n = 0
    for t in dead:
        if approach(t) == "arrived":
            act.use(*t, tool="Scythe")
            _, f2, _ = tile_info(r=2)
            if not f2.get(t, {}).get("dead"): n += 1
            else:
                act.use(*t, tool="Pickaxe"); n += 1     # fallback: pickaxe removes the dirt and the crop
    if dead: act.log(f"cleared {n}/{len(dead)} dead crops")
    return n
