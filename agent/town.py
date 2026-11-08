"""Shopping, foraging, sleeping."""
import time
import sv, act

SUMMER_FORAGE = {"Spice Berry", "Grape", "Sweet Pea"}      # Red Mushroom/Fiddlehead: Secret Woods (woods.py)
FALL_FORAGE = {"Common Mushroom", "Wild Plum", "Hazelnut", "Blackberry"}
WINTER_FORAGE = {"Crystal Fruit", "Crocus", "Winter Root", "Snow Yam"}   # roots/yams: hoe Artifact Spots (wiki)
SPRING_FORAGE = {"Wild Horseradish", "Daffodil", "Leek", "Dandelion", "Spring Onion", "Salmonberry", "Morel", "Common Mushroom"}

def forage_nearby(r=10, max_items=20, products=False):
    """Pick up spawned forage within r tiles (right-click, like a player)."""
    got = 0; skip = set(); fails = 0
    for _ in range(max_items):
        a = sv.call("around", r=r)
        loc, me = act.here()
        # products=True (inside a coop): eggs/feathers/wool are spawned objects but not isForage() (W6 Y2: 0 picked)
        items = [o for o in a["objects"] if (o.get("forage") or (products and o.get("spawned") and not o.get("bc")))
                 and (o["x"], o["y"]) not in skip]
        if not items:
            break
        # W5 Y2: 51 uncollected eggs covered the coop floor; the nearest one lay UNDER the farmer at the door, its
        # adjacent-walk failed and the loop broke -> eggs blocked every path (no hay, no petting for weeks).
        # Own tile and adjacent tiles first (no walk), unreachable items skipped instead of ending the loop.
        items.sort(key=lambda o: abs(o["x"] - me[0]) + abs(o["y"] - me[1]))
        o = items[0]
        st = sv.state()
        if len(st["inventory"]) >= st.get("backpack", 12) and not any(i["name"] == o["name"] for i in st["inventory"]):
            act.log(f"forage: backpack full, skipping {len(items)} items"); break   # sanity: never forage blind
        d = abs(o["x"] - me[0]) + abs(o["y"] - me[1])
        if d > 1 and act.walk(o["x"], o["y"], adjacent=True) != "arrived":
            skip.add((o["x"], o["y"])); fails += 1
            if fails >= 6: break
            continue
        n0 = sum(i["stack"] for i in act.inv())
        act.use(o["x"], o["y"], right=True)
        act.dismiss()
        if sum(i["stack"] for i in act.inv()) <= n0:
            act.log(f"could not pick {o['name']} at {(o['x'], o['y'])} from {me} (backpack full?)")
            skip.add((o["x"], o["y"])); fails += 1
            if fails >= 6: break
            continue
        got += 1
        act.log(f"foraged {o['name']}")
    return got

def open_shop(location, action_prefix="Buy "):
    global _last_shop
    _last_shop = location
    if location == "SeedShop" and sv.state()["time"] < 900:   # Pierre's door + counter open 9:00 (wiki)
        act.goto("Town")
        sv.wait_clock(900)
    act.goto(location)
    acts = sv.call("actions")
    counters = [a for a in acts if a["action"].startswith(action_prefix)]
    if not counters:
        raise LookupError(f"no {action_prefix} tile in {location}: {acts[:5]}")
    c = counters[0]
    act.walk(c["x"], c["y"], adjacent=True)
    for attempt in range(6):          # the shopkeeper may still be walking to the counter at opening time
        act.use(c["x"], c["y"], right=True)
        try:
            sv.wait(lambda s: (s.get("menu") or {}).get("type") in ("ShopMenu", "DialogueBox"), timeout=5)
            break
        except TimeoutError:
            if attempt == 5: raise
            act.log(f"shop {location}: counter not answering at {sv.state()['time']}, retrying")
            time.sleep(3)
    s = sv.state()
    if (s.get("menu") or {}).get("type") == "DialogueBox":
        act.dismiss()
    time.sleep(0.6)      # ShopMenu ignores clicks for its first 250 ms (safetyTimer)
    return sv.call("shop")

_last_shop = None

def _reopen():
    open_shop(_last_shop)

