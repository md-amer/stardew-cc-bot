"""Mines: break rocks, find ladders, fight, descend; leave when tired/hurt/late."""
import time, json
ARR_FILE = "/tmp/claude-1000/mine_arrival.json"
import sv, act, farming

WEAPONS = ("Galaxy Sword", "Silver Saber", "Cutlass", "Pirate's Sword", "Steel Smallsword", "Iron Edge", "Femur", "Insect Head", "Wooden Blade", "Rusty Sword")   # best first
ROCKS = {"Stone"}      # plain rocks; ore nodes also named Stone in 1.6 objects -> id tells

def weapon():
    for w in WEAPONS:
        if act.slot_of(w) is not None:
            return w
    return None

def fight(m_info, max_swings=12):
    """Swing at the nearest monster until it dies or we are hurt."""
    w = weapon()
    if not w:
        return False
    for _ in range(max_swings):
        mi = sv.call("mine")
        if not mi or not mi["monsters"]:
            return True
        _, me = act.here()
        m = min(mi["monsters"], key=lambda m: abs(m["x"] - me[0]) + abs(m["y"] - me[1]))
        d = abs(m["x"] - me[0]) + abs(m["y"] - me[1])
        if d > 3:
            return True
        if d > 1:
            act.walk(m["x"], m["y"], adjacent=True, timeout=5)
        act.use(m["x"], m["y"], tool=w)
        if sv.state()["player"]["health"] < 35 and not eat_if_hurt(35):
            return False
    return True

def deepest_lift():
    """Deepest floor the lift offers (what the lift menu shows): every 5 floors."""
    import json, os
    try:
        return json.load(open(os.path.join(os.path.dirname(__file__), "progress.json"))).get("deepest_lift", 0)
    except Exception:
        return 0

def eat_if_tired(threshold=25):
    """Food also restores energy (Amer): eat before energy ends the session."""
    s = sv.state()
    if s["player"]["stamina"] >= threshold:
        return False
    return eat_if_hurt(threshold=999)

def eat_if_hurt(threshold=50):
    """Eat the cheapest edible item no bundle needs (needs the mod's `edible`/`heal` fields)."""
    s = sv.state()
    if s["player"]["health"] >= threshold:
        return False
    mi = sv.call("mine")
    if mi and danger(mi, r=3) and s["player"]["health"] > 15:
        return False                      # eating animation = no defence: fight (reflex) first
    import needs
    q = needs.quota()
    hold = needs.quality_holds()          # W6: ate a gold Melon kept for Quality Crops
    if "Wine" in q:                        # W25: ate the Crystal Fruit kept for the keg
        hold = dict(hold); fr = [i for i in s["inventory"] if i.get("cat") == -79]
        if len(fr) == 1: hold[fr[0]["name"]] = (0, 1)
    food = [i for i in s["inventory"] if i.get("edible", -300) > 0 and i.get("heal", 0) > 0 and i["name"] not in q
            and not (i["name"] in hold and i.get("quality", 0) >= hold[i["name"]][0])]
    if not food:
        return False
    f = min(food, key=lambda i: i.get("price", 0) / max(1, i["heal"]))
    _, me = act.here()
    slot = f["slot"] if f["slot"] < 12 else act.to_hotbar(f["name"])
    if slot is None or slot >= 12:
        return False
    n0 = sum(i["stack"] for i in s["inventory"] if i["name"] == f["name"])
    h0, e0 = s["player"]["health"], s["player"]["stamina"]
    asked = False
    prev = sv.call("speed").get("speed", 1)
    sv.call("speed", n=1)                 # Fa 21: at 12x the question came after the 3 s window, dismiss() said No
    try:
        sv.call("use", x=me[0], y=me[1], slot=slot, right=True)     # action with food in hand -> "Eat?"
        for _ in range(40):
            time.sleep(0.15)
            yes = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
            if yes:
                asked = True
                for _k in range(6):           # W5: the first click can land while the text still animates
                    sv.call("click", x=yes[0]["x"], y=yes[0]["y"]); time.sleep(0.25)
                    if not [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]: break
                break
        try:      # eating animation: food count drops at once, health/energy rise when it ends
            sv.wait(lambda st: not st["player"]["using_tool"] and (st["player"]["health"] > h0 or st["player"]["stamina"] > e0), timeout=4, every=0.2)
        except TimeoutError:
            pass
        sv.call("stop")                   # never leave a tool task running into the next action (Fa 21 fishing)
    finally:
        sv.call("speed", n=prev)
    s2 = sv.state()
    n1 = sum(i["stack"] for i in s2["inventory"] if i["name"] == f["name"])
    if n1 >= n0:
        act.log(f"eat {f['name']} FAILED (question seen: {asked}); menu {s2.get('menu') and s2['menu'].get('type')}")
        act.dismiss(); return False
    act.log(f"ate {f['name']}: health {h0} -> {s2['player']['health']}, energy {e0} -> {s2['player']['stamina']}")
    return True
