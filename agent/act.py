"""Mid-level actions built on the ClaudeHands API: walking across maps, tools, farming."""
import time
from collections import deque
import sv

LOG = []

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, "stats", "events.jsonl")

def log(msg, **extra):
    s = sv.state()
    t = f"{s.get('season','?')} {s.get('day','?')} {s.get('time','?')}"
    line = f"[{t}] {msg}"
    LOG.append(line)
    print(line, flush=True)
    event(msg, s, **extra)

def event(msg, s=None, **extra):
    """Structured stats: one JSON line per agent event, with a full player snapshot."""
    import json, os
    try:
        s = s or sv.state()
        p = s.get("player", {})
        row = {"real": time.time(), "year": s.get("year"), "season": s.get("season"), "day": s.get("day"),
               "time": s.get("time"), "weather": s.get("weather"), "loc": p.get("loc"),
               "money": p.get("money"), "stamina": p.get("stamina"), "health": p.get("health"),
               "skills": p.get("skills"), "inv_used": len(s.get("inventory", [])), "backpack": s.get("backpack"),
               "msg": msg, **extra}
        can = next((i for i in s.get("inventory", []) if i["name"] == "Watering Can"), None)
        if can and can.get("water") is not None:
            row["can"], row["can_max"] = can["water"], can["water_max"]
        os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
        with open(EVENTS, "a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass

# ---------- basics ----------

def wait_done(key, timeout=30):
    def ok(s):
        if (s.get("menu") or {}).get("type") == "GameMenu":   # auto-paused: resume
            sv.call("tap", key="Escape", ticks=5)
        return s[key] not in ("walking", "busy")
    return sv.wait(ok, timeout=timeout, every=0.05)

def dismiss(max_n=10):
    """Click through dialogue boxes / letters like a player."""
    for _ in range(max_n):
        s = sv.state()
        m = s.get("menu")
        if m and m["type"] == "ItemListMenu":          # "items lost" after passing out: OK through it
            ok = [x for x in sv.widgets()["widgets"] if x["field"] == "okButton"]
            if ok:
                sv.call("click", x=ok[0]["x"], y=ok[0]["y"]); time.sleep(0.6); continue
        if not m or m["type"] not in ("DialogueBox", "LetterViewerMenu", "LevelUpMenu"):
            if s.get("skip_button"):
                sv.call("click", x=s["skip_button"][0], y=s["skip_button"][1]); time.sleep(0.5); continue
            if s.get("event"):
                sv.call("click", x=400, y=400); time.sleep(0.3); continue
            return s
        if m["type"] == "DialogueBox":
            resp = [w for w in sv.widgets()["widgets"] if w["field"] == "responseCC"]
            if resp:
                # question dialogues ignore a plain click. Farm cave (Demetrius): Mushrooms (first) -> Red/Purple
                # Mushrooms for Dye, Exotic and Field Research. Other questions: last option (usually No/Leave).
                txt = (m.get("text") or "").lower()
                yes_first = ("prefer" in txt or "return to stardew valley" in txt)     # eat prompts: mining.eat_if_hurt clicks Yes itself; stray ones (jar busy) -> No
                pick = resp[0] if yes_first else resp[-1]
                log(f"dialogue question '{(m.get('text') or '')[:60]}': picking option {resp.index(pick) + 1}/{len(resp)}")
                sv.call("click", x=pick["x"], y=pick["y"]); time.sleep(0.5); continue
        sv.call("click", x=400, y=400)
        time.sleep(0.35)
    return sv.state()

def inv():
    return sv.state()["inventory"]

TOOL_BASES = ("Axe", "Pickaxe", "Hoe", "Watering Can")
TOOL_TIERS = ("Copper", "Steel", "Gold", "Iridium")

def slot_of(name):
    for it in inv():
        if it["name"] == name:
            return it["slot"]
    if name in TOOL_BASES:           # upgraded tools: "Copper Axe" etc. still answer to "Axe"
        for it in inv():
            if it["name"] in tuple(f"{t} {name}" for t in TOOL_TIERS):
                return it["slot"]
    return None

def walk(x, y, adjacent=False, timeout=180, expect_loc=None):
    m = sv.state().get("menu")
    if m and m["type"] in ("DialogueBox", "LetterViewerMenu"):
        dismiss()
    elif m and m["type"] in _STRAY:
        # Su 22 Y2: an extra chest's menu stayed open; every walk timed out and the clock froze at 6:20
        log(f"SANITY: {m['type']} left open before a walk: closing it")
        import town; town.close_menu()
    loc_start, me = here()
    if expect_loc and loc_start != expect_loc:
        return "location_changed"         # Fa 24: the warp was already crossed; (x, y) belong to the old map
    d = abs(me[0] - x) + abs(me[1] - y)
    if (adjacent and d == 1) or (not adjacent and d == 0):
        return "arrived"
    if d >= 30:      # long walks are where game time goes (Amer, Fa 22: "going to corner of farm unnecessarily")
        import traceback
        fr = [f"{f.name}:{f.lineno}" for f in traceback.extract_stack()[-5:-1]]
        log(f"long walk {me}->{(x, y)} ({d} tiles) by {' < '.join(reversed(fr))}")
    fast = _slow_depth > 0 and _slow_prev and _slow_prev > 1 and d >= 10
    if fast: sv.call("speed", n=_slow_prev)          # Fa 23: chest trips inside @slow walked across the map at 1x
    sv.call("walk", x=x, y=y, adjacent=adjacent)
    # W8: a stuck walker waited the full 180 s real, which at 12x is a whole game night (passed out at 2:00).
    # The farmer walks ~5 tiles/s at 1x, so 12 s + 0.5 s/tile is generous at any speed.
    # W15: at 12x a whole game night passes in ~30 s real, so the limit must shrink with the speed.
    try:
        sv.call("speed"); spd = sv.SPEED[0]
    except Exception: spd = 1
    # session 6: sv.wait already scales by the fast-forward factor; scaling here too cut walks at 0.5 s real
    t_game = min(timeout, max(12.0, (12 + 0.5 * d) * 1.5))       # in 1x seconds
    t_lim = max(0.5, t_game * 2.0 / spd) if spd > 1 else t_game  # real seconds, for the log only
    try:
        s = wait_done("walker", t_game)
    except TimeoutError:
        sv.call("stop")
        log(f"walk to {(x, y)} timed out after {t_lim:.0f}s (from {me}); walker stopped")
        s = sv.state(); s["walker"] = "failed:timeout"
    finally:
        if fast: sv.call("speed", n=1)
    st = s["walker"]
    # only when the walk failed on the Farm itself: a walk that crossed a warp (FarmCave exit -> Farm) reports
    # failed:location_changed, and clearing a path to the old map's coordinates sent the farmer to the far west
    # corner of the farm every cave visit (Amer, Fa 22-23)
    if st.startswith("failed") and st != "failed:location_changed" and _clear_ok and s["player"]["loc"] == "Farm" and loc_start == "Farm":
        # blocked by debris: clear a path like a player would, then retry
        import farming
        goals = [(x, y)] if not adjacent else [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
        for gtile in goals:
            _clear(False)
            try:
                ok = farming.clear_path_to(gtile)
            finally:
                _clear(True)
            if ok:
                return "arrived"
    return st

_clear_ok = True
def _clear(v):
    global _clear_ok
    _clear_ok = v

def to_hotbar(name, target=11, slot=None):
    """Hotbar keys reach slots 0-11 only. Move an item from the 2nd/3rd row into the hotbar the way
    a player does: open the inventory, click the item, click a hotbar slot (they swap), close.
    slot: move that exact stack (quality-specific) instead of the first stack with this name."""
    if slot is None and name in TOOL_BASES:      # upgraded tool ("Copper Pickaxe" for "Pickaxe"), Fa 25
        slot = slot_of(name)
        if slot is None or slot < 12: return slot
        name = next((i["name"] for i in inv() if i["slot"] == slot), name)
        r = to_hotbar(name, target, slot)
        return r
    it = next((i for i in inv() if (i["slot"] == slot if slot is not None else i["name"] == name)), None)
    if not it or it["slot"] < 12:
        return it and it["slot"]
    # never push a tool out of the hotbar to make room (W4: food swapped the Pickaxe out of slot 11)
    keep = ("Axe", "Pickaxe", "Hoe", "Watering Can", "Milk Pail", "Scythe", "Rod", "Pole", "Sword", "Femur", "Saber", "Dirk", "Blade", "Club")
    occ = {i["slot"]: i["name"] for i in inv()}
    if any(k in occ.get(target, "") for k in keep):
        free = [t for t in range(11, -1, -1) if t not in occ] + \
               [t for t in range(11, -1, -1) if t in occ and not any(k in occ[t] for k in keep)]
        if free: target = free[0]
    if not sv.state().get("menu"):
        sv.call("tap", key="Escape", ticks=5)
        for _ in range(20):                   # W4 (mine, 2x): the menu was not open yet, so no clicks happened
            time.sleep(0.15)
            if (sv.state().get("menu") or {}).get("type") == "GameMenu": break
    # the game menu reopens on the LAST tab used (often Crafting, whose layout has the trash can where the
    # inventory row is expected): switch to the Inventory tab first (Su 2-3: two scarecrows trashed)
    tab = next((x for x in sv.widgets()["widgets"] if x["field"] == "tabs" and x["name"] == "inventory"), None)
    if tab:
        sv.call("click", x=tab["x"], y=tab["y"]); time.sleep(0.5)
    if (sv.state().get("menu") or {}).get("page") not in (None, "InventoryPage"):
        log(f"to_hotbar: not on inventory page ({sv.state().get('menu')}), aborting")
        import town; town.close_menu(); return it["slot"]
    def wid(i):
        return next((x for x in sv.widgets()["widgets"] if x["field"].endswith("inventory.slot") and x["i"] == i), None)
    a, b = wid(it["slot"]), wid(target)
    if not (a and b):
        log(f"to_hotbar {name}: inventory widgets missing (menu {sv.state().get('menu')})")
    if a and b:
        sv.call("click", x=a["x"], y=a["y"]); time.sleep(0.25)
        sv.call("click", x=b["x"], y=b["y"]); time.sleep(0.25)
        held = sv.state().get("inventory")
        # the item that was in the hotbar slot is now on the cursor: drop it into the emptied slot
        sv.call("click", x=a["x"], y=a["y"]); time.sleep(0.25)
    import town; town.close_menu()
    if slot_of(name) is None:
        log(f"ERROR to_hotbar: {name} disappeared from the backpack")
    if slot is not None:
        return target if any(i["slot"] == target and i["name"] == name for i in inv()) else None
    return slot_of(name)

_STRAY = ("ItemGrabMenu", "ShopMenu", "CraftingPage", "JunimoNoteMenu", "CarpenterMenu", "PurchaseAnimalsMenu", "ShippingMenu", "LevelUpMenu", "AnimalQueryMenu")   # W23 Y2: clicking a petted hen opens its info panel; walks froze

def use(x, y, tool=None, right=False):
    m = sv.state().get("menu")
    if m and m["type"] in _STRAY:      # Su 25 Y2: chest menu left open by a withdraw -> barn door click failed
        log(f"SANITY: {m['type']} left open before a use at {(x, y)}: closing it")
        import town; town.close_menu()
    if right and not tool:
        tool = "Axe" if slot_of("Axe") is not None else None   # never right-click with food in hand (eat prompt)
    slot = slot_of(tool) if tool else -1
    if tool and slot is None:
        raise LookupError(f"no {tool} in inventory")
    if tool and slot >= 12:
        slot = to_hotbar(tool)
        if slot is None or slot >= 12:
            raise LookupError(f"could not move {tool} to the hotbar")
    s0 = sv.state() if right else None
    sv.call("use", x=x, y=y, slot=slot if slot is not None else -1, right=right)
    # Su 27 Y2 floor 85: a weapon swing never reported done (combat reflex kept the tool busy) and each use waited
    # ~30 game minutes. Tools finish in < 2 game seconds.
    try:
        s = wait_done("tool", 4)
    except TimeoutError:
        sv.call("stop"); s = sv.state(); s["tool"] = "failed:timeout"
        log(f"SANITY: tool {tool} at {(x, y)} did not finish; stopped")
    if right and NP_CHECK[0]:
        _no_progress(s0, sv.state(), (x, y))
    return s["tool"]

NP_CHECK = [True]      # off for animal petting (friendship is invisible: a pet changes nothing we can see)

class NoProgress(RuntimeError):
    pass

_NP = [0, []]
def _sig(s):
    return (tuple((i["name"], i["stack"]) for i in s.get("inventory") or []), s["player"]["money"], s["player"]["loc"],
            (s.get("menu") or {}).get("type"), s["player"].get("stamina"), s["player"].get("health"))

def _no_progress(s0, s1, tile):
    """Sanity breaker (Amer, Su 17 Y2: "u r picking things when inventory full"): a right-click that changes nothing
    (inventory, money, map, menu, energy, health) is a wasted action. 8 in a row -> stop the step, say why."""
    if _sig(s0) != _sig(s1):
        _NP[0] = 0; _NP[1] = []; return
    _NP[0] += 1; _NP[1] = (_NP[1] + [tile])[-8:]
    if _NP[0] >= 8:
        full = len(s1.get("inventory") or []) >= s1.get("backpack", 12)
        _NP[0] = 0
        msg = f"SANITY: 8 right-clicks changed nothing {_NP[1]}" + (" - backpack FULL" if full else "")
        log(msg)
        raise NoProgress(msg)

def here():
    p = sv.state()["player"]
    return p["loc"], tuple(p["tile"])

# ---------- cross-map routing ----------

_world = None

def world():
    global _world
    if _world is None:
        _world = sv.call("world")
        # farmhouse door is a building, not a map warp (Standard farm: door tile 64,14)
        _world.setdefault("Farm", []).append({"x": 64, "y": 14, "to": "FarmHouse", "tx": 3, "ty": 11, "door": True})
    return _world

def route(dest):
    src, _ = here()
    if src == dest:
        return []
    prev = {src: None}
    q = deque([src])
    while q:
        cur = q.popleft()
        for w in world().get(cur, []):
            nxt = w["to"]
            if nxt in CLOSED: continue      # evening festival map, closed until it starts (Fa 27 Spirit's Eve)
            if nxt not in prev and nxt in world():
                prev[nxt] = (cur, w)
                if nxt == dest:
                    hops = []
                    n = dest
                    while prev[n]:
                        hops.insert(0, prev[n][1]); n = prev[n][0]
                    return hops
                q.append(nxt)
    raise LookupError(f"no route {src} -> {dest}")

CLOSED = set()

def _take_warp(w):
    loc0, _ = here()
    a = sv.call("around", r=1)
    W, H = a["w"], a["h"]
    x, y = w["x"], w["y"]
    if w["door"]:
        walk(x, y, adjacent=True, expect_loc=loc0)
        use(x, y, right=True)
    else:
        cx, cy = min(max(x, 0), W - 1), min(max(y, 0), H - 1)
        # session 6 (Su 3-6 Y2): the listed Backwoods->Mountain tile (50,10) clamps to (49,10), a wall: no_path,
        # path clearing, lost afternoons. Use the nearest walkable edge tile among all warps to the same map.
        try:
            rows = sv.call("grid")["rows"]; _, me = here()
            cands = []
            for ww in a.get("warps", []):
                if ww["to"] != w["to"]: continue
                tx, ty = min(max(ww["x"], 0), W - 1), min(max(ww["y"], 0), H - 1)
                if rows[ty][tx] == ".": cands.append((abs(tx - me[0]) + abs(ty - me[1]), tx, ty))
            if cands and rows[cy][cx] != ".":
                _, cx, cy = min(cands)
        except Exception as e:
            log(f"warp tile choice failed: {e!r}"); cands = []
        st = walk(cx, cy, expect_loc=loc0)
        if st not in ("arrived", "location_changed") and here()[0] == loc0:
            st = walk(cx, cy, adjacent=True, expect_loc=loc0)      # warp tile itself often collides; a neighbour is enough
        # Su 21-22 Y2: Backwoods (49,17) "no free path" (blocked by an NPC/monster in the corridor?): try the other
        # edge tiles of the same warp before clearing a path
        for _, ax, ay in sorted(cands)[:6]:
            if st in ("arrived", "location_changed") or here()[0] != loc0: break
            if (ax, ay) == (cx, cy): continue
            st = walk(ax, ay, expect_loc=loc0)
            if st == "arrived": cx, cy = ax, ay
        if here()[0] != loc0:
            st = "arrived"                        # walking there already crossed the warp (or a festival map loaded)
        if st != "arrived":
            import farming
            log(f"no free path to warp ({cx},{cy}); clearing a path (screenshot media/debug/nopath_*.png)")
            try:
                s_ = sv.state(); sv.call("screenshot", path=f"{ROOT}/media/debug/nopath_{s_['season']}{s_['day']}_{s_['time']}.png")
            except Exception: pass
            farming.clear_path_to((cx, cy))
        # step outward over the map edge / onto the warp
        o = sv.state()["keys"]  # bindings come from the game's options
        if y < 0 or (y <= 0): key = o["up"]
        elif y >= H - 1: key = o["down"]
        elif x <= 0: key = o["left"]
        elif x >= W - 1: key = o["right"]
        else:
            # in-map warp tile: walk onto it
            key = None
        if key and here()[0] == loc0:
            sv.call("hold", down=[key])
            try:
                sv.wait(lambda s: s["player"]["loc"] != loc0, timeout=4)
            finally:
                sv.call("hold", up=[key])
    sv.wait(lambda s: s["player"]["loc"] != loc0, timeout=10)
    # arrival may start a cutscene (Lewis, Marlon, Willy...): click through until free
    for _ in range(300):
        s = dismiss()
        if s.get("free") and not s.get("event"):
            break
        time.sleep(0.3)
    time.sleep(0.2)

def goto(dest, x=None, y=None, adjacent=False):
    if here()[0].startswith("UndergroundMine") and not dest.startswith("UndergroundMine"):
        import mining
        mining.leave()
    loc = here()[0]
    if loc != dest and loc not in world():
        # building interiors (Coop<guid>, Barn<guid>) are not in the warp graph (W12: stuck in the coop all day):
        # leave by the interior's own warp first
        a = sv.call("around", r=1)
        ws = a.get("warps") or []
        if ws:
            w = next((w for w in ws if w["to"] == "Farm"), ws[0])
            # animal-house exits are a warp tile at the bottom wall (W16: (2,9) "no free path"): stand on the
            # tile above it and step down onto it
            k = sv.state()["keys"]["down"]
            for _try in range(12):           # Sp 15: a hen on the door tile blocked the exit for 2 game hours
                walk(w["x"], w["y"] - 1, timeout=6)
                sv.call("hold", down=[k])
                try:
                    sv.wait(lambda st: st["player"]["loc"] != loc, timeout=3)
                except TimeoutError:
                    pass
                finally:
                    sv.call("hold", up=[k])
                if here()[0] != loc: break
                # W16 Y2: hens between farmer and door; 0.5 s real at 1x is too short for them to move. Let game
                # time run a little (turbo) so they wander off, then retry.
                sv.call("turbo", sec=1.5); time.sleep(1.6); sv.call("turbo", sec=0)
            if here()[0] == loc:
                _take_warp({"x": w["x"], "y": w["y"], "door": False, "to": w["to"]})
            for _ in range(20):
                st = dismiss()
                if st.get("free") and not st.get("event"): break
                time.sleep(0.2)
    for w in route(dest):
        _take_warp(w)
    if x is not None:
        return walk(x, y, adjacent)
    return "arrived"

# ---------- pause discipline: game clock only runs while a script acts ----------

def pause():
    for _ in range(4):
        s = sv.state()
        if s.get("menu"):
            return
        sv.call("tap", key="Escape", ticks=5); time.sleep(0.4)

def unpause():
    for _ in range(4):
        s = sv.state()
        if (s.get("menu") or {}).get("type") != "GameMenu":
            return
        sv.call("tap", key="Escape", ticks=5); time.sleep(0.4)

def reel_in():
    """If a rod is still cast (player frozen), click to reel it in."""
    for _ in range(10):
        s = sv.state()
        if not s.get("world_ready") or not s["player"]["using_tool"]:
            return
        sv.call("mouse", left=True); time.sleep(0.1); sv.call("mouse", left=False); time.sleep(0.8)
        dismiss()

LOCK = "/tmp/claude-1000/stardew_agent.pid"

def _take_lock():
    """Only one controller at a time: kill any previous agent process."""
    import os, signal
    try:
        old = int(open(LOCK).read())
        if old != os.getpid():
            os.kill(old, signal.SIGTERM); time.sleep(0.5)
    except Exception:
        pass
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    open(LOCK, "w").write(str(os.getpid()))

def run(fn):
    """Unpause, run fn, always pause again (also on error) so thinking time costs no game time."""
    _take_lock()
    unpause()
    dismiss()
    try:
        return fn()
    finally:
        try:
            sv.call("release"); reel_in(); pause()
        except Exception as e:
            print("pause failed", e)

# ---------- speed control ----------
# Python round trips cost real time; at 8x fast-forward every real second is ~8 game minutes.
# Click-heavy local loops (watering, planting, menus) therefore run at 1x; travel and the
# mod-internal walker/fishing controller keep the fast speed. Fair: the whole game runs slower.
import functools
_slow_depth = 0

_slow_prev = None

def slow(fn):
    @functools.wraps(fn)
    def wrap(*a, **k):
        global _slow_depth
        prev = None
        if _slow_depth == 0:
            try:
                prev = sv.call("speed").get("speed", 1)
                # session 6: with the turbo gate, Python-driven clicks already run at 1x and mod tasks need turbo;
                # forcing speed 1 made Su 19 harvest+watering take 11 game hours. Only pre-gate speeds (<= 16) slow.
                if prev > 16: prev = None
                elif prev > 1: sv.call("speed", n=1)
            except Exception:
                prev = None
        global _slow_prev
        if _slow_depth == 0: _slow_prev = prev
        _slow_depth += 1
        try:
            return fn(*a, **k)
        finally:
            _slow_depth -= 1
            if _slow_depth == 0 and prev and prev > 1:
                sv.call("speed", n=prev)
    return wrap