@act.slow
def buy(wants):
    """wants: {display name: qty}. Scrolls the shop list and right-clicks items (1 per click)."""
    # session 6: ShopMenu ignores clicks for 250 ms after opening (LESSONS 17). Turbo used to burn that instantly;
    # with the game at 1x while Python acts, the first item bought nothing (Su 12 Y2: Melon/Wheat Seeds "spent 0g").
    time.sleep(0.4)
    for name, qty in wants.items():
        sh = sv.call("shop")
        idx = next((it["i"] for it in sh["items"] if it["name"] == name), None)
        if idx is None:
            act.log(f"shop has no {name}"); continue
        for _ in range(60):
            sh = sv.call("shop")
            top = sh["top"]
            if top <= idx < top + len(sh["buttons"]):
                break
            arrow = sh["down"] if idx >= top + len(sh["buttons"]) else sh["up"]
            sv.call("click", x=arrow["x"], y=arrow["y"]); time.sleep(0.3)
        time.sleep(0.3)        # Su 13 Y2: at 1x a click 0.12 s after a scroll click was lost (Wheat Seeds spent 0g)
        b = sh["buttons"][idx - sh["top"]]
        m0 = sh["money"]
        st = sv.state()
        if len(st["inventory"]) >= st.get("backpack", 12) and not any(i["name"] == name for i in st["inventory"]):
            act.log(f"buy {name}: backpack full, cannot buy (Su 13-16 Y2: silent 'spent 0g')"); continue
        # Shortcuts (Amer): wiki says Shift + click = 5 and Ctrl + Shift + click = 25, but Sp 28 Y2 one Ctrl+Shift click
        # bought 125 Wood (2,000 Wood for 20,000g). So measure: one modified click, units = money spent / price,
        # then repeat only while the remainder is at least that many units.
        price = next((it["price"] for it in sh["items"] if it["i"] == idx), -1)
        left = qty; retries = 0
        for keys in (["LeftControl", "LeftShift"], ["LeftShift"], []):
            if left <= 0: break
            per = None
            while left > 0:
                if per is not None and per > left: break
                # first probe only when even the largest observed multiple cannot overbuy (Ctrl+Shift = 125 seen)
                # session 6: measured at 1x (Su 19 Y2): Shift = 5, Ctrl+Shift = 25 (wiki). The old 125 was turbo
                # repeating one held click; Python's clicks now run at 1x (turbo gate)
                if per is None and keys and left < (25 if len(keys) == 2 else 5): break
                m_before = sv.call("shop")
                if m_before is None: break
                if keys: sv.call("hold", down=keys); time.sleep(0.05)
                try:
                    sv.call("click", x=b["x"], y=b["y"]); time.sleep(0.3)
                finally:
                    if keys: sv.call("hold", up=keys); time.sleep(0.05)
                m_after = sv.call("shop")
                if m_after is None: left = 0; break
                spent = m_before["money"] - m_after["money"]
                got = spent // price if price > 0 else 1
                if got <= 0 and per is None and not keys and m_after["money"] >= price and retries < 3:
                    retries += 1; time.sleep(0.5); continue  # Su 13-14 Y2: first click after a scroll was lost in-run
                if got <= 0: left = 0; break                 # not affordable / out of stock
                per = got if per is None else per
                left -= got
                if keys and per > qty: act.log(f"buy {name}: one {'+'.join(keys)} click bought {per}")
        time.sleep(0.2)
        now = sv.call("shop")
        if now is None:                       # tool upgrades close the shop on purchase
            act.log(f"bought {name}: shop closed after purchase, money now {sv.state()['player']['money']}")
            return
        act.log(f"bought {name}: spent {m0 - now['money']}g (idx {idx}, top {sh['top']}, btn {b})")
        # purchase sits on the cursor: drop it into an empty backpack slot (shop won't close while holding)
        filled = {i["slot"] for i in sv.state()["inventory"]}
        e = [x for x in sv.widgets()["widgets"] if x["field"] == "inventory.slot" and x["i"] not in filled and x["i"] < sv.state().get("backpack", 12)]
        same = next((i for i in sv.state()["inventory"] if i["name"] == name), None)
        tgt = next((x for x in sv.widgets()["widgets"] if x["field"] == "inventory.slot" and same and x["i"] == same["slot"]), None) or (e[0] if e else None)
        if tgt:
            sv.call("click", x=tgt["x"], y=tgt["y"]); time.sleep(0.3)