def danger(mi, r=3):
    _, me = act.here()
    return [m for m in mi["monsters"] if abs(m["x"] - me[0]) + abs(m["y"] - me[1]) <= r]

# Node types a player tells apart by sight (decompiled GameLocation.breakStone ids)
VALUABLE = {"751", "849", "290", "850", "764", "765",            # copper, iron, gold, iridium
            "2", "4", "6", "8", "10", "12", "14", "44", "46",  # gem nodes, gem node, mystic stone
            "75", "76", "77", "819",                          # geode stones, omni geode node
            "BasicCoalNode0", "BasicCoalNode1"}

def _sid(o):
    return o.get("id", "").replace("(O)", "")

def loot_floor(r=10, min_sta=30, nodes_ok=True):
    """Before taking the ladder: grab cave forage (minerals too), mine valuable nodes nearby, sweep drops.
    Amer W7 Y2: "not collecting all valuables, missing red quartz": isForage() excludes minerals (Quartz, Fire Quartz,
    Earth Crystal, Frozen Tear), so they were never picked. Mine forage = spawned, non-bigcraftable, not a Stone."""
    got = 0; skip = set()
    for _ in range(30):
        s = sv.state()
        if s.get("backpack", 12) - len(s["inventory"]) < 1:
            break
        a = sv.call("around", r=r)
        _, me = act.here()
        forage = [o for o in a["objects"] if (o.get("forage") or (o.get("spawned") and not o.get("bc") and o.get("name") != "Stone"))
                  and (o["x"], o["y"]) not in skip]
        nodes = [o for o in a["objects"] if _sid(o) in VALUABLE and (o["x"], o["y"]) not in skip] \
            if nodes_ok and s["player"]["stamina"] >= min_sta else []
        if not forage and not nodes:
            break
        o = min(forage + nodes, key=lambda o: abs(o["x"] - me[0]) + abs(o["y"] - me[1]) - (30 if o in forage else 0))
        t = (o["x"], o["y"])
        if o in forage:
            if act.walk(*t, adjacent=True, timeout=15) != "arrived": skip.add(t); continue
            n0 = sum(i["stack"] for i in act.inv())
            act.use(*t, right=True)
            if sum(i["stack"] for i in act.inv()) > n0: act.log(f"mine: picked {o.get('name')}")
            else: skip.add(t)
        else:
            if farming.approach(t) != "arrived": skip.add(t); continue
            for _ in range(4):                    # copper/iron need a few hits with the basic pickaxe
                act.use(*t, tool="Pickaxe")
                if not any(_sid(x) in VALUABLE and (x["x"], x["y"]) == t for x in sv.call("around", r=2)["objects"]):
                    break
        got += 1
        farming.collect_debris(r=4)
    if got:
        act.log(f"mine: looted {got} nodes/forage")
    return got

