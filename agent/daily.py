"""Daily loop pieces + per-day stats log (RUNLOG.csv) for publishing."""
import csv, os, time
import sv, act, farming, town

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNLOG = os.path.join(ROOT, "RUNLOG.csv")
MAILBOX = (68, 16)        # Standard farm
SHIP_BIN = (71, 14)       # Standard farm shipping bin (left tile)

def stats_row(note=""):
    s = sv.state()
    p = s["player"]
    row = {
        "real_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "date": f"Y{s['year']} {s['season']} {s['day']}",
        "game_time": s["time"], "money": p["money"], "stamina": p["stamina"],
        **{k: v for k, v in p["skills"].items()},
        "inventory": ";".join(f"{i['name']}x{i['stack']}" for i in s["inventory"]),
        "note": note,
    }
    new = not os.path.exists(RUNLOG)
    with open(RUNLOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new: w.writeheader()
        w.writerow(row)
    return row

def read_mail():
    act.goto("Farm")
    act.walk(*MAILBOX, adjacent=True)
    for _ in range(6):
        st = act.use(*MAILBOX, right=True)
        s = sv.state()
        m = s.get("menu")
        if not m:
            break
        act.log(f"mail: {m['type']} {m.get('text','')[:60]}")
        if m["type"] == "LetterViewerMenu":
            time.sleep(1.0)
        if "don't have any mail" in m.get("text", ""):
            town.close_menu(); break
        town.close_menu()

def ship(names, hold=None):
    """Ship every stack whose name is in names (hold item, right-click bin).
    hold: {name: min quality}: stacks at/above that quality stay (Quality Crops bundle)."""
    import needs
    hold = hold if hold is not None else {n: q for n, (q, k) in needs.quality_holds().items()}
    act.goto("Farm")
    for it in sorted(act.inv(), key=lambda i: -i["slot"]):
        if it["name"] in names:
            if it["name"] in hold and it.get("quality", 0) >= hold[it["name"]]:
                act.log(f"holding {it['name']} x{it['stack']} (quality {it['quality']}) for Quality Crops"); continue
            act.walk(*SHIP_BIN, adjacent=True)
            n0 = sum(i["stack"] for i in act.inv() if i["name"] == it["name"])
            cur = next((i for i in act.inv() if i["name"] == it["name"] and i.get("quality", 0) == it.get("quality", 0)), None)
            if not cur: continue
            sl = cur["slot"] if cur["slot"] < 12 else act.to_hotbar(it["name"], slot=cur["slot"])
            if sl is None: act.log(f"SHIP FAILED {it['name']}: not on hotbar"); continue
            sv.call("use", x=SHIP_BIN[0], y=SHIP_BIN[1], slot=sl, right=False); act.wait_done("tool", 15)
            n1 = sum(i["stack"] for i in act.inv() if i["name"] == it["name"])
            if n1 < n0:
                act.log(f"shipped {it['name']} x{n0 - n1}")
            else:
                act.log(f"SHIP FAILED {it['name']} (still x{n1})")

JUNK_ORDER = ["Trash", "Joja Cola", "Broken CD", "Broken Glasses", "Soggy Newspaper", "Driftwood",
              "Green Algae", "Seaweed", "Clay", "Stone", "Fiber"]

def take_all_from_grab_menu(max_items=3):
    """Catch popup (backpack full): click item -> if it went to the cursor, swap it with the
    least valuable backpack item and trash that instead. Fish are never thrown away."""
    for k in range(max_items):
        w = sv.widgets()
        src = [x for x in w["widgets"] if x["field"] == "ItemsToGrabMenu.slot"]
        slots = {x["i"]: x for x in w["widgets"] if x["field"] == "inventory.slot"}
        trash = [x for x in w["widgets"] if x["field"] == "trashCan"]
        inv0 = sv.state()["inventory"]
        before = sum(i["stack"] for i in inv0)
        sv.call("click", x=src[k]["x"], y=src[k]["y"]); time.sleep(0.25)
        if sum(i["stack"] for i in sv.state()["inventory"]) != before:
            continue                      # went straight into the backpack
        if k > 0:
            break                         # probably an empty slot: stop
        junk = next((i for n in JUNK_ORDER for i in inv0 if i["name"] == n), None)
        if not junk or not trash:
            # treasure menus refuse OK while an item is on the cursor: drop it at our feet (not destroyed)
            drop = [x for x in w["widgets"] if x["field"] == "dropItemInvisibleButton"]
            if drop:
                sv.call("click", x=drop[0]["x"], y=drop[0]["y"]); time.sleep(0.3)
            act.log("backpack full, nothing to swap: dropped the extra item on the ground"); break
        sv.call("click", x=slots[junk["slot"]]["x"], y=slots[junk["slot"]]["y"]); time.sleep(0.25)  # swap
        sv.call("click", x=trash[0]["x"], y=trash[0]["y"]); time.sleep(0.25)
        act.log(f"made room: trashed {junk['name']} x{junk['stack']}")
    w = sv.widgets()
    ok = [x for x in w["widgets"] if x["field"] == "okButton"]
    if ok and sv.state().get("menu"):
        sv.call("click", x=ok[0]["x"], y=ok[0]["y"]); time.sleep(0.4)
    town.close_menu()

def go_fish_spot_near(x, y, r=30, tries=6, exclude=()):
    """Walk to a bank tile next to water that has a long straight run of open water (good casts)."""
    w = sv.call("water", r=r)
    wset = {tuple(t) for t in w}
    def run_len(t, d):
        n = 0
        while (t[0] + d[0] * (n + 1), t[1] + d[1] * (n + 1)) in wset and n < 6: n += 1
        return n
    w.sort(key=lambda t: abs(t[0] - x) + abs(t[1] - y))
    for t in w[:40]:
        for d in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            bank = (t[0] - d[0], t[1] - d[1])            # land tile facing into the water along d
            if bank in wset or run_len(bank, d) < 4 or any(abs(bank[0]-e[0]) + abs(bank[1]-e[1]) < 4 for e in exclude):
                continue
            if act.walk(*bank) == "arrived":
                return True
            tries -= 1
            if tries <= 0: return False
    return False

def sellable(it):
    """Fish (-4), forage/veg/fruit (-75,-79,-81) etc. Things worth shipping now."""
    # W22 Y2: eggs (-5) and milk (-6) were not sellable -> 58 Eggs sat in the chest, money fell. Bundle items are
    # still never shipped (quota guard in chest_sync_and_ship).
    return it["cat"] in (-4, -75, -79, -81, -80, -20, -23, -2, -12, -5, -6) and it["name"] not in ("Bait",)

def fish_session(until_time=1700, min_stamina=20, max_casts=200, on_full=None, backpack=12):
    """Fish from the current spot (must be next to water) until time/stamina limits."""
    rod = next((act.slot_of(n) for n in ("Iridium Rod", "Fiberglass Rod", "Bamboo Pole", "Training Rod") if act.slot_of(n) is not None), None)
    if rod is None:
        rod = next((i["slot"] for i in act.inv() if "Rod" in i["name"] or "Pole" in i["name"]), None)
    if rod is None:
        raise LookupError("no fishing rod")
    if rod >= 12:                         # hotbar keys reach slots 0-11 only (lesson 61)
        name = next(i["name"] for i in act.inv() if i["slot"] == rod)
        rod = act.to_hotbar(name, target=9)
        if rod is None or rod >= 12: raise LookupError("rod not on hotbar")
    _, me = act.here()
    water = sv.call("water", r=6)
    water.sort(key=lambda t: -((t[0] - me[0]) ** 2 + (t[1] - me[1]) ** 2) if abs(t[0]-me[0]) + abs(t[1]-me[1]) <= 6 else 1e9)
    if not water:
        raise LookupError("no water nearby")
    # cast straight (casts follow the facing direction): pick the direction with the longest water run
    wset = {tuple(t) for t in water}
    best = None
    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        run = 0
        while (me[0] + dx * (run + 1), me[1] + dy * (run + 1)) in wset and run < 8:
            run += 1
        if run and (best is None or run > best[0]):
            best = (run, dx, dy)
    if not best:
        raise LookupError("not facing open water")
    run, dx, dy = best
    target = (me[0] + dx * min(run, 4), me[1] + dy * min(run, 4))
    n = 0
    fish_session._rewalked = False
    caught = set()
    POWERS = [0.97, 0.7, 0.45, 0.25, 0.1] if run >= 5 else [0.6, 0.4, 0.25, 0.1]
    pi, fails = 0, 0
    while n < max_casts:
        s = sv.state()
        if s.get("backpack", 12) - len(s["inventory"]) < 2:
            act.log("fishing: backpack nearly full, stopping session"); break
        if on_full and len(s["inventory"]) >= backpack - 1:
            on_full(caught)
            _, me2 = act.here()
            if me2 != me:
                act.walk(*me)
            s = sv.state()
        if s["time"] >= until_time or s["player"]["stamina"] < min_stamina:
            break
        before = {i["name"]: i["stack"] for i in s["inventory"]}
        # the cast follows the FACING direction, not the cursor: after a walk the farmer may face along the bank
        # (Fa 21/25 screenshot: facing down, water to the right -> every cast hit land). Face the water first
        # with a short tap of the movement key (water is not walkable, so the farmer only turns).
        want_face = {(0, -1): 0, (1, 0): 1, (0, 1): 2, (-1, 0): 3}[(dx, dy)]
        if s["player"].get("facing") != want_face:
            k = s["keys"][{0: "up", 1: "right", 2: "down", 3: "left"}[want_face]]
            sv.call("tap", key=k, ticks=2); time.sleep(0.15)
            if act.here()[1] != me:
                act.walk(*me)
        sv.call("fish", x=target[0], y=target[1], slot=rod, power=POWERS[pi])
        s = sv.wait(lambda s: s["fish"]["status"] != "busy", timeout=180, every=0.2)
        # circuit breaker: casts that never reach water -> try shorter casts, then give up on this spot
        if s["fish"]["status"] == "done:no_cast":
            fails += 1
            if fails == 2 and pi == 0 and not getattr(fish_session, "_rewalked", False):
                # Fa 21: a spot that gave 12 fish failed every cast after an eat: clear stray tasks, re-stand, retry
                fish_session._rewalked = True
                try:
                    sv.call("screenshot", path=f"{act.ROOT}/media/debug/nocast_{s['season']}{s['day']}_{s['time']}.png")
                except Exception: pass
                sv.call("stop"); act.dismiss()
                act.log(f"fishing: 2 casts failed at {me}, facing {s['player'].get('facing')}, item {s['player'].get('item')}: re-standing")
                act.walk(me[0] - dx, me[1] - dy); act.walk(*me)
                fails = 0
            elif fails >= 2:
                pi += 1; fails = 0
                if pi >= len(POWERS):
                    act.log("fishing: no cast power reaches water from here, abandoning spot"); break
                act.log(f"fishing: casts land on shore, trying power {POWERS[pi]}")
        else:
            fails = 0
        if (s.get("menu") or {}).get("type") == "ItemGrabMenu":
            # treasure chest: take everything (click items), then close
            take_all_from_grab_menu()
        act.dismiss()
        after = {i["name"]: i["stack"] for i in sv.state()["inventory"]}
        got = [k for k in after if after[k] > before.get(k, 0)]
        caught.update(got)
        act.log(f"cast {n}: {s['fish']['status']} {got} (bites {s['fish']['bites']} catches {s['fish']['catches']} escapes {s['fish']['escapes']})")
        n += 1
    return n