def close_menu():
    for _ in range(8):
        m = sv.state().get("menu")
        if not m:
            return True
        w = sv.widgets()["widgets"]
        close = [x for x in w if x["field"] == "upperRightCloseButton"] or [x for x in w if x["field"] == "okButton"]
        if close:
            sv.call("click", x=close[0]["x"], y=close[0]["y"])
        elif m["type"] in ("DialogueBox", "LetterViewerMenu", "LevelUpMenu"):
            sv.call("click", x=400, y=400)
        else:
            sv.call("tap", key="Escape", ticks=5)
        time.sleep(0.5)
    raise RuntimeError("menu will not close")

def sleep():
    """Go home, walk into the bed, answer Yes. Day ends and the game saves."""
    # Sp 15, Su 10 Y3: the farmhouse door warp timed out (animal or debris on the porch); the runner crashed and the
    # supervisor restarted the day. Retry the trip home a few times before giving up.
    for _try in range(4):
        try:
            act.goto("FarmHouse"); break
        except TimeoutError:
            act.log(f"sleep: door warp timed out (try {_try + 1}); retrying")
            sv.call("stop"); close_menu(); act.dismiss(); time.sleep(0.5)
            # Su 11 Y3: wild trees boxed the farmer in next to the chests: chop adjacent trees, then retry
            try:
                import farming
                loc, me = act.here()
                if loc == "Farm":
                    _, feats, _ = farming.tile_info(r=2)
                    for d in ((-1, 0), (0, 1), (0, -1), (1, 0)):
                        t = (me[0] + d[0], me[1] + d[1])
                        if (feats.get(t) or {}).get("type") == "Tree":
                            for _h in range(25):
                                act.use(*t, tool="Axe")
                                if (farming.tile_info(r=2)[1].get(t) or {}).get("type") != "Tree": break
                            act.log(f"sleep: chopped tree at {t} to get out")
                    farming.collect_debris(r=2)
            except Exception as e:
                act.log(f"sleep: tree chopping failed: {e!r}")
            if _try == 3: raise
    act.walk(6, 8)                      # step away from the exit first
    sv.call("walk", x=10, y=9)          # walking into the bed (Standard farmhouse) asks "Go to sleep?"
    sv.wait(lambda s: (s.get("menu") or {}).get("type") == "DialogueBox", timeout=30)
    sv.call("stop")
    for _ in range(30):                 # answer buttons appear after the text finishes typing
        yes = [x for x in sv.widgets()["widgets"] if x["field"] == "responseCC"]
        if yes: break
        time.sleep(0.3)
    act.log("going to sleep")
    for _ in range(6):
        m = sv.state().get("menu")
        if not m or m["type"] != "DialogueBox" or "sleep" not in m.get("text", ""):
            break
        yes = [x for x in sv.widgets()["widgets"] if x["field"] == "responseCC"]
        if yes:
            sv.call("mouse", x=yes[0]["x"], y=yes[0]["y"]); time.sleep(0.3)   # hover first, then click
            sv.call("click", x=yes[0]["x"], y=yes[0]["y"])
        time.sleep(1.5)

def sleep_and_wake():
    """Sleep, click through shipping/level-up screens, return when the new day is playable."""
    day0 = sv.state()["day"]
    sleep()
    sv.wait(lambda s: s.get("day") != day0, timeout=180, every=1)
    for _ in range(120):
        s = act.dismiss()
        if s.get("free") and s.get("world_ready"):
            break
        m = s.get("menu")
        if m:
            w = sv.widgets()
            ok = [x for x in w["widgets"] if x["field"] in ("okButton", "okButtonCC") or x["name"] == "OK"]
            if ok:
                sv.call("click", x=ok[0]["x"], y=ok[0]["y"])
            elif m["type"] == "LevelUpMenu":
                sv.call("click", x=400, y=400)
        time.sleep(1)
    s = sv.state()
    act.log(f"NEW DAY Y{s['year']} {s['season']} {s['day']} money {s['player']['money']} weather {s['weather']}")
    return s