def _mins(t):
    return (t // 100) * 60 + t % 100

def descend_level(max_rocks=250):
    """On a mine level: break rocks until a ladder/shaft shows, then take it.
    The lift saves only every 5 floors (lift menu: 0, 5, 10...). Within 2 floors of the next lift
    floor, push on with lower limits: leaving at floor 9 throws the day's depth away."""
    mi0 = sv.call("mine")
    if not mi0: return "left_mine"          # Sp 17: called after the lift ride failed (not in the mine)
    lvl0 = mi0["level"]
    # Amer W6 Y2: "leaving the mine before reaching a lift level = loss" (W4-W6 restarted at 95 three times).
    # Off a lift floor every floor is lost on exit: push to the next lift floor until midnight (home before 2:00).
    push = lvl0 % 5 != 0
    min_sta, min_hp = (4, 35) if push else (12, 40)     # W5: health 32 + failed eat -> knocked out at 97
    bad_exits, fails = set(), {}
    looted = False
    unreachable = set()
    t_floor = _mins(sv.state()["time"])
    for _ in range(max_rocks):
        s = sv.state()
        if s["player"]["health"] < 60 and eat_if_hurt(60):
            s = sv.state()
        if s["player"]["stamina"] < min_sta + 10 and eat_if_tired(min_sta + 10):
            s = sv.state()
        if s["player"]["stamina"] < min_sta or s["player"]["health"] < min_hp or s["time"] >= 2400:
            return "tired"
        if s["time"] >= (2400 if push else 2200):     # W11: reached a floor at 23:00, home after 1:00
            return "late"
        mi = sv.call("mine")
        if not mi:
            return "left_mine"
        if mi["level"] != lvl0:
            return "descended"
        exits = [tuple(e) for e in mi["ladders"] + mi["shafts"] if tuple(e) not in bad_exits]
        if danger(mi):
            # Amer W25 Y2: left at 109 "hurt" one floor short of the 110 lift. Off a lift floor with a ladder in
            # sight, take it instead of leaving (1 s invulnerable on arrival; depth saved at the lift floor).
            if not fight(mi) and not (push and exits and s["player"]["health"] > 15):
                return "hurt"
        if exits and not looted:
            # Amer: take valuables on the floor while energy allows. W5: r=40 looting held one floor for 2.5 game
            # hours; now r=18 and once per floor. Forage (Quartz, Fire Quartz) always; nodes only early on a floor
            # and not in late push (W7 Y2: push skipped looting entirely = 4 of 5 floors unlooted).
            looted = True
            early = _mins(sv.state()["time"]) - t_floor < 40 and s["time"] < 2200
            loot_floor(r=18, min_sta=50, nodes_ok=early)
        if exits:
            _, me = act.here()
            e = min(exits, key=lambda t: abs(t[0] - me[0]) + abs(t[1] - me[1]))
            ok = act.walk(e[0], e[1], adjacent=True, timeout=20) == "arrived"
            if not ok:
                # W3: a ladder behind rocks was retried by walking for 4 game hours. Mine a path to it instead.
                for g in ((e[0], e[1] + 1), (e[0] - 1, e[1]), (e[0] + 1, e[1]), (e[0], e[1] - 1)):
                    try:
                        if farming.clear_path_to(g, r=40, debris_cost=1.5): ok = True; break
                    except Exception as ex:
                        act.log(f"mine: path to ladder failed {ex!r}"); break
            if ok:
                act.use(e[0], e[1], right=True)
                act.dismiss()        # shaft asks to jump: confirm
                try:
                    sv.wait(lambda s: (sv.call("mine") or {}).get("level") != lvl0, timeout=6)
                    return "descended"
                except TimeoutError:
                    pass
            fails[e] = fails.get(e, 0) + 1
            if fails[e] >= 2:
                bad_exits.add(e); act.log(f"mine: ladder {e} unreachable, ignoring it")
            continue
        objs, _, _ = farming.tile_info(r=25)
        _, me = act.here()
        rocks = [t for t, o in objs.items() if o["name"] == "Stone"]
        if not rocks:                     # W5: floor 17 ended the day with rocks further than 25 tiles away
            time.sleep(0.5)
            objs, _, _ = farming.tile_info(r=70)
            rocks = [t for t, o in objs.items() if o["name"] == "Stone"]
            if not rocks:
                act.log(f"mine: no Stone objects on floor {lvl0}: {sorted({o['name'] for o in objs.values()})[:12]}")
        if not rocks:
            return "no_rocks"
        # valuable nodes count as closer (ore/gems while hunting the ladder), unless pushing for the lift
        bonus = 0 if push else 6
        rocks.sort(key=lambda t: abs(t[0] - me[0]) + abs(t[1] - me[1]) - (bonus if _sid(objs[t]) in VALUABLE else 0))
        rocks = [t for t in rocks if t not in unreachable]
        if not rocks:
            if not unreachable:
                time.sleep(0.5)               # W13: right after arriving the floor's objects may not be listed yet
                objs, _, _ = farming.tile_info(r=70)
                rocks = [t for t, o in objs.items() if o["name"] == "Stone"]
                if rocks: continue
            return "no_rocks"
        hit = False
        for t in rocks[:3]:
            if farming.approach(t) == "arrived":
                act.use(*t, tool="Pickaxe"); hit = True
                break
            unreachable.add(t)            # W6: the same 3 unreachable rocks were retried 700 times (4 game hours)
        farming.collect_debris(r=3)
    return "gave_up"

def _parse_vec(v):
    # "{X:12 Y:6}" -> (12, 6)
    import re
    m = re.findall(r"-?\d+", v or "")
    return (int(m[0]), int(m[1])) if len(m) >= 2 else None

def leave():
    """Leave the mines: lift on floors with one, else the up-ladder (positions reported by the game)."""
    global ARRIVAL
    mi = sv.call("mine")
    if mi is None:
        return
    el = _parse_vec(mi.get("elevator_arrival"))
    if el and el != (0, 0):
        ex, ey = el[0], el[1] - 1
        act.walk(*el)
        act.use(ex, ey, right=True); time.sleep(0.6)
        if (sv.state().get("menu") or {}).get("type") == "MineElevatorMenu":
            if _lift_click("0", lambda: sv.state()["player"]["loc"] == "Mine"):
                return
    up = _parse_vec(mi.get("up_arrival"))
    if up and up != (0, 0):
        ARRIVAL = up
    if ARRIVAL is None:
        try: ARRIVAL = tuple(json.load(open(ARR_FILE)))
        except Exception: _, ARRIVAL = act.here()
    x, y = ARRIVAL
    act.walk(x, y)
    act.use(x, y - 1, right=True)
    time.sleep(0.6)
    if (sv.state().get("menu") or {}).get("type") == "MineElevatorMenu":   # arrived by lift: that tile is the lift
        if _lift_click("0", lambda: sv.state()["player"]["loc"] == "Mine"):
            return
    for _ in range(10):                     # "Leave the mines?" -> Yes
        time.sleep(0.4)
        yes = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
        if yes:
            sv.call("click", x=yes[0]["x"], y=yes[0]["y"]); break
    sv.wait(lambda s: s["player"]["loc"] == "Mine", timeout=10)

ARRIVAL = None

def _lift_click(floor, arrived, tries=5):
    """Lift buttons sometimes ignore the first click right after the menu opens: retry until moved."""
    for _ in range(tries):
        if (sv.state().get("menu") or {}).get("type") != "MineElevatorMenu":
            break
        b = next((w for w in sv.widgets()["widgets"] if w["field"] == "elevators" and w["name"] == floor), None)
        if not b:
            break
        time.sleep(0.4)
        sv.call("click", x=b["x"], y=b["y"])
        try:
            sv.wait(lambda s: arrived(), timeout=3)
            return True
        except TimeoutError:
            pass
    return arrived()

MINE_SPEED = 8   # combat decisions come from Python in real time: keep the game slower than travel speed

def run(max_levels=10, until_time=2300):
    prev = sv.call("speed").get("speed", 1)
    sv.call("speed", n=min(prev, MINE_SPEED))
    try:
        return _run(max_levels, until_time)
    finally:
        sv.call("speed", n=prev)

def _run(max_levels=10, until_time=2200):
    if act.here()[0].startswith("UndergroundMine"):      # resumed inside the mine: keep the depth
        return _descend_loop(max_levels, until_time)
    act.goto("Mine")
    for _ in range(100):                  # first visit: Marlon gives a sword (cutscene)
        s = act.dismiss()
        if s.get("free") and not s.get("event"): break
        time.sleep(0.3)
    acts = sv.call("actions")
    elev = next((a for a in acts if a["action"] == "MineElevator"), None)
    entered = False
    if elev:
        # ride the lift straight to the deepest unlocked floor
        act.walk(elev["x"], elev["y"], adjacent=True)
        act.use(elev["x"], elev["y"], right=True)
        time.sleep(0.6)
        if (sv.state().get("menu") or {}).get("type") == "MineElevatorMenu":
            btns = [w for w in sv.widgets()["widgets"] if w["field"] == "elevators" and w["name"].isdigit()]
            deepest = max(btns, key=lambda w: int(w["name"]))
            try:
                import play_day
                pr = play_day.prog(); pr["deepest_lift"] = int(deepest["name"]); play_day.save_prog(pr)
            except Exception:
                pass
            # Fa 9 Y2: always floor 85 -> 1-3 floors/day and no Earth Crystal (wiki: foraged mostly on floors 1-39),
            # Aquamarine (nodes 40+), Fire Quartz (80+). Pick the lift floor by what bundles still need.
            import needs as _n
            q_ = set(_n.quota())
            want_floor = int(deepest["name"])
            if "Earth Crystal" in q_:      # rotate 10..35 by day (Fa 11-13 Y2: always 10 = only floors 10-14 seen)
                want_floor = (10, 15, 20, 25, 30, 35)[sv.state()["day"] % 6]
            elif "Aquamarine" in q_ or "Frozen Tear" in q_: want_floor = 40
            pick = min((w for w in btns if int(w["name"]) >= want_floor), key=lambda w: int(w["name"]), default=deepest)
            if int(pick["name"]) > 0:
                entered = _lift_click(pick["name"], lambda: sv.call("mine") is not None)
                act.log(f"lift to floor {pick['name']} (deepest {deepest['name']}): {'ok' if entered else 'FAILED'}")
            else:
                import town; town.close_menu()
    if not entered:
        ladder = next(a for a in acts if a["action"] == "Mine")       # entrance ladder down
        act.walk(ladder["x"], ladder["y"], adjacent=True)
        act.use(ladder["x"], ladder["y"], right=True)
        sv.wait(lambda s: sv.call("mine") is not None, timeout=8)
    act.dismiss()
    return _descend_loop(max_levels, until_time)

def _descend_loop(max_levels, until_time):
    levels = 0
    global ARRIVAL
    while True:
        lv_now = (sv.call("mine") or {}).get("level")
        on_lift = not lv_now or lv_now % 5 == 0
        # stop only on a lift floor (depth saved); off one, keep going to the next lift floor (Amer W6 Y2)
        if on_lift and (levels >= max_levels or sv.state()["time"] >= until_time): break
        if sv.state()["time"] >= 2400: break
        _, ARRIVAL = act.here()
        json.dump(list(ARRIVAL), open(ARR_FILE, "w"))
        r = descend_level()
        if r == "descended":              # W7: leave() walked to the previous floor's ladder tile (stale ARRIVAL)
            time.sleep(0.3)
            _, ARRIVAL = act.here()
            json.dump(list(ARRIVAL), open(ARR_FILE, "w"))
        mi = sv.call("mine")
        lv = mi and mi["level"]
        act.log(f"mine: {r} -> level {lv}" + (" (lift floor: depth saved)" if lv and lv % 5 == 0 else ""))
        if r != "descended":
            if lv and lv % 5:
                act.log(f"mine: leaving at {lv}, lift saves {lv - lv % 5} (lost {lv % 5} floors of depth)")
            break
        levels += 1
        # tired right after reaching a lift floor: depth is saved, leave now by its lift
        s = sv.state()
        if lv and lv % 5 == 0 and (s["player"]["stamina"] < 40 or s["player"]["health"] < 40):
            act.log(f"mine: lift floor {lv} reached with low energy/health, leaving")
            break
    if sv.call("mine") is not None:
        _, ARRIVAL = ARRIVAL, ARRIVAL
        leave()
    return levels

def ghostfish(until_time=1300, floor="20"):
    """Specialty Fish: Ghostfish (wiki: Mines floors 20 and 60, any season/weather, 6am-2am). Ride the lift to
    floor 20, fish its water, stay in the mine afterwards (mining.run resumes from the current floor)."""
    import needs, daily
    q = needs.quota()
    # W13: fishing floor 20 restarted the day's mining at 20 although the lift reached 30. Specialty Fish also needs
    # the summer Pufferfish, so the Ghostfish waits until Pufferfish is in (Y2).
    if "Ghostfish" not in q or "Pufferfish" in q or deepest_lift() < int(floor): return False
    s = sv.state()
    if s["time"] >= until_time - 100: return False
    prev = sv.call("speed").get("speed", 1)
    sv.call("speed", n=min(prev, MINE_SPEED))
    try:
        act.goto("Mine")
        for _ in range(100):
            st = act.dismiss()
            if st.get("free") and not st.get("event"): break
            time.sleep(0.3)
        elev = next((a for a in sv.call("actions") if a["action"] == "MineElevator"), None)
        if not elev: return False
        act.walk(elev["x"], elev["y"], adjacent=True); act.use(elev["x"], elev["y"], right=True); time.sleep(0.6)
        if not _lift_click(floor, lambda: (sv.call("mine") or {}).get("level") == int(floor)):
            act.log("ghostfish: lift to floor 20 failed"); import town; town.close_menu(); return False
        act.dismiss()
        _, me = act.here()
        if not daily.go_fish_spot_near(*me, r=40):
            act.log("ghostfish: no fishing spot on floor 20"); return False
        got = False
        for _ in range(30):                     # short sessions: monsters can reach the farmer while a cast is out
            eat_if_hurt(60)
            if sv.state()["player"]["health"] < 40: act.log("ghostfish: hurt, stopping"); break
            daily.fish_session(until_time=until_time, min_stamina=40, max_casts=3)
            if "Ghostfish" in {i["name"] for i in act.inv()}: got = True; break
            if sv.state()["time"] >= until_time - 20: break
        act.log(f"ghostfish: {'CAUGHT' if got else 'not caught'} (floor {floor}, until {sv.state()['time']})")
        return got
    finally:
        sv.call("speed", n=prev)