def dig_artifact_spots(r=40, max_n=8):
    """Hoe the Artifact Spots (wiggling worms) in range: Winter Root / Snow Yam in winter (wiki: 17-24%), artifacts."""
    n = 0
    for _ in range(max_n):
        a = sv.call("around", r=r)
        spots = [o for o in a["objects"] if o["name"] == "Artifact Spot"]
        if not spots or sv.state()["player"]["stamina"] < 20: break
        loc, me = act.here()
        o = min(spots, key=lambda o: abs(o["x"] - me[0]) + abs(o["y"] - me[1]))
        if act.walk(o["x"], o["y"], adjacent=True) != "arrived": break
        act.use(o["x"], o["y"], tool="Hoe")
        import farming; farming.collect_debris(r=3)
        n += 1
    if n: act.log(f"dug {n} artifact spots")
    return n

def till_for_roots(n=30, min_stamina=60):
    """Winter: each tilled tile off the farm has a 4% Winter Root chance (wiki Winter Root; Snow Yam similar).
    Hoe free Diggable tiles nearby as one mod-side batch (SeqTask, animation cancelled once tilled)."""
    s = sv.state()
    if s["player"]["stamina"] < min_stamina or s["player"]["loc"] == "Farm": return 0
    try:
        tiles = [(t["x"], t["y"]) for t in sv.call("diggable", r=10)]
    except Exception as e:
        act.log(f"till_for_roots: mod has no diggable endpoint ({e!r})"); return 0
    hoe = act.slot_of("Hoe")
    if hoe is None or not tiles: return 0
    if hoe >= 12: hoe = act.to_hotbar("Hoe")
    _, me = act.here()
    tiles.sort(key=lambda t: (t[1], t[0] if t[1] % 2 else -t[0]))        # snake rows: short walks
    tiles = tiles[:min(n, int((s["player"]["stamina"] - min_stamina + 20) / 2))]
    ops = []
    for t in tiles:
        ops += [{"op": "walk", "x": t[0], "y": t[1], "adjacent": True},
                {"op": "use", "x": t[0], "y": t[1], "slot": hoe, "cancel": "hoe"}]
    inv0 = {i["name"]: i["stack"] for i in act.inv()}
    sv.call("seq", ops=ops)
    for _ in range(1500):
        st = sv.call("seq_status")
        if st["status"] != "busy": break
        time.sleep(0.2)
    import farming; farming.collect_debris(r=12)
    got = {k: v - inv0.get(k, 0) for k, v in ((i["name"], i["stack"]) for i in act.inv()) if v > inv0.get(k, 0)}
    act.log(f"tilled {len(tiles)} tiles for roots: {st} -> {got}")
    return len(tiles)


PIERRE_CATS = (-75, -79, -80, -81, -5, -6, -26, -7, -74)   # wiki: forage, crops, seeds, artisan goods, cooked, animal products


def sell_until(target, protect=()):
    """Shop open (Pierre): sell crops/forage/animal goods from the backpack until money >= target.
    Amer (Su 19 Y2): "for instant money, u can sell stuff to pierre". Bundle items and quality holds are never sold."""
    import needs
    keep = set(needs.quota()) | set(needs.quality_holds()) | set(protect)
    sold = 0
    for _ in range(24):
        st = sv.state()
        if st["player"]["money"] >= target: break
        items = [i for i in st["inventory"] if i.get("cat") in PIERRE_CATS and i["name"] not in keep and i.get("price", 0) > 0]
        if not items: break
        it = max(items, key=lambda i: i["price"] * i["stack"])
        w = next((x for x in sv.widgets()["widgets"] if x["field"] == "inventory.slot" and x["i"] == it["slot"]), None)
        if not w: break
        m0 = st["player"]["money"]
        sv.call("click", x=w["x"], y=w["y"]); time.sleep(0.4)
        m1 = sv.state()["player"]["money"]
        if m1 <= m0:
            act.log(f"sell {it['name']}: shop did not buy it"); keep.add(it["name"]); continue
        sold += m1 - m0
        act.log(f"sold {it['name']} x{it['stack']} to the shop for {m1 - m0}g")
    return sold
